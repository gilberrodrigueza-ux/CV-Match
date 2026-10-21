"""Funciones para ser más eficiente en la búsqueda: banco de respuestas para formularios, empresas favoritas,
frescura de las ofertas, simulador de entrevista, plan de estudio y resumen diario por Outlook."""
import json
import re
from datetime import date, datetime

from .config import DATA_DIR
from .prompts import REGLA_NO_INVENTAR

BANCO = DATA_DIR / "banco_formularios.json"
PLAN = DATA_DIR / "plan_estudio.json"
PRACTICA = DATA_DIR / "practicas_entrevista.json"
DIGEST = DATA_DIR / "ultimo_resumen.txt"


def _leer(p, defecto):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return defecto


def _escribir(p, data):
    DATA_DIR.mkdir(exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _ia(pipe, system, user, calidad=False, max_tokens=1500):
    """calidad=False: Ollama → Gemini → Haiku (gratis casi siempre).
    calidad=True (texto que verá un reclutador): Gemini → Claude de redacción."""
    if not calidad:
        return pipe._ia_barata(system, user, max_tokens=max_tokens) or {}
    from . import gemini
    if gemini.disponible():
        try:
            return gemini.ask_json(system, user)
        except Exception:
            pass
    return pipe.llm.ask_json(system, user, redaccion=True, max_tokens=max_tokens)


# ======================= 1) Banco de respuestas para formularios =======================
SYSTEM_FORMULARIO = """Eres un reclutador técnico que ayuda a un candidato a responder preguntas de formularios de
postulación. Escribes respuestas concretas, naturales y en primera persona, SOLO con datos reales del candidato
(su CV, sus respuestas confirmadas y respuestas que ya aprobó antes). Si un tema no aparece en sus datos, lo dices
con honestidad y puentes hacia lo que sí tiene; nunca inventas experiencia. Respondes SIEMPRE en JSON válido.""" + REGLA_NO_INVENTAR

PROMPT_FORMULARIO = """Pregunta del formulario: {pregunta}
{contexto}
=== CV ===
{cv}

=== RESPUESTAS CONFIRMADAS POR EL CANDIDATO ===
{hechos}

=== RESPUESTAS QUE YA APROBÓ ANTES PARA PREGUNTAS PARECIDAS (reutilízalas y adáptalas) ===
{previas}

Escribe la respuesta en el idioma de la pregunta, {largo}. Empieza por lo más fuerte y concreto (cifras reales si las hay).
Si piden algo que no tiene, dilo en una frase honesta y pasa a lo relacionado que sí tiene.
Devuelve SOLO este JSON: {{"respuesta": "", "datos_usados": [""], "temas_sin_evidencia": [""]}}"""


def banco():
    return _leer(BANCO, [])


def _tokens(s):
    return {w for w in re.findall(r"[a-záéíóúñ0-9#+.]{3,}", (s or "").lower())} - {
        "tell", "about", "your", "with", "what", "have", "the", "and", "you", "for", "how", "describe", "experience",
        "cuéntanos", "sobre", "tu", "experiencia", "que", "con", "los", "las", "una", "por"}


def parecidas(pregunta, n=3):
    """Respuestas guardadas con preguntas parecidas (por palabras en común, sin IA)."""
    t = _tokens(pregunta)
    out = []
    for r in banco():
        comun = len(t & _tokens(r["pregunta"]))
        if comun:
            out.append((comun / max(1, len(t)), r))
    return [r for _, r in sorted(out, key=lambda x: -x[0])[:n]]


def responder_formulario(pipe, pregunta, empresa="", puesto="", largo="80-150 palabras"):
    previas = parecidas(pregunta)
    ctx = f"Empresa/puesto: {empresa} — {puesto}\n" if (empresa or puesto) else ""
    data = _ia(pipe, SYSTEM_FORMULARIO, PROMPT_FORMULARIO.format(
        pregunta=pregunta, contexto=ctx, cv=pipe.cv[:6000], hechos=pipe.facts.as_text()[:6000],
        previas="\n\n".join(f"P: {r['pregunta']}\nR: {r['respuesta']}" for r in previas) or "(ninguna)",
        largo=largo), calidad=True, max_tokens=1500)
    return data, previas


def guardar_respuesta(pregunta, respuesta, empresa=""):
    b = banco()
    b = [r for r in b if r["pregunta"].strip().lower() != pregunta.strip().lower()]
    b.insert(0, {"pregunta": pregunta.strip(), "respuesta": respuesta.strip(), "empresa": empresa,
                 "fecha": date.today().isoformat()})
    _escribir(BANCO, b)


def borrar_respuesta(i):
    b = banco()
    if 0 <= i < len(b):
        b.pop(i)
        _escribir(BANCO, b)


# ======================= 3) Empresas favoritas =======================
def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def es_favorita(empresa, cfg):
    e = _norm(empresa)
    return bool(e) and any(_norm(f) and (_norm(f) in e or e in _norm(f)) for f in cfg.get("empresas_favoritas", []))


# ======================= 7) Frescura =======================
def dias_publicada(j):
    f = (j.get("fecha") or "")[:10]
    try:
        return (date.today() - date.fromisoformat(f)).days
    except Exception:
        return None


def orden_lista(j, cfg):
    """Favoritas primero dentro de su nivel, y las de más de 30 días bajan."""
    m = j.get("match_estimado") or 0
    d = dias_publicada(j)
    vieja = d is not None and d > int(cfg.get("dias_oferta_vieja", 30))
    return (not vieja, m // 10, es_favorita(j.get("empresa"), cfg), m)  # favorita gana dentro del mismo rango de 10


# ======================= 4) Simulador de entrevista =======================
SYSTEM_SIMULADOR = """Eres un entrevistador técnico senior. Evalúas la respuesta del candidato a una pregunta de
entrevista con honestidad y de forma útil: estructura (STAR), claridad, concreción, cifras y si responde lo que se
preguntó. Tu mejora propuesta usa SOLO datos que el candidato dijo o que están en su CV/respuestas confirmadas.
Respondes SIEMPRE en JSON válido en español.""" + REGLA_NO_INVENTAR

PROMPT_SIMULADOR = """Puesto: {puesto} en {empresa}
Pregunta: {pregunta}
Respuesta del candidato:
\"\"\"{respuesta}\"\"\"

Datos reales del candidato (para no inventar):
{hechos}

Devuelve SOLO este JSON:
{{"nota": 7, "bien": [""], "mejorar": [""], "respuesta_mejorada": "", "repregunta": ""}}
"nota" de 1 a 10. "repregunta" = la siguiente pregunta que haría un entrevistador real para profundizar."""


def evaluar_practica(pipe, puesto, empresa, pregunta, respuesta):
    data = _ia(pipe, SYSTEM_SIMULADOR, PROMPT_SIMULADOR.format(
        puesto=puesto, empresa=empresa, pregunta=pregunta, respuesta=respuesta[:4000],
        hechos=(pipe.cv[:3000] + "\n" + pipe.facts.as_text()[:4000])), calidad=False)
    hist = _leer(PRACTICA, [])
    hist.insert(0, {"fecha": datetime.now().isoformat(timespec="minutes"), "puesto": puesto, "empresa": empresa,
                    "pregunta": pregunta, "respuesta": respuesta, "nota": data.get("nota")})
    _escribir(PRACTICA, hist[:300])
    return data


def practicas():
    return _leer(PRACTICA, [])


# ======================= 6) Plan de estudio con progreso =======================
def plan():
    return _leer(PLAN, {})


def marcar_estudio(habilidad, estado, detalle, facts=None):
    """estado: 'pendiente' | 'en curso' | 'terminado'. Al terminar, se guarda como respuesta confirmada (así entra en
    tus próximos CVs y sube el match), con tu propio detalle: nada se inventa."""
    p = plan()
    p[habilidad] = {"estado": estado, "detalle": detalle, "fecha": date.today().isoformat()}
    _escribir(PLAN, p)
    if estado == "terminado" and facts is not None and detalle.strip():
        facts.add(habilidad, "si", detalle.strip(), "Plan de estudio")


# ======================= 2) Resumen diario por Outlook =======================
def resumen_pendiente_hoy():
    try:
        return DIGEST.read_text(encoding="utf-8").strip() != date.today().isoformat()
    except Exception:
        return True


def armar_resumen(ofertas, cfg, maximo=5):
    vieja = int(cfg.get("dias_oferta_vieja", 30))
    nuevas = [j for j in ofertas if j.get("nueva") and (dias_publicada(j) is None or dias_publicada(j) <= vieja)]
    minimo = int(cfg.get("resumen_diario", {}).get("match_minimo", 70))
    top = [j for j in nuevas if (j.get("match_estimado") or 0) >= minimo or es_favorita(j.get("empresa"), cfg)]
    top.sort(key=lambda j: (es_favorita(j.get("empresa"), cfg), j.get("match_estimado") or 0), reverse=True)
    return top[:maximo]


def html_resumen(top):
    filas = "".join(
        f"<tr><td style='padding:6px'><b>{j.get('match_estimado') or '—'}</b></td>"
        f"<td style='padding:6px'>{'⭐ ' if j.get('_fav') else ''}<a href='{j['url']}'>{j['puesto']}</a><br>"
        f"<small>{j.get('empresa', '')} · {j.get('ubicacion', '')} · {', '.join(j.get('areas') or [])}</small><br>"
        f"<small style='color:#555'>{j.get('motivo', '')}</small></td></tr>" for j in top)
    return (f"<p>Hola, estas son tus mejores ofertas nuevas de hoy ({date.today().isoformat()}):</p>"
            f"<table style='font-family:Segoe UI,Arial;font-size:14px;border-collapse:collapse'>{filas}</table>"
            "<p style='color:#777;font-size:12px'>Enviado por tu app CV Match. Ábrela para adaptar tu CV.</p>")


def enviar_resumen(cfg, ofertas, log=print, forzar=False):
    """Envía (a tu propio correo) el resumen de ofertas nuevas, una vez al día. Devuelve cuántas incluyó."""
    rd = cfg.get("resumen_diario") or {}
    if not rd.get("activado") and not forzar:
        return 0
    if not forzar and not resumen_pendiente_hoy():
        return 0
    top = armar_resumen(ofertas, cfg)
    for j in top:
        j["_fav"] = es_favorita(j.get("empresa"), cfg)
    if not top and not forzar:
        return 0
    from . import correo
    cid = (cfg.get("outlook") or {}).get("client_id", "")
    tok = correo.token_envio(cid)
    if not tok:
        raise RuntimeError("Outlook no tiene permiso de envío: en ⚙️ Configuración → Outlook pulsa "
                           "«Dar permiso para enviarme el resumen».")
    destino = correo.cuenta(cid)
    asunto = f"CV Match: {len(top)} ofertas nuevas para ti" if top else "CV Match: hoy no hubo ofertas nuevas que superen tu filtro"
    correo.enviar_a_mi(tok, destino, asunto, html_resumen(top) if top else "<p>Sin ofertas nuevas hoy.</p>")
    DIGEST.write_text(date.today().isoformat(), encoding="utf-8")
    log(f"  Resumen enviado a {destino} con {len(top)} ofertas")
    return len(top)

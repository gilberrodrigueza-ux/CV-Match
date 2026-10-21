"""Búsqueda web de ofertas en Costa Rica, por área, en orden jerárquico (se pasa al siguiente solo si el anterior falla):
1) Tavily (1000 búsquedas gratis al mes); los resultados los lee Ollama en tu PC, o Gemini sin búsqueda si
   Ollama está cerrado                                                               -> USD 0
2) Claude con búsqueda web (el más caro, último recurso)                            -> ~USD 0.026 por área
Gemini con búsqueda de Google NO se usa: en tu cuenta exige facturación (error 429).
"""
import json
import re
from datetime import date

import requests

from . import jobs
from .config import DATA_DIR
from .llm import extract_json, reparar_json

TAVILY_URL = "https://api.tavily.com/search"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
GEMINI_MODELOS_RESPALDO = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash-lite", "gemini-flash-latest",
                           "gemini-3.1-flash-lite"]  # primero los de capa gratuita
SITIOS_EMPLEO = ["linkedin.com", "glassdoor.com", "computrabajo.com", "indeed.com", "getonbrd.com", "torre.ai",
                 "tecoloco.co.cr", "elempleo.com", "myworkdayjobs.com", "greenhouse.io", "lever.co",
                 "smartrecruiters.com", "careers.ibm.com", "kyndryl.com", "jobs.careers.microsoft.com"]


class SinProveedor(RuntimeError):
    pass


# ---------------- claves ----------------
def _ruta_clave(nombre):
    return DATA_DIR / f"{nombre}_key.txt"


def get_key(nombre):
    p = _ruta_clave(nombre)
    if p.exists():
        return p.read_text(encoding="utf-8-sig").strip()
    return ""


def save_key(nombre, valor):
    DATA_DIR.mkdir(exist_ok=True)
    _ruta_clave(nombre).write_text((valor or "").strip() + "\n", encoding="utf-8")


def _registrar(proveedor, tarea, busquedas, usd=0.0):
    """Deja constancia en el medidor de gasto (aunque sea gratis) para que veas cuántas búsquedas usaste."""
    try:
        from . import gasto
        from datetime import datetime
        with open(gasto.ARCHIVO, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"), "modelo": proveedor, "tarea": tarea,
                                "usd": round(usd, 5), "entrada": 0, "salida": 0, "cache_lectura": 0,
                                "cache_escritura": 0, "web": busquedas}, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ---------------- 1) Tavily + Ollama ----------------
def consultas_area(area, n):
    """Consultas por área: títulos exactos entre comillas, en inglés y español, a páginas de vacantes individuales."""
    nom = area["nombre"]
    terms = area["terminos"] or [nom]
    en = next((t for t in terms if t.isascii() and " " in t), None) or next((t for t in terms if t.isascii()), terms[0])
    es = next((t for t in terms if not t.isascii() or re.search(r"arquitect|ingenier|soporte|técnico|infraestructura|migraci|nube", t)), None)
    base = [
        (f'"{en}" Costa Rica', SITIOS_EMPLEO),
        (f'"{en}" remote LATAM Costa Rica', None),
        ((f'"{es}" Costa Rica empleo' if es else f'"{nom}" Costa Rica job'), SITIOS_EMPLEO),
    ]
    return base[:max(1, n)]


RANGO_TIEMPO = ["month"]  # "week" en búsquedas frecuentes (lo fija buscar_area)


def tavily_buscar(clave, consulta, dominios=None, max_results=10):
    body = {"query": consulta, "search_depth": "basic", "max_results": max_results, "time_range": RANGO_TIEMPO[0],
            "topic": "general", "country": "costa rica"}
    if dominios:
        body["include_domains"] = dominios
    r = requests.post(TAVILY_URL, json=body, timeout=60, headers={"Authorization": f"Bearer {clave}"})
    if r.status_code != 200:
        raise RuntimeError(f"Tavily respondió {r.status_code}: {r.text[:200]}")
    return r.json().get("results", [])


SYSTEM_EXTRAER = """Eres un asistente que lee resultados de un buscador y extrae SOLO ofertas de empleo concretas.
Nunca inventas datos ni enlaces: solo usas los resultados que te dan. Respondes SIEMPRE en JSON válido."""

PROMPT_EXTRAER = """Área buscada: «{area}» (términos: {terminos}). Hoy es {hoy}.
El candidato vive en Costa Rica. Solo sirven puestos en Costa Rica o 100 % remotos que acepten Costa Rica/LATAM.

Resultados del buscador (cada uno con su número):
{resultados}

Tareas:
- Incluye SOLO resultados que sean UNA oferta de empleo concreta del área buscada (no listas con muchas ofertas,
  no artículos, no perfiles de personas, no cursos).
- Excluye las que digan claramente que son en otro país, presenciales fuera de Costa Rica o con relocation.
- Usa el número del resultado ("n"); no escribas enlaces.
- empresa y puesto tal como aparecen; si no aparece la empresa, deja "".
- resumen: 1-2 frases con requisitos que se vean en el texto (plataformas, años, certificaciones). No inventes.

Devuelve SOLO este JSON: {{"ofertas": [{{"n": 1, "empresa": "", "puesto": "", "ubicacion": "", "modalidad": "", "resumen": ""}}]}}"""


def _ollama_modelo(cfg):
    from . import ollama
    oc = cfg.get("ollama") or {}
    url = oc.get("url", "http://localhost:11434")
    ok, instalados = ollama.disponible(url)
    modelo = ollama.elegir_modelo(oc.get("modelo", ""), instalados) if ok else None
    return modelo, url


def buscar_tavily_ollama(cfg, area, n_busquedas, log, llm=None, consultas=None):
    clave = get_key("tavily")
    if not clave:
        raise SinProveedor("falta la clave de Tavily")
    modelo, url = _ollama_modelo(cfg)
    from . import gemini
    if not modelo and not gemini.disponible() and not llm:
        raise SinProveedor("Ollama no está abierto y Gemini no está disponible para leer los resultados")
    resultados, vistos = [], set()
    consultas = consultas or consultas_area(area, n_busquedas)
    for q, dominios in consultas:
        for r in tavily_buscar(clave, q, dominios):
            u = jobs.normalizar_link(r.get("url", ""))
            if u.startswith("http") and u not in vistos:
                vistos.add(u)
                resultados.append({"titulo": r.get("title", ""), "url": u, "texto": (r.get("content") or "")[:600],
                                   "fecha": (r.get("published_date") or "")[:10]})
    _registrar("tavily", f"Búsqueda web · {area['nombre']}", len(consultas))
    if not resultados:
        return []
    from . import ollama
    listado = "\n\n".join(f"[{i}] {x['titulo']}\n{x['url']}\n{x['texto']}" for i, x in enumerate(resultados))
    user = PROMPT_EXTRAER.format(area=area["nombre"], terminos=", ".join(area["terminos"]),
                                 hoy=date.today().isoformat(), resultados=listado)
    data = None
    if modelo:
        try:
            data = ollama.ask_json(SYSTEM_EXTRAER, user, modelo, url)
        except Exception as e:
            log(f"    Ollama no pudo leer los resultados ({e.__class__.__name__}); pruebo con Gemini")
    if data is None and gemini.disponible():
        try:
            data = gemini.ask_json(SYSTEM_EXTRAER, user)  # Gemini sin búsqueda: solo lee lo que trajo Tavily
        except Exception as e:
            log(f"    Gemini no pudo leer los resultados ({str(e)[:60]})")
    if data is None:
        if not llm:
            raise SinProveedor("ni Ollama ni Gemini pudieron leer los resultados de Tavily")
        from .config import modelo_tarea
        log("    Leo los resultados de Tavily con Claude Haiku (~USD 0.002, sin búsqueda pagada)")
        data = llm.ask_json(SYSTEM_EXTRAER, user, max_tokens=3000, modelo=modelo_tarea(cfg, "ranking"))
    ofertas = []
    for o in (data or {}).get("ofertas", []):
        try:
            i = int(o.get("n"))
        except (TypeError, ValueError):
            continue
        if 0 <= i < len(resultados):
            res = resultados[i]
            ofertas.append({**o, "url": res["url"], "sitio": _sitio(res["url"]),
                            "puesto": o.get("puesto") or res["titulo"],
                            "resumen": o.get("resumen") or res["texto"][:300], "fecha": res.get("fecha", "")})
    return ofertas


def _sitio(url):
    from urllib.parse import urlparse
    h = urlparse(url).netloc.lower().replace("www.", "")
    for s, nombre in (("linkedin", "LinkedIn"), ("glassdoor", "Glassdoor"), ("computrabajo", "Computrabajo"),
                      ("indeed", "Indeed"), ("getonbrd", "Get on Board"), ("torre", "Torre")):
        if s in h:
            return nombre
    return h


# ---------------- 2) Gemini con Google Search ----------------
def _resolver_redireccion(url):
    """Gemini entrega enlaces de redirección (vertexaisearch...); se siguen para obtener la página real."""
    if "grounding-api-redirect" not in url:
        return url
    try:
        r = requests.head(url, allow_redirects=False, timeout=15)
        return r.headers.get("Location") or url
    except Exception:
        return url


_MODELOS_CACHE = {}


def gemini_modelos_disponibles(clave):
    """Pide a Google la lista real de modelos de tu clave (los nombres cambian con el tiempo)."""
    if clave in _MODELOS_CACHE:
        return _MODELOS_CACHE[clave]
    nombres = []
    try:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", params={"pageSize": 200},
                         headers={"x-goog-api-key": clave}, timeout=30)
        if r.status_code == 200:
            for m in r.json().get("models", []):
                n = m.get("name", "").replace("models/", "")
                if "generateContent" in (m.get("supportedGenerationMethods") or []) and "flash" in n \
                        and not any(x in n for x in ("image", "tts", "audio", "live", "embedding", "thinking")):
                    nombres.append(n)
    except Exception:
        pass
    # primero los "lite" y estables (más cuota gratis), luego el resto
    nombres.sort(key=lambda n: (("preview" in n or "exp" in n), "lite" not in n, n))
    _MODELOS_CACHE[clave] = nombres
    return nombres


def _detalle_429(r):
    try:
        err = r.json().get("error", {})
        metr = [v.get("quotaMetric", "").split("/")[-1] + (f" (límite {v.get('quotaValue')})" if v.get("quotaValue") else "")
                for d in err.get("details", []) for v in d.get("violations", [])]
        return ", ".join(x for x in metr if x) or err.get("message", "")[:200]
    except Exception:
        return r.text[:200]


def gemini_generar(clave, prompt, modelo_pref):
    modelos = [m for m in [modelo_pref] + GEMINI_MODELOS_RESPALDO + gemini_modelos_disponibles(clave) if m]
    intentos, primer_429, modelo_429 = [], None, None
    for m in list(dict.fromkeys(modelos))[:10]:
        r = requests.post(GEMINI_URL.format(modelo=m), headers={"x-goog-api-key": clave}, timeout=120, json={
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0.2}})
        if r.status_code == 404:
            intentos.append(f"{m}: no existe")
            continue
        if r.status_code == 429:
            if primer_429 is None:
                primer_429, modelo_429 = _detalle_429(r), m
            intentos.append(f"{m}: sin cuota")
            continue
        if r.status_code != 200:
            raise RuntimeError(f"Gemini respondió {r.status_code}: {r.text[:200]}")
        cand = (r.json().get("candidates") or [{}])[0]
        texto = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
        chunks = [(c.get("web") or {}) for c in (cand.get("groundingMetadata") or {}).get("groundingChunks", [])]
        return texto, chunks, m
    msg = "; ".join(intentos) or "Gemini no respondió"
    if primer_429:
        msg += f". Cuota agotada: {primer_429}"
        # diagnóstico: ¿la clave tiene cuota sin la búsqueda de Google?
        try:
            r = requests.post(GEMINI_URL.format(modelo=modelo_429), headers={"x-goog-api-key": clave}, timeout=60,
                              json={"contents": [{"role": "user", "parts": [{"text": "Responde solo: ok"}]}]})
            if r.status_code == 200:
                msg += (". DIAGNÓSTICO: tu clave SÍ funciona, pero la búsqueda de Google (grounding) no tiene "
                        "cuota gratis en tu cuenta/proyecto")
            elif r.status_code == 429:
                msg += ". DIAGNÓSTICO: la clave no tiene cuota gratis ni sin búsqueda (proyecto con límite 0)"
        except Exception:
            pass
    raise RuntimeError(msg)


def buscar_gemini(cfg, area, cv_resumen, n_ofertas, log):
    clave = get_key("gemini")
    if not clave:
        raise SinProveedor("falta la clave de Gemini")
    from .prompts import PROMPT_BUSQUEDA_CR
    nb = int(cfg["busqueda"].get("busquedas_web_por_area", 2))
    prompt = PROMPT_BUSQUEDA_CR.format(hoy=date.today().isoformat(), perfil=cv_resumen, area=area["nombre"],
                                       keywords=", ".join(area["terminos"]), n=n_ofertas, busquedas=nb)
    prompt += ("\nNunca inventes enlaces: usa solo páginas que aparecieron en tus búsquedas de Google. "
               "Si no encontraste ofertas, devuelve {\"ofertas\": []}.")
    texto, chunks, modelo = gemini_generar(clave, prompt, (cfg.get("busqueda_web") or {}).get("gemini_modelo"))
    _registrar(f"gemini ({modelo})", f"Búsqueda web · {area['nombre']}", nb)
    data = extract_json(texto) if texto else {}
    if not data:
        data = reparar_json(texto) or {}
    # enlaces que Google realmente devolvió (para descartar links inventados)
    reales = {_resolver_redireccion(c.get("uri", "")) for c in chunks if c.get("uri")}
    dominios_reales = {re.sub(r"^www\.", "", u.split("/")[2]) for u in reales if u.count("/") >= 2}
    ofertas = []
    for o in (data or {}).get("ofertas", []):
        u = _resolver_redireccion(o.get("url", ""))
        if not u.startswith("http"):
            continue
        dom = re.sub(r"^www\.", "", u.split("/")[2]) if u.count("/") >= 2 else ""
        if reales and u not in reales and dom not in dominios_reales:
            continue  # el enlace no salió de la búsqueda: probablemente inventado
        o["url"] = u
        ofertas.append(o)
    return ofertas


# ---------------- 3) Claude (respaldo opcional) ----------------
def buscar_claude(llm, cfg, area, cv_resumen, n_ofertas):
    from .config import modelo_tarea
    from .prompts import PROMPT_BUSQUEDA_CR, SYSTEM_BUSCADOR
    nb = int(cfg["busqueda"].get("busquedas_web_por_area", 2))
    data = llm.ask_json(SYSTEM_BUSCADOR, PROMPT_BUSQUEDA_CR.format(
        hoy=date.today().isoformat(), perfil=cv_resumen, area=area["nombre"],
        keywords=", ".join(area["terminos"]), n=n_ofertas, busquedas=nb),
        max_tokens=5000, web=True, modelo=modelo_tarea(cfg, "busqueda_web"), max_busquedas=nb)
    return data.get("ofertas", [])


# ---------------- orquestador ----------------
def a_jobs(ofertas, area, cfg=None):
    out = []
    for o in ofertas:
        if not str(o.get("url", "")).startswith("http"):
            continue
        if cfg and jobs.titulo_excluido(o.get("puesto"), cfg):
            continue
        j = jobs._job(f"Web: {o['sitio']}" if o.get("sitio") else "Búsqueda web", o.get("empresa"), o.get("puesto"),
                      o.get("url"), o.get("ubicacion") or o.get("modalidad"), o.get("resumen"), _fecha_iso(o.get("fecha")))
        j["url"] = jobs.normalizar_link(j["url"])
        j["tipo_link"] = jobs.tipo_link(j["url"])
        loc = jobs.location_ok(f"{j['ubicacion']} {o.get('modalidad', '')}", ["remote", "remoto"], j["descripcion"])
        if loc is False:
            continue
        j["elegible_ubicacion"] = loc
        j["kw_score"] = 0
        j["areas"] = [area["nombre"]]
        out.append(j)
    return out


ORDEN = ["tavily", "claude"]
_GEMINI_SIN_CUOTA = [0.0]


def _fecha_iso(f):
    """Tavily da fechas tipo 'Mon, 13 Oct 2026 ...' o ISO; se guarda AAAA-MM-DD si se puede."""
    f = (f or "").strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", f):
        return f[:10]
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(f).date().isoformat()
    except Exception:
        return ""


def buscar_favoritas(cfg, llm, log, por_consulta=4):
    """Busca en tus empresas favoritas (Tavily, agrupadas de a 4 para gastar pocos créditos)."""
    favs = [f for f in cfg.get("empresas_favoritas", []) if f.strip()]
    if not favs:
        return []
    consultas = [(" OR ".join(f'"{x}"' for x in favs[i:i + por_consulta]) +
                  " cloud infrastructure job Costa Rica", None) for i in range(0, len(favs), por_consulta)]
    area = {"nombre": "Empresas favoritas", "terminos": [t for a in cfg["busqueda"].get("areas", []) for t in a["terminos"][:1]]}
    ofertas = buscar_tavily_ollama(cfg, area, len(consultas), log, llm, consultas=consultas)
    out = a_jobs(ofertas, area, cfg)
    from . import jobs as _j
    areas = _j.areas_config(cfg)
    for j in out:
        j["areas"] = _j.areas_de_oferta(j, areas) or ["Empresas favoritas"]
    return out


def buscar_area(cfg, llm, area, cv_resumen, log, n_ofertas=8):
    """Devuelve (ofertas, proveedor usado). Orden: Gemini → Tavily+Ollama → Claude (si está permitido)."""
    bw = cfg.get("busqueda_web") or {}
    nb = int(cfg["busqueda"].get("busquedas_web_por_area", 2))
    fallos, vacio = [], None
    for prov in [p for p in (bw.get("orden") or ORDEN) if p != "gemini"]:  # Gemini con búsqueda exige facturación
        try:
            if prov in ("gemini", "tavily"):
                if prov == "gemini":
                    import time
                    if time.time() - _GEMINI_SIN_CUOTA[0] < 900:  # ya falló por cuota hace poco: no repetir 7 intentos
                        fallos.append("gemini: sin cuota (se reintenta en 15 min)")
                        continue
                    try:
                        r = a_jobs(buscar_gemini(cfg, area, cv_resumen, n_ofertas, log), area, cfg)
                    except RuntimeError as e:
                        if "Cuota agotada" in str(e):
                            _GEMINI_SIN_CUOTA[0] = time.time()
                        raise
                    nombre = "Gemini (gratis)"
                else:
                    r, nombre = a_jobs(buscar_tavily_ollama(cfg, area, nb, log, llm), area, cfg), "Tavily (gratis)"
                if r:
                    return r, nombre
                vacio = nombre  # funcionó pero no trajo ofertas: se prueba el siguiente gratis, no Claude
                fallos.append(f"{prov}: 0 ofertas")
                continue
            if prov == "claude":
                if vacio:
                    return [], vacio + " · sin ofertas nuevas"
                if not bw.get("claude_respaldo", True):
                    fallos.append("Claude: desactivado")
                    continue
                if not llm:
                    fallos.append("Claude: falta la API key")
                    continue
                log(f"    {area['nombre']}: {'; '.join(fallos)} → uso Claude (~USD 0.026)")
                return a_jobs(buscar_claude(llm, cfg, area, cv_resumen, n_ofertas), area, cfg), "Claude (pagado)"
        except SinProveedor as e:
            fallos.append(f"{prov}: {e}")
        except Exception as e:
            if e.__class__.__name__ == "PresupuestoAgotado":
                raise
            fallos.append(f"{prov}: {e}")
    if vacio:
        return [], vacio + " · sin ofertas nuevas"
    raise SinProveedor("; ".join(fallos))

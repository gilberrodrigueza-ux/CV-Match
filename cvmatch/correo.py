"""Outlook vía Microsoft Graph (solo lectura): detecta respuestas de empresas a las que aplicaste
y sugiere cambios de estado. Nunca cambia nada sin tu confirmación."""
import json
import re
from datetime import datetime, timedelta, timezone

import requests

from . import history
from .config import DATA_DIR

AUTHORITY = "https://login.microsoftonline.com/consumers"   # cuentas personales (outlook.com / hotmail)
SCOPES = ["Mail.Read"]
SCOPES_ENVIO = ["Mail.Send"]  # solo para enviarte a ti mismo el resumen diario
CACHE = DATA_DIR / "outlook_token.bin"
SUGERENCIAS = DATA_DIR / "sugerencias_correo.json"
PROCESADOS = DATA_DIR / "correos_procesados.json"
GRAPH = "https://graph.microsoft.com/v1.0"

ESTADO_POR_CATEGORIA = {"acuse_recibo": "Aplicado", "entrevista": "Entrevista", "prueba_tecnica": "Prueba técnica",
                        "oferta": "Oferta", "rechazo": "Rechazado"}
ESTADOS_ABIERTOS = {"Por aplicar", "Aplicado", "Entrevista", "Prueba técnica"}


# ---------------- autenticación ----------------
def _app(client_id):
    import msal
    cache = msal.SerializableTokenCache()
    if CACHE.exists():
        cache.deserialize(CACHE.read_text(encoding="utf-8"))
    return msal.PublicClientApplication(client_id, authority=AUTHORITY, token_cache=cache), cache


def _guardar(cache):
    if cache.has_state_changed:
        CACHE.write_text(cache.serialize(), encoding="utf-8")


def iniciar_conexion(client_id, con_envio=False):
    """Paso 1: devuelve el código y la URL para iniciar sesión en el navegador."""
    app, _ = _app(client_id)
    flow = app.initiate_device_flow(scopes=SCOPES + (SCOPES_ENVIO if con_envio else []))
    if "user_code" not in flow:
        raise RuntimeError(flow.get("error_description") or "No se pudo iniciar la conexión con Microsoft")
    return flow


def completar_conexion(client_id, flow):
    """Paso 2: espera a que inicies sesión (hasta ~15 min) y guarda el token localmente."""
    app, cache = _app(client_id)
    r = app.acquire_token_by_device_flow(flow)
    _guardar(cache)
    if "access_token" not in r:
        raise RuntimeError(r.get("error_description") or "No se completó el inicio de sesión")
    return (r.get("id_token_claims") or {}).get("preferred_username", "")


def token(client_id):
    """Token sin interacción (renovación automática). None si hay que conectar de nuevo."""
    if not client_id or not CACHE.exists():
        return None
    app, cache = _app(client_id)
    cuentas = app.get_accounts()
    if not cuentas:
        return None
    r = app.acquire_token_silent(SCOPES, account=cuentas[0])
    _guardar(cache)
    return r.get("access_token") if r else None


def token_envio(client_id):
    """Token con permiso de envío (Mail.Send). None si aún no diste ese permiso."""
    if not client_id or not CACHE.exists():
        return None
    app, cache = _app(client_id)
    cuentas = app.get_accounts()
    if not cuentas:
        return None
    r = app.acquire_token_silent(SCOPES_ENVIO, account=cuentas[0])
    _guardar(cache)
    return r.get("access_token") if r else None


def enviar_a_mi(tok, destino, asunto, html):
    """Envía un correo SOLO a tu propia dirección (el resumen diario)."""
    r = requests.post(f"{GRAPH}/me/sendMail", headers={"Authorization": f"Bearer {tok}"}, timeout=30, json={
        "message": {"subject": asunto, "body": {"contentType": "HTML", "content": html},
                    "toRecipients": [{"emailAddress": {"address": destino}}]},
        "saveToSentItems": False})
    if r.status_code not in (200, 202):
        raise RuntimeError(f"Outlook no envió el resumen ({r.status_code}): {r.text[:200]}")


def cuenta(client_id):
    if not client_id or not CACHE.exists():
        return None
    app, _ = _app(client_id)
    c = app.get_accounts()
    return c[0].get("username") if c else None


def desconectar():
    CACHE.unlink(missing_ok=True)


# ---------------- lectura ----------------
def leer_correos(tok, dias=14, maximo=300):
    desde = (datetime.now(timezone.utc) - timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    for carpeta in ("inbox", "junkemail"):
        url = (f"{GRAPH}/me/mailFolders/{carpeta}/messages?$filter=receivedDateTime ge {desde}"
               "&$select=id,subject,from,receivedDateTime,bodyPreview,webLink&$orderby=receivedDateTime desc&$top=50")
        while url and len(out) < maximo:
            r = requests.get(url, headers={"Authorization": f"Bearer {tok}"}, timeout=30)
            r.raise_for_status()
            d = r.json()
            for m in d.get("value", []):
                m["_carpeta"] = carpeta
                out.append(m)
            url = d.get("@odata.nextLink")
    return out


# ---------------- coincidencia con el historial ----------------
def _tokens(s):
    s = history._norm(s)
    return [t for t in s.split() if len(t) > 2 and t not in {"group", "global", "services", "solutions", "technologies",
                                                             "technology", "consulting", "latam", "america", "systems"}]


def _empresa_en(texto, empresa):
    """La empresa aparece en el texto (todas sus palabras significativas, o la principal si es distintiva)."""
    t = " " + history._norm(texto) + " "
    toks = _tokens(empresa)
    if not toks:
        return False
    if all(f" {k} " in t for k in toks):
        return True
    return len(toks[0]) >= 5 and f" {toks[0]} " in t


def coincidencias(mensajes, filas):
    out = []
    abiertas = [r for r in filas if r["estado"] in ESTADOS_ABIERTOS]
    for m in mensajes:
        de = (m.get("from") or {}).get("emailAddress") or {}
        dominio = (de.get("address") or "").split("@")[-1].lower()
        texto = f"{de.get('name', '')} {dominio.replace('.', ' ')} {m.get('subject', '')} {m.get('bodyPreview', '')[:600]}"
        mejor = None
        for r in abiertas:
            if _empresa_en(texto, r["empresa"]):
                puntos = 2 + sum(1 for k in _tokens(r["puesto"]) if f" {k} " in " " + history._norm(texto) + " ")
                if not mejor or puntos > mejor[0]:
                    mejor = (puntos, r)
        if mejor:
            out.append({"mensaje": m, "fila": mejor[1]})
    return out


# ---------------- clasificación ----------------
PROMPT = """Clasifica este correo recibido por un candidato que aplicó al puesto "{puesto}" en {empresa}.
De: {de}
Asunto: {asunto}
Extracto: {extracto}

Categorías: acuse_recibo (confirmaron que recibieron la aplicación), entrevista (invitan o agendan entrevista/llamada),
prueba_tecnica (assessment, prueba, test, ejercicio), oferta (oferta laboral), rechazo (no continúan),
otro (no relacionado o informativo).
Devuelve SOLO este JSON: {{"categoria": "", "resumen": "una línea en español"}}"""

PALABRAS = [("oferta", r"\boffer letter\b|\bjob offer\b|oferta (laboral|de empleo)|pleased to offer"),
            ("rechazo", r"unfortunately|not (to )?(move|moving) forward|other candidates|no continuar|lamentamos|"
                        r"decided to pursue|will not be|no ha sido seleccionad|position has been filled"),
            ("prueba_tecnica", r"assessment|coding (test|challenge)|technical (test|exercise)|hackerrank|codility|"
                               r"prueba t[eé]cnica|take[- ]home"),
            ("entrevista", r"interview|entrevista|schedule (a|your) (call|time)|availability|disponibilidad|"
                           r"calendly|phone screen|llamada"),
            ("acuse_recibo", r"received your application|thank you for (applying|your application)|"
                             r"hemos recibido|gracias por (aplicar|postular)|application (has been )?received")]


def _por_palabras(texto):
    t = texto.lower()
    for cat, rx in PALABRAS:
        if re.search(rx, t):
            return cat
    return "otro"


def clasificar(pipe, m, fila):
    de = (m.get("from") or {}).get("emailAddress") or {}
    user = PROMPT.format(puesto=fila["puesto"], empresa=fila["empresa"], de=f"{de.get('name', '')} <{de.get('address', '')}>",
                         asunto=m.get("subject", ""), extracto=(m.get("bodyPreview") or "")[:900])
    sistema = "Clasificas correos de procesos de selección. Respondes SIEMPRE en JSON válido."
    oc = pipe.cfg.get("ollama") or {}
    if oc.get("usar_para_evaluar_ofertas"):
        try:
            from . import ollama
            ok, inst = ollama.disponible(oc.get("url", "http://localhost:11434"))
            mod = ollama.elegir_modelo(oc.get("modelo", ""), inst) if ok else None
            if mod:
                d = ollama.ask_json(sistema, user, mod, oc.get("url", "http://localhost:11434"), timeout=180)
                if d.get("categoria") in list(ESTADO_POR_CATEGORIA) + ["otro"]:
                    return d
        except Exception:
            pass
    if pipe.llm:
        try:
            from .config import modelo_tarea
            d = pipe.llm.ask_json(sistema, user, max_tokens=300, modelo=modelo_tarea(pipe.cfg, "seguimiento"))
            if d.get("categoria"):
                return d
        except Exception:
            pass
    return {"categoria": _por_palabras(f"{m.get('subject', '')} {m.get('bodyPreview', '')}"), "resumen": m.get("subject", "")}


# ---------------- flujo ----------------
def _cargar(path, defecto):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return defecto


def revisar(pipe, log=print):
    """Lee el correo, cruza con el historial y guarda sugerencias nuevas. Devuelve la lista de sugerencias pendientes."""
    oc = pipe.cfg.get("outlook") or {}
    tok = token(oc.get("client_id", ""))
    if not tok:
        raise RuntimeError("Outlook no está conectado (⚙️ Configuración → Outlook → Conectar)")
    procesados = set(_cargar(PROCESADOS, []))
    pendientes = _cargar(SUGERENCIAS, [])
    ya = {s["msg_id"] for s in pendientes} | procesados
    mensajes = [m for m in leer_correos(tok, int(oc.get("dias_revisar", 14))) if m["id"] not in ya]
    log(f"Correos nuevos revisados: {len(mensajes)}")
    filas = history.all_rows()
    nuevas = 0
    for c in coincidencias(mensajes, filas):
        m, fila = c["mensaje"], c["fila"]
        cl = clasificar(pipe, m, fila)
        cat = cl.get("categoria", "otro")
        destino = ESTADO_POR_CATEGORIA.get(cat)
        if not destino or destino == fila["estado"] or (cat == "acuse_recibo" and fila["estado"] != "Por aplicar"):
            procesados.add(m["id"])
            continue
        de = (m.get("from") or {}).get("emailAddress") or {}
        pendientes.append({"msg_id": m["id"], "id_solicitud": fila["id"], "empresa": fila["empresa"],
                           "puesto": fila["puesto"], "estado_actual": fila["estado"], "estado_sugerido": destino,
                           "categoria": cat, "resumen": cl.get("resumen", ""), "asunto": m.get("subject", ""),
                           "de": de.get("address", ""), "fecha": (m.get("receivedDateTime") or "")[:10],
                           "link": m.get("webLink", ""), "carpeta": m.get("_carpeta", "")})
        nuevas += 1
    en_pendientes = {x["msg_id"] for x in pendientes}
    procesados |= {m["id"] for m in mensajes if m["id"] not in en_pendientes}  # no volver a leer los ajenos
    SUGERENCIAS.write_text(json.dumps(pendientes, indent=2, ensure_ascii=False), encoding="utf-8")
    PROCESADOS.write_text(json.dumps(sorted(procesados)[-5000:], ensure_ascii=False), encoding="utf-8")
    log(f"Sugerencias nuevas: {nuevas}")
    return pendientes


def sugerencias():
    return _cargar(SUGERENCIAS, [])


def resolver(msg_id, aceptar):
    """Aplica (o descarta) una sugerencia."""
    pend = sugerencias()
    s = next((x for x in pend if x["msg_id"] == msg_id), None)
    if not s:
        return
    if aceptar:
        fila = next((r for r in history.all_rows() if r["id"] == s["id_solicitud"]), None)
        notas = ((fila or {}).get("notas") or "")
        nota = f"Correo {s['fecha']}: {s['asunto'][:80]}"
        history.update(s["id_solicitud"], estado=s["estado_sugerido"], notas=(f"{notas} | {nota}" if notas else nota))
    pend = [x for x in pend if x["msg_id"] != msg_id]
    SUGERENCIAS.write_text(json.dumps(pend, indent=2, ensure_ascii=False), encoding="utf-8")
    procesados = set(_cargar(PROCESADOS, []))
    procesados.add(msg_id)
    PROCESADOS.write_text(json.dumps(sorted(procesados)[-5000:], ensure_ascii=False), encoding="utf-8")

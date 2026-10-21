"""Medidor de gasto real de la API (con lo que reporta cada respuesta) y tope mensual."""
import json
from collections import defaultdict
from datetime import datetime

from .config import DATA_DIR

ARCHIVO = DATA_DIR / "gasto.jsonl"

# USD por millón de tokens (entrada, salida). Haiku cambia de precio si el prompt supera 100k tokens.
PRECIOS = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-haiku-5-5>100k": (0.50, 2.50),
}
WEB_SEARCH_USD = 10.0 / 1000  # por búsqueda
CACHE_LECTURA = 0.1
CACHE_ESCRITURA = 1.25


class PresupuestoAgotado(RuntimeError):
    pass


def etiqueta(system):
    from . import prompts as P
    mapa = [(P.SYSTEM_BUSCADOR, "Búsqueda web Costa Rica"), (P.SYSTEM_RANKER, "Evaluar ofertas"),
            (P.SYSTEM_RECLUTADOR, "Análisis reclutador"), (P.SYSTEM_EMPRESA, "Investigar empresa"),
            (P.SYSTEM_REDACTOR, "Reescritura XYZ"), (P.SYSTEM_ESCANER, "ATS + 100 CVs"),
            (P.SYSTEM_VERIFICADOR, "Auditoría"), (P.SYSTEM_PULIDO, "Pulido de estilo"),
            (P.SYSTEM_ENTREVISTA, "Entrevista"), (P.SYSTEM_METRICAS, "Banco de métricas"),
            (P.SYSTEM_COVER, "Cover letter"), (P.SYSTEM_SEGUIMIENTO, "Seguimiento / correo"),
            (P.SYSTEM_SKILLS, "Top 5 habilidades"),
            (P.SYSTEM_COINCIDENCIAS, "Usar respuestas previas"),
            (P.SYSTEM_REFRASEO, "Refrasear respuesta")]
    for s, nombre in mapa:
        if system == s:
            return nombre
    return "Otros"


def costo(model, usage):
    """Calcula el costo de una respuesta a partir de su objeto usage."""
    entrada = getattr(usage, "input_tokens", 0) or 0
    salida = getattr(usage, "output_tokens", 0) or 0
    c_lect = getattr(usage, "cache_read_input_tokens", 0) or 0
    c_escr = getattr(usage, "cache_creation_input_tokens", 0) or 0
    web = 0
    stu = getattr(usage, "server_tool_use", None)
    if stu is not None:
        web = getattr(stu, "web_search_requests", 0) or 0
    clave = model
    if model.startswith("claude-haiku-5-5") and (entrada + c_lect + c_escr) > 100_000:
        clave = "claude-haiku-5-5>100k"
    pin, pout = PRECIOS.get(clave, (4.0, 20.0))  # modelo desconocido: se asume el más caro
    usd = (entrada * pin + c_lect * pin * CACHE_LECTURA + c_escr * pin * CACHE_ESCRITURA + salida * pout) / 1e6
    usd += web * WEB_SEARCH_USD
    return usd, {"entrada": entrada, "salida": salida, "cache_lectura": c_lect, "cache_escritura": c_escr, "web": web}


def registrar(model, usage, tarea):
    usd, det = costo(model, usage)
    DATA_DIR.mkdir(exist_ok=True)
    with open(ARCHIVO, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"), "modelo": model, "tarea": tarea,
                            "usd": round(usd, 5), **det}, ensure_ascii=False) + "\n")
    return usd


def registros():
    out = []
    if ARCHIVO.exists():
        for line in ARCHIVO.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def total(prefijo_fecha):
    return sum(r["usd"] for r in registros() if r["ts"].startswith(prefijo_fecha))


def total_mes():
    return total(datetime.now().strftime("%Y-%m"))


def total_hoy():
    return total(datetime.now().strftime("%Y-%m-%d"))


def por_tarea(prefijo_fecha=None):
    pref = prefijo_fecha or datetime.now().strftime("%Y-%m")
    acc = defaultdict(lambda: {"usd": 0.0, "llamadas": 0, "busquedas_web": 0})
    for r in registros():
        if r["ts"].startswith(pref):
            a = acc[r["tarea"]]
            a["usd"] += r["usd"]
            a["llamadas"] += 1
            a["busquedas_web"] += r.get("web", 0)
    return dict(acc)


def verificar_presupuesto(cfg):
    tope = float(cfg.get("presupuesto_mensual_usd") or 0)
    if tope > 0:
        gastado = total_mes()
        if gastado >= tope:
            raise PresupuestoAgotado(
                f"Llegaste a tu presupuesto mensual (USD {gastado:.2f} de {tope:.2f}). "
                "Súbelo en ⚙️ Configuración → Presupuesto si quieres seguir este mes.")

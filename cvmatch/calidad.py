"""Calidad de la búsqueda: ofertas descartadas ("No me interesa") y aprendizaje de tus elecciones, verificación de
vigencia (ofertas cerradas) y rendimiento por fuente y área (las fuentes que nunca aportan se apagan solas)."""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

import requests

from .config import DATA_DIR

DESCARTADAS = DATA_DIR / "descartadas.json"
RENDIMIENTO = DATA_DIR / "rendimiento.json"
VIGENCIA = DATA_DIR / "vigencia.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


def _leer(p, d):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return d


def _escribir(p, data):
    DATA_DIR.mkdir(exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ======================= 2) No me interesa + aprendizaje =======================
def descartadas():
    return _leer(DESCARTADAS, [])


def descartar(ofertas, motivo=""):
    from .history import clave
    d = descartadas()
    ya = {x["url"] for x in d}
    for j in ofertas:
        if j["url"] not in ya:
            d.insert(0, {"url": j["url"], "clave": clave(j.get("empresa"), j.get("puesto")), "empresa": j.get("empresa", ""),
                         "puesto": j.get("puesto", ""), "areas": j.get("areas") or [], "motivo": motivo,
                         "fecha": date.today().isoformat()})
    _escribir(DESCARTADAS, d[:2000])


def restaurar(url):
    _escribir(DESCARTADAS, [x for x in descartadas() if x["url"] != url])


def es_descartada(j, _cache={}):
    from .history import clave
    d = descartadas()
    urls = {x["url"] for x in d}
    claves = {x.get("clave") for x in d if x.get("clave")}
    return j.get("url") in urls or clave(j.get("empresa"), j.get("puesto")) in claves  # también si la republican


def preferencias_texto(maximo=8):
    """Ejemplos de lo que te interesó (cola / CVs generados) y lo que descartaste, para el filtro rápido."""
    from . import history
    les = []
    for r in history.all_rows()[:maximo]:
        les.append(f"- {r.get('puesto', '')} ({r.get('empresa', '')})")
    try:
        cola = json.loads((DATA_DIR / "cola.json").read_text(encoding="utf-8"))
        for j in cola[:maximo]:
            les.append(f"- {j.get('puesto', '')} ({j.get('empresa', '')})")
    except Exception:
        pass
    no = [f"- {x['puesto']} ({x['empresa']})" + (f": {x['motivo']}" if x.get("motivo") else "") for x in descartadas()[:maximo]]
    if not les and not no:
        return "(todavía no hay ejemplos)"
    return ("LE INTERESARON (súbelas si se parecen):\n" + ("\n".join(dict.fromkeys(les)) or "-") +
            "\nDESCARTÓ (baja las que se parezcan):\n" + ("\n".join(no) or "-"))


# ======================= 3) Vigencia =======================
CERRADA = re.compile(
    r"no longer accepting applications|no longer available|position (has been )?(closed|filled)|job (is )?(closed|expired)|"
    r"this job (has )?expired|posting (has )?(closed|expired)|vacante (ya )?(no está disponible|cerrada)|"
    r"oferta (ya )?(no está disponible|ha expirado|cerrada)|ya no (acepta|recibe) (solicitudes|postulaciones)|"
    r"the page you are looking for (doesn't|does not) exist|job not found", re.I)


def esta_cerrada(url):
    """True = cerrada, False = abierta, None = no se pudo saber (se deja pasar)."""
    try:
        r = requests.get(url, headers=UA, timeout=12, allow_redirects=True)
        if r.status_code in (404, 410):
            return True
        if r.status_code >= 400:
            return None
        return bool(CERRADA.search(r.text[:300000]))
    except Exception:
        return None


def verificar_vigencia(ofertas, log=print, maximo=60, dias_cache=2):
    """Revisa los links (en paralelo, gratis) y marca j['cerrada']. Recuerda el resultado 2 días."""
    cache = _leer(VIGENCIA, {})
    hoy = date.today()
    pend = []
    for j in ofertas:
        c = cache.get(j["url"])
        if c and (hoy - date.fromisoformat(c["fecha"])).days < dias_cache:
            j["cerrada"] = c["cerrada"]
        elif j.get("tipo_link") != "lista":
            pend.append(j)
    pend = pend[:maximo]
    with ThreadPoolExecutor(max_workers=8) as ex:
        for j, cerr in zip(pend, ex.map(lambda x: esta_cerrada(x["url"]), pend)):
            j["cerrada"] = cerr
            cache[j["url"]] = {"cerrada": cerr, "fecha": hoy.isoformat()}
    _escribir(VIGENCIA, {k: v for k, v in cache.items() if (hoy - date.fromisoformat(v["fecha"])).days < 15})
    n = sum(1 for j in ofertas if j.get("cerrada") is True)
    if pend or n:
        log(f"  Vigencia: revisé {len(pend)} links · {n} ofertas cerradas se ocultan")
    return n


# ======================= 6) Rendimiento por fuente y área =======================
def _fuente_base(f):
    f = (f or "").replace("Web: ", "")
    return "Portales de empresas" if f.startswith("Portal:") else ("Búsqueda web" if "Web" in (f or "") or "." in f or " " in f else f)


def _grupo_fuente(f):
    f = f or ""
    if f.startswith("Portal:"):
        return "Portales de empresas"
    if f.startswith("Web") or f.startswith("Búsqueda web"):
        return "Búsqueda web"
    return f


def registrar_rendimiento(evaluadas, util=70):
    """Guarda, por búsqueda, cuántas ofertas aportó cada fuente y cada área y cuántas fueron útiles (match ≥ 70)."""
    if not evaluadas:
        return
    d = _leer(RENDIMIENTO, {"busquedas": []})
    fila = {"fecha": datetime.now().isoformat(timespec="minutes"), "fuentes": {}, "areas": {}}
    for j in evaluadas:
        ok = int((j.get("match_estimado") or 0) >= util)
        for grupo, claves in (("fuentes", [_grupo_fuente(j.get("fuente"))]), ("areas", j.get("areas") or [])):
            for k in claves:
                g = fila[grupo].setdefault(k, [0, 0])
                g[0] += 1
                g[1] += ok
    d["busquedas"] = ([fila] + d["busquedas"])[:20]
    _escribir(RENDIMIENTO, d)


def resumen_rendimiento(n=10):
    d = _leer(RENDIMIENTO, {"busquedas": []})["busquedas"][:n]
    tot = {"fuentes": {}, "areas": {}}
    for b in d:
        for grupo in ("fuentes", "areas"):
            for k, (a, u) in b.get(grupo, {}).items():
                t = tot[grupo].setdefault(k, [0, 0])
                t[0] += a
                t[1] += u
    return tot, len(d)


NOMBRES_BOLSA = {"Remotive": "remotive", "RemoteOK": "remoteok", "Himalayas": "himalayas", "Jobicy": "jobicy",
                 "We Work Remotely": "weworkremotely", "Working Nomads": "workingnomads"}


def bolsas_sin_rendimiento(minimo_ofertas=15, busquedas=5):
    """Bolsas que en las últimas búsquedas aportaron muchas ofertas pero ninguna útil: se saltan."""
    tot, n = resumen_rendimiento(busquedas)
    if n < 3:
        return []
    return [NOMBRES_BOLSA[k] for k, (a, u) in tot["fuentes"].items()
            if k in NOMBRES_BOLSA and a >= minimo_ofertas and u == 0]

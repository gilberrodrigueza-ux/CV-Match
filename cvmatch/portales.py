"""Portales de empleo de empresas (sin IA y sin créditos): Workday, Greenhouse, Lever, SmartRecruiters y Ashby.
Se lee la lista pública de vacantes de cada portal y se queda solo con lo de Costa Rica / remoto LATAM y tus áreas.
Los portales se agregan pegando la URL de la página de empleos de la empresa, o se descubren solos cuando una oferta
de tus búsquedas viene de uno de estos sistemas."""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from urllib.parse import urlparse

import requests

from .config import DATA_DIR

ARCHIVO = DATA_DIR / "portales.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CVMatch/1.0", "Accept": "application/json"}
# verificados: ServiceNow publica sus vacantes de Costa Rica en SmartRecruiters
POR_DEFECTO = [{"empresa": "ServiceNow", "url": "https://careers.smartrecruiters.com/ServiceNow", "origen": "incluido"}]


# ---------------- detección del tipo de portal ----------------
def detectar(url):
    """Devuelve (tipo, datos) o (None, None) si la URL no es de un portal conocido."""
    u = (url or "").strip()
    p = urlparse(u if "://" in u else "https://" + u)
    host, partes = p.netloc.lower(), [x for x in p.path.split("/") if x]
    if "myworkdayjobs.com" in host:
        partes = [x for x in partes if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", x)]
        if partes:
            return "workday", {"host": host, "tenant": host.split(".")[0], "site": partes[0]}
    if "greenhouse.io" in host and partes:
        tok = partes[0] if partes[0] not in ("embed", "v1") else (p.query.split("for=")[-1].split("&")[0] if "for=" in p.query else "")
        if tok:
            return "greenhouse", {"token": tok}
    if host.endswith("lever.co") and partes:
        return "lever", {"empresa": partes[0]}
    if "smartrecruiters.com" in host and partes:
        return "smartrecruiters", {"empresa": partes[0]}
    if "ashbyhq.com" in host and partes:
        return "ashby", {"org": partes[0]}
    return None, None


def lista():
    try:
        d = json.loads(ARCHIVO.read_text(encoding="utf-8"))
        return d if isinstance(d, list) else list(POR_DEFECTO)
    except Exception:
        return list(POR_DEFECTO)


def guardar(portales):
    DATA_DIR.mkdir(exist_ok=True)
    ARCHIVO.write_text(json.dumps(portales, indent=2, ensure_ascii=False), encoding="utf-8")


def agregar(empresa, url, origen="manual"):
    tipo, _ = detectar(url)
    if not tipo:
        return False
    ps = lista()
    if any(detectar(x["url"]) == detectar(url) for x in ps):
        return False
    ps.append({"empresa": empresa or "", "url": url, "origen": origen})
    guardar(ps)
    return True


def descubrir(ofertas, cfg, minimo=70):
    """Si una oferta buena (o de una empresa favorita) viene de Workday/Greenhouse/Lever/SmartRecruiters/Ashby,
    se agrega ese portal para revisarlo directo en las próximas búsquedas."""
    from .extras import es_favorita
    nuevos = []
    for j in ofertas:
        if (j.get("match_estimado") or 0) >= minimo or es_favorita(j.get("empresa"), cfg):
            for u in [j.get("url", "")] + [o.get("url", "") for o in j.get("otras_fuentes", [])]:
                tipo, d = detectar(u)
                if tipo:
                    base = _url_base(tipo, d)
                    if agregar(j.get("empresa", ""), base, "descubierto"):
                        nuevos.append(f"{j.get('empresa', '')} ({tipo})")
    return nuevos


def _url_base(tipo, d):
    return {"workday": lambda: f"https://{d['host']}/{d['site']}",
            "greenhouse": lambda: f"https://boards.greenhouse.io/{d['token']}",
            "lever": lambda: f"https://jobs.lever.co/{d['empresa']}",
            "smartrecruiters": lambda: f"https://careers.smartrecruiters.com/{d['empresa']}",
            "ashby": lambda: f"https://jobs.ashbyhq.com/{d['org']}"}[tipo]()


# ---------------- lectores por tipo ----------------
def _limpiar(html):
    from .jobs import _clean
    return _clean(html)


def _workday(d, consultas):
    base = f"https://{d['host']}/wday/cxs/{d['tenant']}/{d['site']}"
    out, vistos = [], set()
    for q in consultas:
        r = requests.post(f"{base}/jobs", headers={**UA, "Content-Type": "application/json"}, timeout=30,
                          json={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": q})
        r.raise_for_status()
        for jp in r.json().get("jobPostings", []):
            ep = jp.get("externalPath", "")
            if not ep or ep in vistos:
                continue
            vistos.add(ep)
            out.append({"puesto": jp.get("title", ""), "url": f"https://{d['host']}/{d['site']}{ep}",
                        "ubicacion": jp.get("locationsText", ""), "fecha": _fecha_workday(jp.get("postedOn", "")),
                        "_detalle": f"{base}{ep}"})
    return out


def _fecha_workday(txt):
    """'Posted Today' / 'Posted 3 Days Ago' / 'Posted 30+ Days Ago' → AAAA-MM-DD aproximada."""
    t = (txt or "").lower()
    from datetime import timedelta
    if "today" in t or "hoy" in t:
        return date.today().isoformat()
    if "yesterday" in t or "ayer" in t:
        return (date.today() - timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\+?\s*(day|día)", t)
    return (date.today() - timedelta(days=int(m.group(1)))).isoformat() if m else ""


def _detalle_workday(url):
    try:
        r = requests.get(url, headers=UA, timeout=30)
        info = r.json().get("jobPostingInfo", {})
        return _limpiar(info.get("jobDescription", "")), (info.get("startDate") or "")[:10]
    except Exception:
        return "", ""


def _greenhouse(d, consultas):
    r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{d['token']}/jobs", params={"content": "true"},
                     headers=UA, timeout=30)
    r.raise_for_status()
    import html as _h
    return [{"puesto": j.get("title", ""), "url": j.get("absolute_url", ""), "ubicacion": (j.get("location") or {}).get("name", ""),
             "fecha": (j.get("updated_at") or "")[:10], "descripcion": _limpiar(_h.unescape(j.get("content", "")))}
            for j in r.json().get("jobs", [])]


def _lever(d, consultas):
    r = requests.get(f"https://api.lever.co/v0/postings/{d['empresa']}", params={"mode": "json"}, headers=UA, timeout=30)
    r.raise_for_status()
    out = []
    for j in r.json():
        ts = j.get("createdAt")
        f = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date().isoformat() if ts else ""
        cat = j.get("categories") or {}
        out.append({"puesto": j.get("text", ""), "url": j.get("hostedUrl", ""),
                    "ubicacion": " / ".join(filter(None, [cat.get("location", ""), j.get("workplaceType", "")])),
                    "fecha": f, "descripcion": (j.get("descriptionPlain") or "")[:8000]})
    return out


def _smartrecruiters(d, consultas):
    out = []
    for params in ({"country": "cr", "limit": 100}, {"q": "remote", "limit": 100}):
        r = requests.get(f"https://api.smartrecruiters.com/v1/companies/{d['empresa']}/postings", params=params,
                         headers=UA, timeout=30)
        r.raise_for_status()
        for j in r.json().get("content", []):
            loc = j.get("location") or {}
            out.append({"puesto": j.get("name", ""),
                        "url": f"https://jobs.smartrecruiters.com/{d['empresa']}/{j.get('id')}",
                        "ubicacion": ", ".join(filter(None, [loc.get("city"), loc.get("country", "").upper(),
                                                             "Remote" if loc.get("remote") else ""])),
                        "fecha": (j.get("releasedDate") or "")[:10],
                        "_detalle": f"https://api.smartrecruiters.com/v1/companies/{d['empresa']}/postings/{j.get('id')}"})
    return out


def _detalle_smart(url):
    try:
        r = requests.get(url, headers=UA, timeout=30)
        secs = ((r.json().get("jobAd") or {}).get("sections") or {})
        return _limpiar(" ".join((v or {}).get("text", "") for v in secs.values())), ""
    except Exception:
        return "", ""


def _ashby(d, consultas):
    r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{d['org']}", headers=UA, timeout=30)
    r.raise_for_status()
    return [{"puesto": j.get("title", ""), "url": j.get("jobUrl", ""),
             "ubicacion": " / ".join(filter(None, [j.get("location", ""), "Remote" if j.get("isRemote") else ""])),
             "fecha": (j.get("publishedAt") or "")[:10], "descripcion": (j.get("descriptionPlain") or "")[:8000]}
            for j in r.json().get("jobs", [])]


LECTORES = {"workday": _workday, "greenhouse": _greenhouse, "lever": _lever, "smartrecruiters": _smartrecruiters,
            "ashby": _ashby}


def leer_portal(portal, cfg, log=print):
    """Vacantes del portal que sean de Costa Rica/remoto contratable y de tus áreas."""
    from . import jobs
    tipo, d = detectar(portal["url"])
    if not tipo:
        return []
    areas = jobs.areas_config(cfg)
    consultas = list(dict.fromkeys(["Costa Rica"] + [f"{a['terminos'][0]}" for a in areas[:6]]))[:4]
    crudas = LECTORES[tipo](d, consultas)
    validas = cfg["busqueda"]["ubicaciones_remotas_validas"] + ["remote", "remoto"]
    out, vistos = [], set()
    for c in crudas:
        if not c.get("url") or c["url"] in vistos:
            continue
        vistos.add(c["url"])
        j = jobs._job(f"Portal: {portal.get('empresa') or tipo}", portal.get("empresa") or "", c["puesto"], c["url"],
                      c.get("ubicacion"), c.get("descripcion", ""), c.get("fecha", ""))
        if jobs.titulo_excluido(j["puesto"], cfg):
            continue
        if jobs.location_ok(j["ubicacion"], validas, j["descripcion"]) is not True:
            continue  # en portales de empresa la ubicación es confiable: solo CR o remoto válido
        j["areas"] = jobs.areas_de_oferta(j, areas)
        if not j["areas"]:
            continue
        if c.get("_detalle") and len(j["descripcion"]) < 400:
            desc, f = (_detalle_workday if tipo == "workday" else _detalle_smart)(c["_detalle"])
            j["descripcion"] = desc or j["descripcion"]
            j["fecha"] = j["fecha"] or f
        j["elegible_ubicacion"] = True
        j["tipo_link"] = "directo"
        j["kw_score"] = jobs.keyword_score(j, [t for a in areas for t in a["terminos"]])
        out.append(j)
    return out


def leer_todos(cfg, log=print):
    ps = lista()
    if not ps:
        return []
    res = []

    def uno(p):
        try:
            r = leer_portal(p, cfg, log)
            return p, r, None
        except Exception as e:
            return p, [], e
    with ThreadPoolExecutor(max_workers=6) as ex:
        for p, r, e in ex.map(uno, ps):
            nombre = p.get("empresa") or p["url"]
            if e:
                log(f"  Portal {nombre}: no disponible ({e.__class__.__name__})")
            else:
                log(f"  Portal {nombre}: {len(r)} vacantes de tus áreas en Costa Rica/remoto")
            res.extend(r)
    return res

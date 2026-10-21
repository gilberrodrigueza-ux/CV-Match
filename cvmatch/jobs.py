"""Fuentes de ofertas: bolsas remotas con API pública + búsqueda web con IA para Costa Rica."""
import html
import re
from datetime import date

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CVMatch/1.0"}


def _clean(text, limit=None):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] if limit else text


def fecha_iso(f):
    """Normaliza fechas de las bolsas (ISO, RSS 'Mon, 13 Oct 2026', epoch) a AAAA-MM-DD; '' si no se puede."""
    f = str(f or "").strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", f):
        return f[:10]
    if re.fullmatch(r"\d{9,13}", f):
        from datetime import datetime as _dt
        n = int(f) / (1000 if len(f) > 10 else 1)
        return _dt.utcfromtimestamp(n).date().isoformat()
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(f).date().isoformat()
    except Exception:
        return ""


def _job(fuente, empresa, puesto, url, ubicacion, descripcion, fecha=""):
    return {"fuente": fuente, "empresa": (empresa or "").strip(), "puesto": (puesto or "").strip(),
            "url": (url or "").strip(), "ubicacion": (ubicacion or "").strip() or "Sin especificar",
            "descripcion": _clean(descripcion), "fecha": fecha_iso(fecha)}


def fetch_remotive(keywords):
    out = []
    for kw in keywords[:30]:
        r = requests.get("https://remotive.com/api/remote-jobs", params={"search": kw, "limit": 100},
                         headers=UA, timeout=30)
        r.raise_for_status()
        for j in r.json().get("jobs", []):
            out.append(_job("Remotive", j.get("company_name"), j.get("title"), j.get("url"),
                            j.get("candidate_required_location"), j.get("description"), j.get("publication_date")))
    return out


def fetch_remoteok(keywords):
    r = requests.get("https://remoteok.com/api", headers=UA, timeout=30)
    r.raise_for_status()
    out = []
    for j in r.json()[1:]:
        out.append(_job("RemoteOK", j.get("company"), j.get("position"), j.get("url"), j.get("location"),
                        j.get("description"), j.get("date")))
    return out


def fetch_himalayas(keywords):
    out = []
    for offset in range(0, 500, 20):
        r = requests.get("https://himalayas.app/jobs/api", params={"limit": 20, "offset": offset},
                         headers=UA, timeout=30)
        r.raise_for_status()
        jobs = r.json().get("jobs", [])
        if not jobs:
            break
        for j in jobs:
            loc = ", ".join(j.get("locationRestrictions") or []) or "Worldwide"
            out.append(_job("Himalayas", j.get("companyName"), j.get("title"),
                            j.get("applicationLink") or j.get("guid"), loc,
                            j.get("description") or j.get("excerpt"), str(j.get("pubDate", ""))))
    return out


def fetch_jobicy(keywords):
    out = []
    consultas = [{"count": 100, "geo": g} for g in ("latam", "anywhere")]
    consultas += [{"count": 50, "tag": t} for t in ("cloud", "devops", "infrastructure", "azure", "vmware", "sysadmin")]
    for params in consultas:
        try:
            r = requests.get("https://jobicy.com/api/v2/remote-jobs", params=params, headers=UA, timeout=30)
            r.raise_for_status()
            lista = r.json().get("jobs", [])
        except Exception:
            continue
        for j in lista:
            out.append(_job("Jobicy", j.get("companyName"), j.get("jobTitle"), j.get("url"),
                            j.get("jobGeo"), j.get("jobDescription") or j.get("jobExcerpt"), j.get("pubDate")))
    return out


def fetch_weworkremotely(keywords):
    """We Work Remotely (RSS). Categorías de DevOps/SysAdmin y back-end."""
    import xml.etree.ElementTree as ET
    out = []
    for cat in ("remote-devops-sysadmin-jobs", "remote-back-end-programming-jobs", "remote-full-stack-programming-jobs"):
        r = requests.get(f"https://weworkremotely.com/categories/{cat}.rss", headers=UA, timeout=30)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        for it in root.iter("item"):
            title = it.findtext("title") or ""
            empresa, _, puesto = title.partition(":")
            out.append(_job("We Work Remotely", empresa, puesto or title, it.findtext("link"),
                            it.findtext("region") or "", it.findtext("description"), it.findtext("pubDate") or ""))
    return out


def fetch_workingnomads(keywords):
    r = requests.get("https://www.workingnomads.com/api/exposed_jobs/", headers=UA, timeout=30)
    r.raise_for_status()
    return [_job("Working Nomads", j.get("company_name"), j.get("title"), j.get("url"), j.get("location"),
                 j.get("description"), j.get("pub_date") or "") for j in r.json()]


FUENTES = {"remotive": fetch_remotive, "remoteok": fetch_remoteok, "himalayas": fetch_himalayas,
           "jobicy": fetch_jobicy, "weworkremotely": fetch_weworkremotely, "workingnomads": fetch_workingnomads}


OTROS_PAISES = [
    "mexico", "méxico", "cdmx", "guadalajara", "monterrey", "colombia", "bogota", "bogotá", "medellin", "medellín",
    "brazil", "brasil", "são paulo", "sao paulo", "argentina", "buenos aires", "chile", "santiago", "peru", "perú",
    "lima", "uruguay", "montevideo", "panama", "panamá", "guatemala", "el salvador", "honduras", "nicaragua",
    "dominican", "dominicana", "ecuador", "bolivia", "paraguay", "venezuela", "puerto rico", "united states", "usa",
    "u.s.", "us only", "us-only", "canada", "canadá", "united kingdom", "uk", "england", "london", "ireland",
    "germany", "spain", "españa", "madrid", "portugal", "france", "poland", "netherlands", "europe", "emea", "india",
    "philippines", "australia", "new york", "san francisco", "texas", "california", "florida", "toronto"]
NO_REMOTO = ["relocation", "relocate", "reubicación", "on-site", "onsite", "on site", "in-office", "in office",
             "presencial", "hybrid", "híbrido", "hibrido"]


def _menciona(texto, palabras):
    return any(re.search(r"(?<![a-záéíóúñ])" + re.escape(p) + r"(?![a-záéíóúñ])", texto) for p in palabras)


CR_MARCAS = re.compile(
    r"costa rica|(?<![a-z])cr(?![a-z])|heredia|alajuela|cartago|escaz[uú]|bel[eé]n|santa ana|curridabat|"
    r"la sabana|grecia|san jos[eé](?!,? ?(ca|california))", re.I)


PAIS_REMOTO = re.compile(r"remote\s*[-–(:|]*\s*(us|u\.s\.|usa|united states|canada|australia|uk|europe|emea|india|"
                         r"argentina|brazil|mexico|portugal|spain|germany|poland|philippines)\b")
RESTRICCION_TEXTO = re.compile(
    r"(only able to hire|can only hire|only hiring|open (only )?to candidates (located|based|residing)|"
    r"must (reside|be located|be based|live|be authorized to work) in|candidates must be (located|based) in|"
    r"(this (role|position) (is|will be) )?based (onsite|on-site|in-office) (at|in)|position will be based in|"
    r"location requirement|remote-first \((?!latam|americas|worldwide|anywhere))")


def restringido_en_descripcion(descripcion):
    """Muchas bolsas ponen 'Anywhere in the World' pero el texto limita el país (p. ej. 'Headquarters: Remote - US',
    'only able to hire employees residing in Ontario'). Devuelve True si el texto lo restringe fuera de CR."""
    d = (descripcion or "").lower()
    if not d or CR_MARCAS.search(d[:3000]) and re.search(r"costa rica|latam|latin america", d[:3000]):
        return False
    m = re.search(r"headquarters:\s*(.{0,60})", d)
    if m:
        cab = m.group(1)
        if "remote" in cab and (_menciona(cab, OTROS_PAISES) or PAIS_REMOTO.search(cab)):
            return True
    if PAIS_REMOTO.search(d[:400]):
        return True
    for r in RESTRICCION_TEXTO.finditer(d):
        trozo = d[r.start():r.end() + 120]
        if not re.search(r"latam|latin america|americas|costa rica|anywhere|worldwide", trozo):
            return True
    return False


def location_ok(ubicacion, validas, descripcion=""):
    """Solo Costa Rica o remoto contratable desde Costa Rica.
    True = válido, None = no especificado (verificar), False = otro país / presencial fuera de CR / pide mudarse."""
    u = (ubicacion or "").lower()
    d = (descripcion or "").lower()[:4000]
    if CR_MARCAS.search(u):
        return True
    if _menciona(u, NO_REMOTO) or re.search(r"relocation (is )?(supported|available|provided|assistance)|willing to relocate", d):
        return False
    if restringido_en_descripcion(descripcion):
        return False
    if _menciona(u, OTROS_PAISES):
        return False  # oficina en otro país o restringido a otro país (aunque diga LATAM)
    if not u or u == "sin especificar":
        return None
    if any(v in u for v in validas):
        return True
    return False


def keyword_score(job, keywords):
    title = job["puesto"].lower()
    desc = job["descripcion"].lower()
    score = 0
    for kw in keywords:
        k = kw.lower()
        if k in title:
            score += 5
        if k in desc:
            score += 1
    return score


# para asignar un área por la DESCRIPCIÓN, el título tiene que ser de infraestructura/cloud (no basta "engineer")
GENERICO_TITULO = re.compile(r"architect|arquitect|infrastructure|infraestructura|cloud|nube|devops|platform|plataforma|"
                             r"systems|sistemas|sre|site reliability|virtuali|datacenter|data center|network|redes|"
                             r"support|soporte|migration|migraci|moderniz|vmware|azure|gcp")
TITULO_INFRA = GENERICO_TITULO


def titulo_excluido(puesto, cfg):
    """True si el título es de un perfil que no buscas (desarrollo de software, QA, ventas...)."""
    t = (puesto or "").lower()
    b = cfg["busqueda"]
    if _menciona(t, [x.lower() for x in b.get("excluir_titulos", [])]):
        return True
    if _menciona(t, [x.lower() for x in b.get("excluir_salvo_infra", [])]) and not TITULO_INFRA.search(t):
        return True
    # nivel: junior/intern/associate se descartan, salvo en soporte TI si así lo configuras
    if _menciona(t, [x.lower() for x in b.get("excluir_nivel", [])]):
        es_soporte = re.search(r"support|soporte|help ?desk|service desk|mesa de ayuda|technician|técnico", t)
        senior = re.search(r"senior|sr\.?\b|lead|principal|staff|manager|director|head", t)  # "Senior Associate" es senior
        if not senior and not (es_soporte and b.get("nivel_bajo_en_soporte", True)):
            return True
    return False
AREAS_TECNICAS = {"VMware", "HCX", "Hybrid Cloud", "Azure", "GCP"}


def areas_config(cfg, extra_keywords=None):
    """Las áreas de búsqueda; las palabras extra de la pantalla Buscar se tratan como un área más."""
    areas = [dict(a) for a in cfg["busqueda"].get("areas") or []]
    if not areas:  # config viejo: cada palabra clave como área
        areas = [{"nombre": k, "terminos": [k]} for k in cfg["busqueda"].get("palabras_clave", [])]
    extra = [k for k in (extra_keywords or []) if k]
    if extra:
        areas.append({"nombre": "Extra: " + ", ".join(extra), "terminos": extra})
    return areas


def areas_de_oferta(job, areas):
    """Áreas a las que pertenece una oferta: por el título; las técnicas (VMware, HCX, Azure, GCP, Hybrid) también
    por la descripción si el título es de infraestructura/cloud."""
    t = (job.get("puesto") or "").lower()
    d = (job.get("descripcion") or "").lower()[:6000]
    out = []
    for a in areas:
        terms = [x.lower() for x in a["terminos"]]
        if _menciona(t, terms):
            out.append(a["nombre"])
        elif a["nombre"] in AREAS_TECNICAS and GENERICO_TITULO.search(t) and _menciona(d, terms):
            out.append(a["nombre"])
    return out


def fetch_remote_jobs(cfg, extra_keywords, log):
    bcfg = cfg["busqueda"]
    areas = areas_config(cfg, extra_keywords)
    keywords = list(dict.fromkeys(t for a in areas for t in a["terminos"]))
    consultas = list(dict.fromkeys(t for a in areas for t in a["terminos"][:2]))  # 2 consultas por área en Remotive
    jobs = []
    for name in bcfg["fuentes_remotas"]:
        fn = FUENTES.get(name)
        if not fn:
            continue
        try:
            got = fn(consultas if name == "remotive" else keywords)
            log(f"  {name}: {len(got)} ofertas leídas")
            jobs.extend(got)
        except Exception as e:  # una fuente caída no detiene la búsqueda
            log(f"  {name}: no disponible ({e.__class__.__name__})")
    filtered, seen = [], set()
    desc_ubic = desc_kw = desc_tit = 0
    for j in jobs:
        if not j["url"] or j["url"] in seen:
            continue
        seen.add(j["url"])
        loc = location_ok(j["ubicacion"], bcfg["ubicaciones_remotas_validas"], j["descripcion"])
        if loc is False:
            desc_ubic += 1
            continue
        j["elegible_ubicacion"] = loc
        if titulo_excluido(j["puesto"], cfg):
            desc_tit += 1
            continue
        j["areas"] = areas_de_oferta(j, areas)
        j["kw_score"] = keyword_score(j, keywords)
        if j["areas"]:
            filtered.append(j)
        else:
            desc_kw += 1
    log(f"  Bolsas remotas: {len(seen)} ofertas distintas · {desc_ubic} descartadas por ubicación (no contratables "
        f"desde Costa Rica) · {desc_tit} de perfiles que no buscas (desarrollo, QA, ventas…) · {desc_kw} fuera de tus "
        f"áreas · {len(filtered)} de tus áreas")
    por_area = {a["nombre"]: sum(1 for j in filtered if a["nombre"] in j["areas"]) for a in areas}
    log("  Por área: " + " · ".join(f"{k} {v}" for k, v in por_area.items()))
    filtered.sort(key=lambda x: x["kw_score"], reverse=True)
    return filtered


def repartir_por_area(lista, areas, max_por_area):
    """Elige hasta max_por_area ofertas de CADA área (las de mejor coincidencia primero), sin repetir."""
    elegidas, usadas = [], set()
    for a in areas:
        n = 0
        for j in lista:
            if n >= max_por_area:
                break
            if a["nombre"] in (j.get("areas") or []):
                if j["url"] not in usadas:
                    usadas.add(j["url"])
                    elegidas.append(j)
                n += 1  # una oferta de varias áreas cuenta para cada una
    return elegidas


def search_costa_rica(llm, cv_summary, area, n=8, modelo=None, max_busquedas=2):
    """Búsqueda web (IA) de UN área: Costa Rica o remoto contratable desde CR."""
    from .prompts import PROMPT_BUSQUEDA_CR, SYSTEM_BUSCADOR
    data = llm.ask_json(SYSTEM_BUSCADOR, PROMPT_BUSQUEDA_CR.format(
        hoy=date.today().isoformat(), perfil=cv_summary, area=area["nombre"],
        keywords=", ".join(area["terminos"]), n=n, busquedas=max_busquedas),
        max_tokens=5000, web=True, modelo=modelo, max_busquedas=max_busquedas)
    out = []
    for o in data.get("ofertas", []):
        if o.get("url", "").startswith("http"):
            j = _job(f"Web: {o['sitio']}" if o.get("sitio") else "Búsqueda web (IA)", o.get("empresa"), o.get("puesto"), o.get("url"),
                     o.get("ubicacion") or o.get("modalidad"), o.get("resumen"))
            j["url"] = normalizar_link(j["url"])
            j["tipo_link"] = tipo_link(j["url"])
            loc = location_ok(f"{j['ubicacion']} {o.get('modalidad', '')}", ["remote", "remoto"], j["descripcion"])
            if loc is False:
                continue
            j["elegible_ubicacion"] = loc
            j["kw_score"] = 0
            j["areas"] = [area["nombre"]]
            out.append(j)
    return out


def fetch_jd_text(url):
    """Intenta descargar el texto completo de una oferta. Devuelve '' si el sitio lo bloquea (ej. LinkedIn)."""
    try:
        from bs4 import BeautifulSoup
        r = requests.get(url, headers=UA, timeout=30)
        if r.status_code != 200:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
            t.decompose()
        text = re.sub(r"\n\s*\n+", "\n\n", soup.get_text("\n")).strip()
        if "sign in" in text.lower()[:400] and len(text) < 2500:
            return ""
        return text[:20000]
    except Exception:
        return ""


def dedupe(jobs_list):
    """Une la misma oferta publicada en varias fuentes (misma empresa + puesto). Conserva la descripción más larga
    y lista todas las fuentes y links."""
    from .history import clave
    por_clave = {}
    for j in jobs_list:
        k = clave(j.get("empresa"), j.get("puesto"))
        if k in por_clave:
            base = por_clave[k]
            base.setdefault("otras_fuentes", [])
            base["otras_fuentes"].append({"fuente": j["fuente"], "url": j["url"]})
            if len(j.get("descripcion", "")) > len(base.get("descripcion", "")):
                base["descripcion"] = j["descripcion"]
            base["areas"] = list(dict.fromkeys((base.get("areas") or []) + (j.get("areas") or [])))
        else:
            por_clave[k] = j
    return list(por_clave.values())


# ---------------- links directos vs. páginas de lista ----------------
from urllib.parse import quote_plus, urlparse  # noqa: E402

_DIRECTO = [r"linkedin\.com/jobs/view/\d+", r"linkedin\.com/.*currentJobId=\d+", r"indeed\.[a-z.]+/(viewjob|rc/clk|pagead)",
            r"[?&]jk=[0-9a-f]+", r"glassdoor\.[a-z.]+/job-listing/", r"glassdoor\.[a-z.]+/.*jobListingId=\d+",
            r"computrabajo\.com/ofertas-de-trabajo/oferta-de-trabajo", r"getonbrd\.com/jobs/[^/]+/[^/]+",
            r"torre\.ai/post/", r"tecoloco\.[a-z.]+/.+\d{4,}", r"myworkdayjobs\.com/.+/job/", r"greenhouse\.io/.+/jobs/\d+",
            r"lever\.co/[^/]+/[0-9a-f-]{20,}", r"smartrecruiters\.com/[^/]+/\d+", r"icims\.com/jobs/\d+",
            r"successfactors\.com/.*(career_job_req_id|jobId)=\d+", r"oraclecloud\.com/.+/job/\d+", r"/jobs?/\d{4,}",
            r"/job/[^/]+/\d{4,}", r"/requisition", r"[?&](job_?id|jobid|req(id)?|posting_?id)=\w+"]
_LISTA = [r"linkedin\.com/jobs/search", r"linkedin\.com/jobs/collections", r"linkedin\.com/jobs/[a-z0-9-]+-jobs",
          r"linkedin\.com/jobs/?$", r"indeed\.[a-z.]+/(jobs|q-|empleos)", r"glassdoor\.[a-z.]+/(Job|Empleo)/.*SRCH",
          r"computrabajo\.com/(trabajo-de|empleos-)", r"[?&](keywords|q|query|search)=", r"/search", r"/(jobs|empleos|careers)/?$"]


def normalizar_link(url):
    """Convierte links de LinkedIn que traen el id de la oferta (currentJobId) en el link directo /jobs/view/<id>."""
    m = re.search(r"linkedin\.com/.*[?&]currentJobId=(\d+)", url or "", re.I)
    if m:
        return f"https://www.linkedin.com/jobs/view/{m.group(1)}/"
    return url


def tipo_link(url):
    """'directo' si apunta a una oferta concreta, 'lista' si es una página de resultados, 'desconocido' si no se sabe."""
    u = normalizar_link(url or "")
    if not u.lower().startswith("http"):
        return "desconocido"
    if any(re.search(p, u, re.I) for p in _DIRECTO):
        return "directo"
    if any(re.search(p, u, re.I) for p in _LISTA):
        return "lista"
    return "desconocido"


def link_busqueda(job):
    """Link para encontrar una oferta cuando solo tenemos una página de lista: búsqueda filtrada por puesto + empresa."""
    puesto, empresa = (job.get("puesto") or "").strip(), (job.get("empresa") or "").strip()
    host = urlparse(job.get("url") or "").netloc.lower()
    if "linkedin" in host:
        return ("https://www.linkedin.com/jobs/search/?keywords=" + quote_plus(f'"{puesto}" {empresa}')
                + "&location=" + quote_plus("Costa Rica"))
    return "https://www.google.com/search?q=" + quote_plus(f'"{puesto}" "{empresa}" empleo')

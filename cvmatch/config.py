import json
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
BASE_DATOS = APP_DIR / "datos"              # datos del sistema (usuarios, acceso remoto)
SISTEMA_PATH = BASE_DATOS / "sistema.json"  # {"multiusuario": true/false, "registro_abierto": false}
_USUARIO_GLOBAL = [None]                    # para procesos sin interfaz (búsqueda automática --usuario X)


class SinUsuario(RuntimeError):
    pass


def sistema():
    try:
        return json.loads(SISTEMA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def guardar_sistema(d):
    BASE_DATOS.mkdir(parents=True, exist_ok=True)
    SISTEMA_PATH.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def multiusuario():
    """Modo multiusuario (cada persona con su usuario, contraseña y datos separados).
    Instalaciones nuevas: sí. Instalaciones que ya tenían datos de una sola persona: no, hasta que se migren."""
    s = sistema()
    if "multiusuario" in s:
        return bool(s["multiusuario"])
    legado = (BASE_DATOS / "api_key.txt").exists() or (APP_DIR / "config.json").exists()
    return not legado


def set_usuario(nombre):
    _USUARIO_GLOBAL[0] = nombre


def usuario_actual():
    """Usuario de la sesión de Streamlit (cada navegador tiene el suyo) o el del proceso en segundo plano."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        try:
            ctx = get_script_run_ctx(suppress_warning=True)
        except TypeError:
            ctx = get_script_run_ctx()
        if ctx is not None:
            import streamlit as st
            u = st.session_state.get("_usuario")
            if u:
                return u
    except Exception:
        pass
    return _USUARIO_GLOBAL[0]


def dir_datos():
    if not multiusuario():
        return BASE_DATOS
    u = usuario_actual()
    if not u:
        raise SinUsuario("No hay un usuario con sesión iniciada")
    return BASE_DATOS / "usuarios" / u


def dir_usuario_app():
    """Dónde viven config.json y el CV base: la carpeta de la app (un usuario) o la carpeta del usuario."""
    return dir_datos() if multiusuario() else APP_DIR


class LazyPath(os.PathLike):
    """Ruta que se resuelve en el momento de usarla, según el usuario de la sesión.
    Se comporta como pathlib.Path (exists, read_text, open, / ...)."""

    def __init__(self, base, *partes):
        self._base, self._partes = base, partes

    def resolver(self):
        return self._base().joinpath(*self._partes)

    def __truediv__(self, otro):
        return LazyPath(self._base, *self._partes, otro)

    def __fspath__(self):
        return str(self.resolver())

    __str__ = __fspath__

    def __repr__(self):
        return f"LazyPath({self.resolver()!s})"

    def mkdir(self, *a, **k):
        k.setdefault("parents", True)
        k.setdefault("exist_ok", True)
        return self.resolver().mkdir(*a, **k)

    def __getattr__(self, nombre):
        return getattr(self.resolver(), nombre)

    def __eq__(self, otro):
        return Path(self) == Path(otro)

    def __hash__(self):
        return hash(str(self))


DATA_DIR = LazyPath(dir_datos)
CONFIG_PATH = LazyPath(dir_usuario_app, "config.json")
ENV_PATH = DATA_DIR / ".env"
KEY_PATH = DATA_DIR / "api_key.txt"

DEFAULTS = {
    "cv_base": "CV_base.pdf",
    "carpeta_salida": "../Automatico",
    "modelo_analisis": "claude-sonnet-5-5",
    "modelo_redaccion": "claude-sonnet-5-5",
    "presupuesto_mensual_usd": 5.0,
    "horas_entre_busquedas_web": 6,
    "generar_pdf": True,
    "max_paginas_cv": 2,
    "puntaje_minimo_mostrar": 50,
    "max_ofertas_a_rankear": 30,
    "trainings_con_busqueda_web": True,
    "busqueda_automatica": {"horas": ["07:00", "13:00"]},
    "ollama": {"usar_para_evaluar_ofertas": True, "modelo": "qwen2.5", "url": "http://localhost:11434"},
    "investigar_empresa": True,
    "preparar_entrevista": True,
    "idiomas_declarados": "",
    "dias_para_seguimiento": 7,
    "outlook": {"client_id": "", "dias_revisar": 14, "revisar_en_busqueda_automatica": True},
    "modelos_por_tarea": {
        "ranking": "claude-haiku-5-5",
        "busqueda_web": "claude-haiku-5-5",
        "top5": "claude-haiku-5-5",
        "empresa": "claude-haiku-5-5",
        "seguimiento": "claude-haiku-5-5",
        "pulido_estilo": "claude-sonnet-5-5"
    },
    "perfil_objetivo": 'PERFIL OBJETIVO del candidato (qué puestos SÍ busca):\n- Arquitecto/ingeniero senior de infraestructura y cloud (Azure, GCP; AWS en migraciones), arquitectura de soluciones.\n- Migración y modernización (datacenter, cargas, bases de datos, correo, identidad), VMware/vSphere/vSAN/HCX,\n  nube híbrida, plataforma/SRE/DevOps enfocados en infraestructura.\n- Soporte TI remoto (IT Support Technician, service desk, desktop support): también le interesa.\nNO es su perfil: desarrollo de software como tarea principal (programar productos en Go, TypeScript, Java, .NET,\nScala, front-end, full-stack), QA, ciencia de datos, ventas.',
    "empresas_favoritas": ["Kyndryl", "IBM", "Microsoft", "Akamai", "ServiceNow", "Equifax", "Experian", "Oracle",
                           "Amazon", "Google", "Accenture", "Dell", "HPE", "Cisco", "Broadcom", "Pythian", "Gartner"],
    "buscar_en_favoritas": True,
    "dias_oferta_vieja": 30,
    "resumen_diario": {"activado": False, "match_minimo": 70},
    "busqueda_web": {"orden": ["tavily", "claude"], "claude_respaldo": True},
    "busqueda": {
        "palabras_clave": ["senior infrastructure", "infrastructure engineer", "infrastructure architect", "cloud architect", "cloud architecture", "solutions architect", "cloud engineer", "migration", "modernization", "vmware", "hcx", "hybrid cloud", "azure", "gcp", "google cloud", "platform engineer", "systems engineer", "site reliability", "datacenter", "infrastructure"],
        "areas": [
            {"nombre": "Senior Infrastructure", "terminos": ["senior infrastructure", "infrastructure engineer", "infrastructure architect", "infrastructure lead", "infrastructure manager", "it infrastructure", "infrastructure", "network engineer", "datacenter", "data center", "systems engineer", "infraestructura", "ingeniero de sistemas"]},
            {"nombre": "Cloud Architecture", "terminos": ["cloud architect", "cloud architecture", "solutions architect", "solution architect", "enterprise architect", "cloud solutions", "arquitecto cloud", "arquitecto de soluciones", "arquitecto de nube"]},
            {"nombre": "Migration and modernization", "terminos": ["migration", "modernization", "modernisation", "cloud migration", "transformation", "migración", "modernización"]},
            {"nombre": "Engineering", "terminos": ["cloud engineer", "platform engineer", "site reliability", "sre", "devops engineer", "cloud operations", "ingeniero cloud", "ingeniero de nube"]},
            {"nombre": "VMware", "terminos": ["vmware", "vsphere", "vsan", "vcf", "nsx", "virtualization"]},
            {"nombre": "HCX", "terminos": ["hcx", "vmware engine", "gcve", "azure vmware solution", "vmware cloud"]},
            {"nombre": "Hybrid Cloud", "terminos": ["hybrid cloud", "multi-cloud", "multicloud", "nube híbrida"]},
            {"nombre": "Azure", "terminos": ["azure"]},
            {"nombre": "GCP", "terminos": ["gcp", "google cloud"]},
            {"nombre": "Remote IT Support Technician", "terminos": ["it support", "support technician", "technical support",
                                                                    "desktop support", "help desk", "helpdesk", "service desk",
                                                                    "it technician", "support engineer", "soporte técnico",
                                                                    "soporte ti", "técnico de soporte", "mesa de ayuda"]}
        ],
        "excluir_titulos": ["frontend", "front-end", "full stack", "full-stack", "fullstack", ".net", "c#", "java",
                            "scala", "golang", "ruby", "php", "ios", "android", "mobile", "data scientist",
                            "machine learning engineer", "qa", "test engineer", "testing", "designer", "sales",
                            "account executive", "marketing", "recruiter", "atlassian"],
        "excluir_salvo_infra": ["software engineer", "developer", "desarrollador", "programmer", "backend", "back-end",
                                "ai engineer", "agent engineer", "data engineer"],
        "excluir_nivel": ["junior", "jr", "jr.", "intern", "internship", "trainee", "entry level", "entry-level",
                          "associate", "graduate", "becario", "practicante", "pasante"],
        "nivel_bajo_en_soporte": True,
        "usar_portales": True,
        "verificar_vigencia": True,
        "apagar_fuentes_sin_rendimiento": True,
        "auto_solo_recientes_horas": 48,
        "max_por_area": 8,
        "busquedas_web_por_area": 2,
        "fuentes_remotas": ["remotive", "remoteok", "himalayas", "jobicy", "weworkremotely", "workingnomads"],
        "buscar_costa_rica_con_ia": True,
        "ubicaciones_remotas_validas": [
            "worldwide", "anywhere", "global", "latam", "latin america",
            "americas", "costa rica", "central america", "south america",
            "remote - americas", "lat am"
        ]
    }
}


def _merge(base, override):
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


VERSION_CONFIG = 3


def _migrar(cfg):
    """Agrega una sola vez las novedades a un config.json existente, sin pisar lo que el usuario cambió."""
    if not CONFIG_PATH.exists():
        return
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return
    if raw.get("version_config", 1) >= VERSION_CONFIG:
        return
    fuentes = raw.setdefault("busqueda", {}).setdefault("fuentes_remotas", list(cfg["busqueda"]["fuentes_remotas"]))
    for nueva in ("weworkremotely", "workingnomads"):
        if nueva not in fuentes:
            fuentes.append(nueva)
    # si las palabras clave seguían siendo las de fábrica, se cambian por tus áreas
    viejas = ["cloud architect", "cloud engineer", "infrastructure architect", "infrastructure engineer", "migration",
              "azure", "google cloud", "gcp", "vmware", "systems engineer", "identity", "entra", "terraform",
              "solutions architect", "m365", "exchange", "datacenter"]
    if raw["busqueda"].get("palabras_clave") == viejas:
        raw["busqueda"]["palabras_clave"] = list(DEFAULTS["busqueda"]["palabras_clave"])
        cfg["busqueda"]["palabras_clave"] = raw["busqueda"]["palabras_clave"]
    raw["version_config"] = VERSION_CONFIG
    CONFIG_PATH.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    cfg["busqueda"]["fuentes_remotas"] = fuentes


def load_config():
    import copy
    DATA_DIR.mkdir(exist_ok=True)
    cfg = copy.deepcopy(DEFAULTS)  # copia: nunca se modifican los valores de fábrica (importante con varios usuarios)
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = _merge(copy.deepcopy(DEFAULTS), json.load(f))
    else:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULTS, f, indent=2, ensure_ascii=False)
    _migrar(cfg)
    cfg["_cv_base_path"] = (dir_usuario_app() / cfg["cv_base"]).resolve()
    cfg["_salida_path"] = (APP_DIR / cfg["carpeta_salida"]).resolve()
    if multiusuario():
        cfg["_salida_path"] = cfg["_salida_path"] / usuario_actual()  # cada usuario con su carpeta de CVs
    cfg["_salida_path"].mkdir(parents=True, exist_ok=True)
    return cfg


def modelo_tarea(cfg, tarea):
    return (cfg.get("modelos_por_tarea") or {}).get(tarea) or cfg["modelo_analisis"]


def get_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    if KEY_PATH.exists():
        k = KEY_PATH.read_text(encoding="utf-8-sig").strip()
        if k:
            return k
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


def save_api_key(key):
    DATA_DIR.mkdir(exist_ok=True)
    KEY_PATH.write_text(key.strip() + "\n", encoding="utf-8")

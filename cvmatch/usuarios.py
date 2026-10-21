"""Usuarios del modo multiusuario: nombre + contraseña (PBKDF2-SHA256 con sal), cada uno con su carpeta de datos."""
import hashlib
import hmac
import json
import os
import re
import shutil
import time
from datetime import date

from .config import APP_DIR, BASE_DATOS, guardar_sistema, sistema

ARCHIVO = BASE_DATOS / "usuarios.json"
NOMBRE_OK = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")


def _cargar():
    try:
        return json.loads(ARCHIVO.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _guardar(d):
    BASE_DATOS.mkdir(parents=True, exist_ok=True)
    tmp = ARCHIVO.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(ARCHIVO)


def _hash(clave, salt):
    return hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), bytes.fromhex(salt), 300_000).hex()


def normalizar(nombre):
    return (nombre or "").strip().lower()


def validar(nombre, clave):
    if not NOMBRE_OK.match(normalizar(nombre)):
        return "El usuario debe tener 3-32 caracteres: letras minúsculas, números, punto, guion o guion bajo."
    if len(clave or "") < 8:
        return "La contraseña debe tener al menos 8 caracteres."
    return None


def hay_usuarios():
    return bool(_cargar())


def lista():
    return [{"usuario": u, **{k: v for k, v in d.items() if k not in ("hash", "salt")}} for u, d in sorted(_cargar().items())]


def es_admin(nombre):
    return bool(_cargar().get(normalizar(nombre), {}).get("admin"))


def crear(nombre, clave, admin=False):
    nombre = normalizar(nombre)
    err = validar(nombre, clave)
    if err:
        raise ValueError(err)
    d = _cargar()
    if nombre in d:
        raise ValueError("Ese usuario ya existe.")
    salt = os.urandom(16).hex()
    d[nombre] = {"salt": salt, "hash": _hash(clave, salt), "admin": bool(admin or not d), "creado": date.today().isoformat()}
    _guardar(d)
    (BASE_DATOS / "usuarios" / nombre).mkdir(parents=True, exist_ok=True)
    return nombre


def verificar(nombre, clave):
    u = _cargar().get(normalizar(nombre))
    ok = bool(u) and hmac.compare_digest(_hash(clave or "", u["salt"]), u["hash"])
    if not ok:
        time.sleep(1.5)  # frena intentos repetidos
    return ok


def cambiar_clave(nombre, nueva):
    nombre = normalizar(nombre)
    if len(nueva or "") < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")
    d = _cargar()
    if nombre not in d:
        raise ValueError("No existe ese usuario.")
    d[nombre]["salt"] = os.urandom(16).hex()
    d[nombre]["hash"] = _hash(nueva, d[nombre]["salt"])
    _guardar(d)


def poner_admin(nombre, admin):
    d = _cargar()
    nombre = normalizar(nombre)
    if nombre in d:
        if not admin and sum(1 for x in d.values() if x.get("admin")) <= 1 and d[nombre].get("admin"):
            raise ValueError("Debe quedar al menos un administrador.")
        d[nombre]["admin"] = bool(admin)
        _guardar(d)


def borrar(nombre, borrar_datos=False):
    d = _cargar()
    nombre = normalizar(nombre)
    if d.get(nombre, {}).get("admin") and sum(1 for x in d.values() if x.get("admin")) <= 1:
        raise ValueError("No se puede borrar el único administrador.")
    d.pop(nombre, None)
    _guardar(d)
    if borrar_datos:
        shutil.rmtree(BASE_DATOS / "usuarios" / nombre, ignore_errors=True)


def registro_abierto():
    return bool(sistema().get("registro_abierto"))


def poner_registro_abierto(valor):
    s = sistema()
    s["registro_abierto"] = bool(valor)
    guardar_sistema(s)


# ---------------- migración desde una instalación de un solo usuario ----------------
SISTEMA_ARCHIVOS = {"usuarios.json", "sistema.json", "acceso.json", "habilitar_firewall.ps1", "usuarios"}


def migrar_a_multiusuario(nombre, clave):
    """Pasa los datos de la instalación actual (un usuario) a un usuario administrador y activa el modo multiusuario."""
    nombre = crear(nombre, clave, admin=True)
    destino = BASE_DATOS / "usuarios" / nombre
    destino.mkdir(parents=True, exist_ok=True)
    for item in list(BASE_DATOS.iterdir()):
        if item.name not in SISTEMA_ARCHIVOS:
            shutil.move(str(item), str(destino / item.name))
    for nombre_archivo in ["config.json"] + [p.name for p in APP_DIR.glob("CV_base.*")]:
        src = APP_DIR / nombre_archivo
        if src.exists():
            shutil.move(str(src), str(destino / nombre_archivo))
    s = sistema()
    s["multiusuario"] = True
    guardar_sistema(s)
    return nombre

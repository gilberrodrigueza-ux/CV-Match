"""Acceso desde otros dispositivos (celular): contraseña, direcciones de la laptop y regla de firewall restringida."""
import hashlib
import json
import os
import socket
import subprocess

from .config import BASE_DATOS as DATA_DIR  # acceso remoto: es del sistema, no de un usuario

ARCHIVO = DATA_DIR / "acceso.json"
PUERTO = 8501


def cargar():
    try:
        return json.loads(ARCHIVO.read_text(encoding="utf-8"))
    except Exception:
        return {"activado": False}


def guardar(d):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVO.write_text(json.dumps(d, indent=2), encoding="utf-8")


def _hash(clave, salt):
    return hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), bytes.fromhex(salt), 200_000).hex()


def poner_clave(clave):
    d = cargar()
    d["salt"] = os.urandom(16).hex()
    d["hash"] = _hash(clave, d["salt"])
    guardar(d)


def verificar(clave):
    d = cargar()
    return bool(d.get("hash")) and _hash(clave or "", d["salt"]) == d["hash"]


def es_local(ip, host):
    """Solo se considera local si la conexión viene de la propia laptop Y se abrió como localhost
    (así un túnel o proxy local no puede saltarse la contraseña)."""
    h = (host or "").split(":")[0].strip("[]").lower()
    return ip is None and h in ("localhost", "127.0.0.1", "::1", "")


def _ip_por_ruta(destino):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect((destino, 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def direcciones():
    """IP de la red de tu casa y, si tienes Tailscale, la IP de Tailscale (100.x.x.x)."""
    out = {}
    lan = _ip_por_ruta("8.8.8.8")
    if lan and not lan.startswith("100."):
        out["wifi"] = f"http://{lan}:{PUERTO}"
    ts = _ip_por_ruta("100.100.100.100")
    if ts and ts.startswith("100."):
        out["tailscale"] = f"http://{ts}:{PUERTO}"
    return out


REGLA = "CV Match (red local y Tailscale)"


def script_firewall():
    """Crea el script de PowerShell con la regla de entrada SOLO para tu red local y Tailscale (no internet)."""
    ps1 = DATA_DIR / "habilitar_firewall.ps1"
    ps1.write_text(
        f"Remove-NetFirewallRule -DisplayName '{REGLA}' -ErrorAction SilentlyContinue\r\n"
        f"New-NetFirewallRule -DisplayName '{REGLA}' -Direction Inbound -Protocol TCP -LocalPort {PUERTO} "
        "-Action Allow -Profile Any -RemoteAddress LocalSubnet,100.64.0.0/10\r\n", encoding="utf-8")
    return ps1


def abrir_firewall():
    """Ejecuta el script como administrador (Windows mostrará el aviso de permiso)."""
    ps1 = script_firewall()
    cmd = (f"Start-Process powershell -Verb RunAs -WindowStyle Hidden "
           f"-ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','\"{ps1}\"'")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


def qr_png(texto):
    import io
    import segno
    buf = io.BytesIO()
    segno.make(texto, error="m").save(buf, kind="png", scale=6, border=2)
    return buf.getvalue()

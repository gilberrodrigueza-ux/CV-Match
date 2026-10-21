"""Tarea programada de Windows para la búsqueda automática.
Uso: python -m cvmatch.scheduler activar|desactivar|estado"""
import json
import subprocess
import sys

from .config import APP_DIR, load_config, multiusuario, usuario_actual

TASK = "CV Match - Busqueda automatica"


def _tarea(usuario=None):
    """Una tarea por usuario en modo multiusuario."""
    u = usuario or (usuario_actual() if multiusuario() else None)
    return f"{TASK} - {u}" if u else TASK


def _ps(script):
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def _pythonw():
    p = APP_DIR / ".venv" / "Scripts" / "pythonw.exe"
    if p.exists():
        return str(p)
    exe = sys.executable
    return exe[:-10] + "pythonw.exe" if exe.lower().endswith("python.exe") else exe


def activar(horas, usuario=None):
    if not sys.platform.startswith("win"):
        return False, "Las tareas programadas solo funcionan en Windows."
    horas = [h.strip() for h in horas if h.strip()]
    if not horas:
        return False, "Indica al menos una hora (HH:MM)."
    triggers = ",".join(f"(New-ScheduledTaskTrigger -Daily -At '{h}')" for h in horas)
    u = usuario or (usuario_actual() if multiusuario() else None)
    arg = f"buscar_auto.py --usuario {u}" if u else "buscar_auto.py"
    script = (
        f"$a = New-ScheduledTaskAction -Execute '{_pythonw()}' -Argument '{arg}' -WorkingDirectory '{APP_DIR}';"
        f"$t = @({triggers});"
        "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
        "-ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew;"
        f"Register-ScheduledTask -TaskName '{_tarea(u)}' -Action $a -Trigger $t -Settings $s "
        "-Description 'Busca ofertas para CV Match' -Force | Out-Null; 'ok'")
    return _ps(script)


def desactivar(usuario=None):
    return _ps(f"Unregister-ScheduledTask -TaskName '{_tarea(usuario)}' -Confirm:$false; 'ok'")


def estado(usuario=None):
    """Devuelve dict con estado, próxima y última ejecución, o None si no existe."""
    if not sys.platform.startswith("win"):
        return None
    ok, out = _ps(
        f"$t = Get-ScheduledTask -TaskName '{_tarea(usuario)}' -ErrorAction Stop; $i = $t | Get-ScheduledTaskInfo;"
        "[pscustomobject]@{estado=[string]$t.State; proxima=[string]$i.NextRunTime; ultima=[string]$i.LastRunTime;"
        "horas=($t.Triggers | ForEach-Object { ([datetime]$_.StartBoundary).ToString('HH:mm') }) -join ', '} | ConvertTo-Json")
    if not ok:
        return None
    try:
        return json.loads(out)
    except Exception:
        return None


if __name__ == "__main__":
    accion = sys.argv[1] if len(sys.argv) > 1 else "estado"
    if accion == "activar":
        horas = load_config().get("busqueda_automatica", {}).get("horas", ["07:00", "13:00"])
        ok, out = activar(horas)
        print(("Búsqueda automática activada a las " + ", ".join(horas)) if ok else f"Error: {out}")
    elif accion == "desactivar":
        ok, out = desactivar()
        print("Búsqueda automática desactivada." if ok else f"Error: {out}")
    else:
        print(estado() or "No hay búsqueda automática programada.")

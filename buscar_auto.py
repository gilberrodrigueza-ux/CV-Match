"""Búsqueda automática (la ejecuta la tarea programada de Windows, sin ventana).
Busca, evalúa solo las ofertas nuevas, las deja en el módulo Buscar y avisa con una notificación."""
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cvmatch.config import DATA_DIR, get_api_key, load_config, multiusuario, set_usuario  # noqa: E402

# modo multiusuario: la tarea programada indica de quién es la búsqueda (buscar_auto.py --usuario nombre)
if "--usuario" in sys.argv:
    set_usuario(sys.argv[sys.argv.index("--usuario") + 1])
elif multiusuario():
    print("Indica el usuario: buscar_auto.py --usuario nombre")
    sys.exit(1)

LOG = DATA_DIR / "busquedas_auto.log"
ESTADO = DATA_DIR / "estado_auto.json"
LOCK = DATA_DIR / "busqueda_auto.lock"


def log(msg):
    DATA_DIR.mkdir(exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M} {msg}\n")


class LogUI:
    def info(self, m): log(m)
    warn = ok = step = title = info


def notificar(titulo, texto):
    if not sys.platform.startswith("win"):
        return
    t = titulo.replace("'", "’")
    x = texto.replace("'", "’")
    ps = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
        "$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
        "$n = $xml.GetElementsByTagName('text');"
        f"$n.Item(0).AppendChild($xml.CreateTextNode('{t}')) > $null;"
        f"$n.Item(1).AppendChild($xml.CreateTextNode('{x}')) > $null;"
        "$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe';"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show([Windows.UI.Notifications.ToastNotification]::new($xml))")
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                       capture_output=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        pass


def main():
    DATA_DIR.mkdir(exist_ok=True)
    if LOCK.exists() and time.time() - LOCK.stat().st_mtime < 3600:
        log("Ya hay una búsqueda en curso; se omite esta.")
        return
    LOCK.write_text(str(datetime.now()), encoding="utf-8")
    estado = {"ultima": datetime.now().strftime("%Y-%m-%d %H:%M"), "nuevas": 0, "total": 0, "error": None}
    try:
        key = get_api_key()
        if not key:
            raise RuntimeError("No hay API key configurada")
        cfg = load_config()
        from cvmatch.cv_reader import read_cv
        from cvmatch.facts import Facts
        from cvmatch.llm import LLM
        from cvmatch.pipeline import Pipeline
        llm = LLM(key, cfg["modelo_analisis"], cfg["modelo_redaccion"])
        llm.cfg = cfg
        pipe = Pipeline(cfg, llm, Facts(), read_cv(cfg["_cv_base_path"]), LogUI())
        log("=== Búsqueda automática iniciada ===")
        try:
            from cvmatch.backup import respaldo_diario
            respaldo_diario()
        except Exception:
            pass
        res = pipe.search([], recientes_h=cfg["busqueda"].get("auto_solo_recientes_horas") or None)
        nuevas = [j for j in res if j.get("nueva")]
        estado.update(nuevas=len(nuevas), total=len(res))
        log(f"=== Terminada: {len(nuevas)} nuevas, {len(res)} en la lista ===")
        oc = cfg.get("outlook") or {}
        if oc.get("client_id") and oc.get("revisar_en_busqueda_automatica", True):
            try:
                from cvmatch import correo
                antes = len(correo.sugerencias())
                pend = correo.revisar(pipe, log)
                if len(pend) > antes:
                    notificar(f"CV Match: {len(pend) - antes} novedad(es) en tu correo",
                              "Respuestas de empresas a las que aplicaste. Abre CV Match → Panel para revisarlas.")
            except Exception as e:
                log(f"Outlook: {e}")
        if nuevas:
            mejor = nuevas[0]
            notificar(f"CV Match: {len(nuevas)} ofertas nuevas",
                      f"Mejor: {mejor['puesto']} — {mejor['empresa']} ({mejor.get('match_estimado')}/100). Abre CV Match → Buscar ofertas.")
    except Exception as e:
        estado["error"] = str(e)
        log(f"ERROR: {e}")
        notificar("CV Match: la búsqueda automática falló", str(e)[:150])
    finally:
        ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

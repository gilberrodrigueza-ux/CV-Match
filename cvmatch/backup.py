"""Respaldo diario del historial y de tus respuestas (protege contra conflictos de sincronización de OneDrive)."""
import shutil
import sqlite3
from datetime import date

from .config import DATA_DIR

RESPALDOS = DATA_DIR / "respaldos"
ARCHIVOS = ["hechos_confirmados.json", "muestra_estilo.txt", "linkedin.txt", "ultima_busqueda.json"]


def respaldo_diario(conservar=14):
    """Crea datos/respaldos/AAAA-MM-DD una vez al día y conserva los últimos `conservar`."""
    destino = RESPALDOS / date.today().isoformat()
    if destino.exists():
        return None
    destino.mkdir(parents=True, exist_ok=True)
    db = DATA_DIR / "historial.db"
    if db.exists():
        src = sqlite3.connect(db)
        dst = sqlite3.connect(destino / "historial.db")
        with dst:
            src.backup(dst)  # copia consistente aunque la base esté en uso
        src.close()
        dst.close()
    for f in ARCHIVOS:
        if (DATA_DIR / f).exists():
            shutil.copy2(DATA_DIR / f, destino / f)
    carpetas = sorted(p for p in RESPALDOS.iterdir() if p.is_dir())
    for viejo in carpetas[:-conservar]:
        shutil.rmtree(viejo, ignore_errors=True)
    return destino

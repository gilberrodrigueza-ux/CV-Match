"""Base de hechos confirmados por el candidato (lo único que se suma al CV base)."""
import json
import re
from datetime import date

from .config import DATA_DIR

FACTS_PATH = DATA_DIR / "hechos_confirmados.json"


def _norm(s):
    return re.sub(r"[^a-z0-9áéíóúñ+#./ ]", " ", (s or "").lower()).split()


class Facts:
    def __init__(self):
        self.items = []
        if FACTS_PATH.exists():
            self.items = json.loads(FACTS_PATH.read_text(encoding="utf-8"))

    def save(self):
        FACTS_PATH.write_text(json.dumps(self.items, indent=2, ensure_ascii=False), encoding="utf-8")

    def add(self, habilidad, tiene, detalle="", origen=""):
        existing = self.find(habilidad)
        entry = {"habilidad": habilidad.strip(), "tiene": tiene, "detalle": detalle.strip(),
                 "fecha": date.today().isoformat(), "origen": origen}
        if existing is not None:
            self.items[self.items.index(existing)] = entry
        else:
            self.items.append(entry)
        self.save()

    def remove(self, idx):
        if 0 <= idx < len(self.items):
            self.items.pop(idx)
            self.save()

    def find(self, habilidad):
        """Coincidencia aproximada por tokens para no volver a preguntar lo mismo."""
        q = set(_norm(habilidad))
        if not q:
            return None
        best, best_score = None, 0.0
        for it in self.items:
            t = set(_norm(it["habilidad"]))
            if not t:
                continue
            inter = len(q & t)
            score = inter / min(len(q), len(t))
            if score > best_score:
                best, best_score = it, score
        return best if best_score >= 0.75 else None

    def as_text(self):
        if not self.items:
            return "(ninguno todavía)"
        lines = []
        for it in self.items:
            det = f" — {it['detalle']}" if it.get("detalle") else ""
            lines.append(f"- {it['habilidad']}: tiene={it['tiene']}{det}")
        return "\n".join(lines)

"""Cliente mínimo de Ollama (IA local gratis). Solo se usa para evaluar ofertas; si falla, la app usa Claude."""
import requests

from .llm import extract_json


def disponible(url="http://localhost:11434"):
    try:
        r = requests.get(f"{url}/api/tags", timeout=3)
        return r.status_code == 200, [m.get("name") for m in r.json().get("models", [])]
    except Exception:
        return False, []


def ask_json(system, user, modelo, url="http://localhost:11434", timeout=600):
    r = requests.post(f"{url}/api/chat", timeout=timeout, json={
        "model": modelo, "stream": False, "format": "json",
        "options": {"temperature": 0.1},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
    r.raise_for_status()
    return extract_json(r.json().get("message", {}).get("content", ""))


def elegir_modelo(preferido, instalados):
    """Usa el modelo configurado si está instalado; si no, uno de la misma familia (ej. qwen2.5:14b); si no, el primero."""
    if not instalados:
        return None
    if preferido in instalados:
        return preferido
    fam = (preferido or "").split(":")[0]
    misma = [m for m in instalados if m.split(":")[0] == fam]
    if misma:
        import re

        def tam(m):
            n = re.search(r":(\d+(?:\.\d+)?)b", m)
            return float(n.group(1)) if n else 7.0  # "latest" suele ser 7b
        return max(misma, key=tam)  # el más grande instalado = mejor calidad
    return instalados[0]

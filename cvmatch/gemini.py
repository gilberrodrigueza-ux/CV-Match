"""Gemini SIN búsqueda web (capa gratis de Google). Se usa solo para tareas donde el texto ya se lo damos:
leer resultados de Tavily, evaluar el match de ofertas y comparar requisitos con tus respuestas guardadas.
Nunca para buscar ofertas (sin búsqueda inventaría puestos)."""
import json
import time

import requests

from .llm import extract_json, reparar_json

URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
PREFERIDOS = ["gemini-flash-lite-latest", "gemini-flash-latest"]
_CACHE = {}
_BLOQUEO = [0.0]  # si Google responde "sin cuota", se descansa 15 min


def clave():
    from .buscador_web import get_key
    return get_key("gemini")


def disponible():
    return bool(clave()) and time.time() - _BLOQUEO[0] > 900


def modelos(k):
    if k in _CACHE:
        return _CACHE[k]
    nombres = []
    try:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", params={"pageSize": 200},
                         headers={"x-goog-api-key": k}, timeout=30)
        if r.status_code == 200:
            for m in r.json().get("models", []):
                n = m.get("name", "").replace("models/", "")
                if "generateContent" in (m.get("supportedGenerationMethods") or []) and "flash" in n \
                        and not any(x in n for x in ("image", "tts", "audio", "live", "embedding", "thinking")):
                    nombres.append(n)
    except Exception:
        pass
    nombres.sort(key=lambda n: (("preview" in n or "exp" in n), "lite" not in n, n))
    out = list(dict.fromkeys(PREFERIDOS + nombres))
    _CACHE[k] = out
    return out


def ask_json(system, user, timeout=120):
    """Devuelve un dict (JSON). Lanza RuntimeError si no hay clave, cuota o respuesta válida."""
    k = clave()
    if not k:
        raise RuntimeError("sin clave de Gemini")
    if not disponible():
        raise RuntimeError("Gemini sin cuota (descanso de 15 min)")
    errores = []
    for m in modelos(k)[:6]:
        r = requests.post(URL.format(modelo=m), headers={"x-goog-api-key": k}, timeout=timeout, json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}})
        if r.status_code in (404, 429):
            errores.append(f"{m}: {r.status_code}")
            continue
        if r.status_code != 200:
            raise RuntimeError(f"Gemini respondió {r.status_code}: {r.text[:160]}")
        cand = (r.json().get("candidates") or [{}])[0]
        texto = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
        try:
            return json.loads(texto)
        except Exception:
            data = extract_json(texto) or reparar_json(texto)
            if data:
                return data
            raise RuntimeError("Gemini no devolvió JSON válido")
    if any(e.endswith("429") for e in errores):
        _BLOQUEO[0] = time.time()
    raise RuntimeError("Gemini: " + "; ".join(errores))

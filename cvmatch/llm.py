"""Cliente de Claude (API de Anthropic) con salida JSON robusta y búsqueda web opcional."""
import json
import re

WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}


class LLMError(RuntimeError):
    pass


def extract_json(text):
    """Extrae el objeto/arreglo JSON más grande de un texto."""
    if not text:
        raise LLMError("Respuesta vacía del modelo")
    fences = re.findall(r"```(?:json)?\s*(.*?)```", text, re.S)
    for chunk in reversed(fences):
        try:
            return json.loads(chunk.strip())
        except Exception:
            pass
    dec = json.JSONDecoder()
    best, best_len = None, 0
    for i, ch in enumerate(text):
        if ch in "{[":
            try:
                obj, end = dec.raw_decode(text[i:])
                if end > best_len:
                    best, best_len = obj, end
            except Exception:
                continue
    if best is None:
        raise LLMError("No pude leer JSON en la respuesta del modelo")
    return best


def reparar_json(text):
    """Rescata un JSON cortado a la mitad: recorta hasta el último elemento completo y cierra llaves y corchetes."""
    if not text or "{" not in text:
        return None
    s = text[text.index("{"):]
    s = re.sub(r"```\s*$", "", s)
    cortes = [i for i, ch in enumerate(s) if ch in ",}]"]
    for fin in reversed(cortes[-400:]):
        trozo = s[:fin + 1] if s[fin] in "}]" else s[:fin]
        pila, en_cadena, escape = [], False, False
        for ch in trozo:
            if en_cadena:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    en_cadena = False
            elif ch == '"':
                en_cadena = True
            elif ch in "{[":
                pila.append("}" if ch == "{" else "]")
            elif ch in "}]":
                if not pila:
                    break
                pila.pop()
        if en_cadena:
            continue
        try:
            obj = json.loads(trozo + "".join(reversed(pila)))
            if isinstance(obj, dict) and obj:
                obj["_respuesta_recortada"] = True
                return obj
        except Exception:
            continue
    return None


class LLM:
    def __init__(self, api_key, modelo_analisis, modelo_redaccion):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key, max_retries=4, timeout=900)
        self.modelo_analisis = modelo_analisis
        self.modelo_redaccion = modelo_redaccion
        self.cfg = None  # se asigna desde la app para aplicar el tope de presupuesto

    def _call(self, system, user, model, max_tokens, tools=None):
        messages = [{"role": "user", "content": user}]
        texts, stop = [], None
        for _ in range(6):
            kwargs = dict(model=model, max_tokens=max_tokens, system=system, messages=messages)
            if tools:
                kwargs["tools"] = tools
            with self.client.messages.stream(**kwargs) as s:
                resp = s.get_final_message()
            try:
                from . import gasto
                gasto.registrar(model, resp.usage, gasto.etiqueta(system))
            except Exception:
                pass
            for b in resp.content:
                if getattr(b, "type", "") == "text":
                    texts.append(b.text)
            stop = resp.stop_reason
            if stop == "pause_turn":
                messages = messages + [{"role": "assistant", "content": resp.content}]
                continue
            break
        return "".join(texts), stop

    def ask_json(self, system, user, redaccion=False, max_tokens=8000, web=False, modelo=None, max_busquedas=None):
        if self.cfg:
            from . import gasto
            gasto.verificar_presupuesto(self.cfg)
        model = modelo or (self.modelo_redaccion if redaccion else self.modelo_analisis)
        tools = [dict(WEB_SEARCH_TOOL, max_uses=max_busquedas or WEB_SEARCH_TOOL["max_uses"])] if web else None
        text, stop = self._call(system, user, model, max_tokens, tools)
        if stop == "max_tokens":
            # Se cortó por largo: primero se rescata lo útil (gratis); solo si no se puede, UN reintento breve
            rescate = reparar_json(text)
            if rescate is not None:
                return rescate
            breve = (user + "\n\nIMPORTANTE: tu respuesta anterior fue demasiado larga y se cortó. Devuelve el MISMO "
                     "JSON pero breve: máximo 12 elementos por lista y frases de máximo 20 palabras.")
            text, stop = self._call(system, breve, model, max_tokens, tools)
            return extract_json(text) if stop != "max_tokens" else (reparar_json(text) or extract_json(text))
        try:
            return extract_json(text)
        except LLMError:
            fix = (user + "\n\nIMPORTANTE: tu respuesta anterior no era JSON válido. "
                   "Devuelve ÚNICAMENTE el JSON pedido, sin texto adicional.")
            text, _ = self._call(system, fix, model, max_tokens, tools)
            return extract_json(text)

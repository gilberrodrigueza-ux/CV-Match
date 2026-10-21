"""Flujo completo por oferta: análisis → preguntas → reescritura XYZ → escaneo ATS → auditoría → DOCX/reporte/historial."""
import json
import re
import unicodedata
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from . import history, jobs, prompts, trainings
from . import estilo, gasto
from .config import DATA_DIR, modelo_tarea
from .docx_builder import build_cover_docx, build_docx, count_pdf_pages, fit_pages, try_pdf
from .report import job_report, skills_report

JD_DIR = DATA_DIR / "ofertas"
RESULTS_PATH = DATA_DIR / "ultima_busqueda.json"


def load_results():
    try:
        return [j for j in json.loads(RESULTS_PATH.read_text(encoding="utf-8")) if j.get("url")]
    except Exception:
        return []


def safe_name(s, maxlen=60, ascii_only=False):
    if ascii_only:
        s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = re.sub(r'[<>:"/\\|?*\n\r\t]+', " ", s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return (s[:maxlen].strip() or "Sin_nombre")


def company_folder(base, empresa):
    """Usa la carpeta existente de la empresa si ya existe (sin importar mayúsculas)."""
    name = safe_name(empresa, 50)
    if base.exists():
        for d in base.iterdir():
            if d.is_dir() and d.name.lower() == name.lower():
                return d
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    return d


CRITERIO = 2  # versión del criterio de match (sube cuando cambia la rúbrica, para re-evaluar lo guardado)


class Pipeline:
    def __init__(self, cfg, llm, facts, cv_text, ui):
        self.cfg, self.llm, self.facts, self.cv, self.ui = cfg, llm, facts, cv_text, ui
        self.respuestas_usadas = []

    # ---------- búsqueda ----------
    WEB_AREAS = DATA_DIR / "ultima_busqueda_web_areas.json"

    def _web_areas_ts(self):
        try:
            return json.loads(self.WEB_AREAS.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def web_disponible(self, area=None):
        """(se puede, horas desde la última búsqueda web). Con area, se mide por área."""
        if area:
            ts = self._web_areas_ts().get(area)
            if not ts:
                return True, None
            horas = (datetime.now() - datetime.fromisoformat(ts)).total_seconds() / 3600
            return horas >= float(self.cfg.get("horas_entre_busquedas_web", 6)), horas
        f = DATA_DIR / "ultima_busqueda_web.txt"
        try:
            ult = datetime.fromisoformat(f.read_text(encoding="utf-8").strip())
        except Exception:
            return True, None
        horas = (datetime.now() - ult).total_seconds() / 3600
        return horas >= float(self.cfg.get("horas_entre_busquedas_web", 6)), horas

    def costo_web_estimado(self, n_areas):
        """USD aproximados si se usara Claude (Tavily+Ollama y Gemini en su cuota gratis cuestan 0)."""
        b = int(self.cfg["busqueda"].get("busquedas_web_por_area", 2))
        return n_areas * (b * 0.01 + 0.006)

    def search(self, extra_keywords, forzar_web=False, areas_web=None, recientes_h=None):
        """Busca POR ÁREA: cada área tiene su propia búsqueda y su propio cupo de ofertas a evaluar.
        areas_web = nombres de áreas para la búsqueda web (None = todas).
        recientes_h = solo ofertas publicadas en las últimas N horas (las que no traen fecha se conservan)."""
        from . import calidad
        ui = self.ui
        areas = jobs.areas_config(self.cfg, extra_keywords)
        b = self.cfg["busqueda"]
        cfg_bolsas = self.cfg
        if b.get("apagar_fuentes_sin_rendimiento", True):
            apagadas = calidad.bolsas_sin_rendimiento()
            if apagadas:
                ui.info(f"  Bolsas omitidas por no aportar ofertas útiles en las últimas búsquedas: {', '.join(apagadas)}")
                cfg_bolsas = {**self.cfg, "busqueda": {**b, "fuentes_remotas": [f for f in b["fuentes_remotas"] if f not in apagadas]}}
        ui.info(f"Buscando por área ({len(areas)} áreas) en bolsas remotas...")
        found = jobs.fetch_remote_jobs(cfg_bolsas, extra_keywords, ui.info)
        if b.get("usar_portales", True):
            from . import portales
            ui.info("Revisando portales de empleo de empresas (sin IA)...")
            try:
                found = portales.leer_todos(self.cfg, ui.info) + found
            except Exception as e:
                ui.warn(f"  Portales: {e}")
        if self.cfg["busqueda"].get("buscar_costa_rica_con_ia"):
            elegidas = [a for a in areas if areas_web is None or a["nombre"] in areas_web]
            ts = self._web_areas_ts()
            nb = int(self.cfg["busqueda"].get("busquedas_web_por_area", 2))
            for a in elegidas:
                ok, horas = self.web_disponible(a["nombre"])
                if not ok and not forzar_web:
                    ui.info(f"  Web · {a['nombre']}: omitida (se buscó hace {horas:.1f} h; sus ofertas siguen en tu lista)")
                    continue
                from . import buscador_web
                # si el área se buscó hace poco, basta con lo publicado en la última semana (menos ruido)
                buscador_web.RANGO_TIEMPO[0] = "week" if (horas is not None and horas < 72) else "month"
                try:
                    cr, prov = buscador_web.buscar_area(self.cfg, self.llm, a, self.cv[:3000], ui.info)
                    ui.info(f"  Web · {a['nombre']}: {len(cr)} ofertas ({prov})")
                    found = cr + found
                    ts[a["nombre"]] = datetime.now().isoformat(timespec="seconds")
                    self.WEB_AREAS.write_text(json.dumps(ts, indent=2, ensure_ascii=False), encoding="utf-8")
                    (DATA_DIR / "ultima_busqueda_web.txt").write_text(datetime.now().isoformat(), encoding="utf-8")
                except gasto.PresupuestoAgotado as e:
                    ui.warn(f"  {e}")
                    break
                except buscador_web.SinProveedor as e:
                    ui.warn(f"  Búsqueda web detenida: ningún buscador disponible ({e})")
                    break
                except Exception as e:
                    ui.warn(f"  Web · {a['nombre']}: no disponible ({e})")
        if self.cfg["busqueda"].get("buscar_costa_rica_con_ia") and self.cfg.get("buscar_en_favoritas"):
            _, horas_f = self.web_disponible("⭐ favoritas")
            if horas_f is None or horas_f >= 24 or forzar_web:  # una vez al día (~5 créditos de Tavily)
                try:
                    from . import buscador_web
                    fav = buscador_web.buscar_favoritas(self.cfg, self.llm, ui.info)
                    ui.info(f"  Web · ⭐ Empresas favoritas: {len(fav)} ofertas")
                    found = fav + found
                    ts = self._web_areas_ts()
                    ts["⭐ favoritas"] = datetime.now().isoformat(timespec="seconds")
                    self.WEB_AREAS.write_text(json.dumps(ts, indent=2, ensure_ascii=False), encoding="utf-8")
                except Exception as e:
                    ui.warn(f"  Web · ⭐ Empresas favoritas: no disponible ({str(e)[:120]})")
        antes = len(found)
        found = jobs.dedupe(found)
        if len(found) < antes:
            ui.info(f"  {antes - len(found)} duplicadas (misma oferta en varias fuentes) se unieron")
        n0 = len(found)
        found = [j for j in found if not calidad.es_descartada(j)]
        if len(found) < n0:
            ui.info(f"  {n0 - len(found)} que marcaste «No me interesa» no se vuelven a mostrar")
        if recientes_h:
            from . import extras as _ex
            n0 = len(found)
            found = [j for j in found if _ex.dias_publicada(j) is None or _ex.dias_publicada(j) * 24 <= recientes_h]
            ui.info(f"  Solo lo publicado en las últimas {recientes_h} h: {n0 - len(found)} más antiguas se omiten")
        # quitar las que ya están en el historial (mismo link, o misma empresa + puesto)
        nuevas = [j for j in found if not history.find_by_url(j["url"])
                  and not history.find_similar(j.get("empresa"), j.get("puesto"))]
        if len(nuevas) < len(found):
            ui.info(f"  {len(found) - len(nuevas)} ya estaban en tu historial y se omiten")
        previas = {j["url"]: j for j in load_results()}
        # reutilizar la puntuación de ofertas ya evaluadas (no se vuelve a pagar por ellas)
        por_rankear = []
        for j in nuevas:
            p = previas.get(j["url"])
            if p and p.get("match_estimado"):  # 0 o vacío = falló la evaluación; se reintenta
                for k in ("match_estimado", "elegible_cr", "motivo", "encontrada"):
                    j[k] = p.get(k)
            else:
                por_rankear.append(j)
        # cupo POR ÁREA (para que un área con muchas ofertas no tape a las demás)
        por_rankear = jobs.repartir_por_area(por_rankear, areas, int(self.cfg["busqueda"].get("max_por_area", 8)))
        ui.info(f"  A evaluar: {len(por_rankear)} ofertas nuevas (hasta "
                f"{self.cfg['busqueda'].get('max_por_area', 8)} por área)")
        self._rankear_lotes(por_rankear)
        try:
            calidad.registrar_rendimiento([j for j in por_rankear if j.get("match_estimado")])
        except Exception:
            pass
        res = self.merge_results([j for j in nuevas if "match_estimado" in j], set(previas))
        try:
            from . import portales
            nuevos = portales.descubrir(load_results(), self.cfg)
            if nuevos:
                ui.info(f"  Portales descubiertos (se revisarán directo desde ahora): {', '.join(nuevos)}")
        except Exception:
            pass
        try:
            from . import extras as _ex
            n = _ex.enviar_resumen(self.cfg, load_results(), ui.info)
        except Exception as e:
            ui.warn(f"  Resumen diario no enviado: {str(e)[:160]}")
        return res

    def _rankear_lotes(self, por_rankear):
        ui = self.ui
        self._ollama_model = None
        oc = self.cfg.get("ollama") or {}
        if por_rankear and oc.get("usar_para_evaluar_ofertas"):
            from . import ollama
            ok, instalados = ollama.disponible(oc.get("url", "http://localhost:11434"))
            self._ollama_model = ollama.elegir_modelo(oc.get("modelo", ""), instalados) if ok else None
            if self._ollama_model:
                ui.info(f"Usando Ollama ({self._ollama_model}) en tu PC para evaluar ofertas (sin costo)")
            else:
                ui.info("Ollama no está abierto; evalúo con Gemini (gratis) o, si no hay cuota, Claude (Haiku)")
        if por_rankear:
            ui.info(f"Evaluando el match de {len(por_rankear)} ofertas nuevas contra tu CV...")
        else:
            ui.info("No hay ofertas nuevas que evaluar.")
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
        for i in range(0, len(por_rankear), 10):
            lote = por_rankear[i:i + 10]
            listado = "\n\n".join(
                f"[id {k}] {j['puesto']} — {j['empresa']} — Ubicación: {j['ubicacion']}\n{j['descripcion'][:1500]}"
                for k, j in enumerate(lote))
            from . import calidad
            user = prompts.PROMPT_RANKING.format(cv=self.cv[:4000], hechos=self.facts.as_text(), ofertas=listado,
                                                 preferencias=calidad.preferencias_texto(),
                                                 perfil_objetivo=self.cfg.get("perfil_objetivo", ""))
            try:
                self._aplicar_ranking(self._rank(user), lote, ahora)
                # Ollama a veces devuelve 0 o se salta ofertas (sobre todo las de descripción corta):
                # si pasa con la mitad del lote o más, se repite el lote con Claude (Haiku, centavos)
                malas = [j for j in lote if not j.get("match_estimado")]
                if self._ollama_model and len(malas) * 2 >= len(lote):
                    ui.info(f"  Ollama no evaluó bien {len(malas)} de {len(lote)}; las reviso con Gemini (o Haiku)")
                    self._aplicar_ranking(self._rank_gemini_o_claude(user), lote, ahora)
            except Exception as e:
                ui.warn(f"  No pude rankear un lote: {e}")
            for j in lote:  # las que sigan sin puntaje no se pierden: quedan como "sin evaluar"
                if not j.get("match_estimado"):
                    j["match_estimado"] = None
                    j["sin_evaluar"] = True
                    j.setdefault("encontrada", ahora)

    def reevaluar_todas(self):
        """Aplica el criterio nuevo a la lista guardada: quita perfiles excluidos, recalcula áreas y vuelve a evaluar
        el match (Ollama/Gemini: gratis)."""
        validas = self.cfg["busqueda"]["ubicaciones_remotas_validas"] + ["remote", "remoto"]
        areas = jobs.areas_config(self.cfg)
        antes = load_results()
        todas = [j for j in antes
                 if jobs.location_ok(j.get("ubicacion", ""), validas, j.get("descripcion", "")) is not False
                 and not jobs.titulo_excluido(j.get("puesto"), self.cfg)]
        for j in todas:
            j["areas"] = jobs.areas_de_oferta(j, areas) or j.get("areas") or []
            j["match_estimado"] = None
        self.ui.info(f"Quité {len(antes) - len(todas)} ofertas de perfiles que no buscas o fuera de Costa Rica; "
                     f"re-evalúo {len(todas)}.")
        self._rankear_lotes(todas)
        todas.sort(key=lambda j: (j.get("match_estimado") or 0), reverse=True)
        RESULTS_PATH.write_text(json.dumps(todas, indent=2, ensure_ascii=False), encoding="utf-8")
        return len(antes) - len(todas), len(todas)

    def evaluar_sin_puntaje(self):
        """Vuelve a evaluar las ofertas guardadas que quedaron sin match (o en 0) y guarda la lista."""
        validas = self.cfg["busqueda"]["ubicaciones_remotas_validas"] + ["remote", "remoto"]
        todas = [j for j in load_results()
                 if jobs.location_ok(j.get("ubicacion", ""), validas, j.get("descripcion", "")) is not False]
        pend = [j for j in todas if not j.get("match_estimado")][: self.cfg["max_ofertas_a_rankear"]]
        if not pend:
            self.ui.info("No hay ofertas sin evaluar.")
            return 0
        self._rankear_lotes(pend)
        todas.sort(key=lambda j: (j.get("match_estimado") or 0), reverse=True)
        RESULTS_PATH.write_text(json.dumps(todas, indent=2, ensure_ascii=False), encoding="utf-8")
        listas = sum(1 for j in pend if j.get("match_estimado"))
        self.ui.info(f"Evaluadas {listas} de {len(pend)} ofertas que estaban sin match.")
        return listas

    @staticmethod
    def _aplicar_ranking(data, lote, ahora):
        for r in (data or {}).get("ranking", []):
            try:
                k = int(r.get("id", -1))
                punt = int(float(r.get("puntuacion") or 0))
                partes = [r.get("tipo_rol"), r.get("tecnologias"), r.get("seniority")]
                if all(isinstance(x, (int, float)) for x in partes):  # la rúbrica manda: suma con topes
                    punt = int(round(min(40, max(0, partes[0])) + min(40, max(0, partes[1])) + min(20, max(0, partes[2]))))
            except (TypeError, ValueError):
                continue
            if 0 <= k < len(lote) and punt > 0:
                lote[k]["match_estimado"] = punt
                lote[k]["sin_evaluar"] = False
                lote[k]["criterio"] = CRITERIO
                lote[k]["elegible_cr"] = r.get("elegible_cr")
                lote[k]["motivo"] = r.get("motivo", "")
                lote[k]["encontrada"] = ahora

    def _rank(self, user):
        """Evalúa un lote: Ollama local si está activado (gratis); si falla, Claude (Haiku por defecto)."""
        oc = self.cfg.get("ollama") or {}
        modelo = getattr(self, "_ollama_model", None)
        if modelo:
            try:
                from . import ollama
                data = ollama.ask_json(prompts.SYSTEM_RANKER, user, modelo, oc.get("url", "http://localhost:11434"))
                if data.get("ranking"):
                    return data
                raise ValueError("respuesta sin ranking")
            except Exception as e:
                self.ui.warn(f"  Ollama no respondió ({e.__class__.__name__}); pruebo con Gemini")
        return self._rank_gemini_o_claude(user)

    def _rank_gemini_o_claude(self, user):
        """Gemini sin búsqueda (gratis) y, si no hay cuota o clave, Claude Haiku."""
        from . import gemini
        if gemini.disponible():
            try:
                data = gemini.ask_json(prompts.SYSTEM_RANKER, user)
                if data.get("ranking"):
                    self._usado_gemini = True
                    return data
            except Exception as e:
                self.ui.warn(f"  Gemini no pudo evaluar ({str(e)[:80]}); uso Claude (Haiku)")
        return self.llm.ask_json(prompts.SYSTEM_RANKER, user, max_tokens=4000, modelo=modelo_tarea(self.cfg, "ranking"))

    def merge_results(self, actuales, urls_previas):
        """Une resultados nuevos con los anteriores (14 días), marca las nuevas y guarda."""
        limite = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
        vistos = {j["url"] for j in actuales}
        for j in actuales:
            j["nueva"] = j["url"] not in urls_previas
        for p in load_results():
            if p["url"] in vistos or history.find_by_url(p["url"]):
                continue
            if (p.get("encontrada") or "")[:10] >= limite:
                p["nueva"] = False
                actuales.append(p)
        todas = [j for j in actuales if j.get("elegible_cr") is not False and j.get("elegible_ubicacion") is not False
                 and not jobs.titulo_excluido(j.get("puesto"), self.cfg)
                 and jobs.location_ok(j.get("ubicacion", ""), self.cfg["busqueda"]["ubicaciones_remotas_validas"]
                                      + ["remote", "remoto"], j.get("descripcion", "")) is not False]
        areas_cfg = jobs.areas_config(self.cfg)
        from . import calidad
        todas = [j for j in todas if not calidad.es_descartada(j)]
        for j in todas:
            if not j.get("areas"):
                j["areas"] = jobs.areas_de_oferta(j, areas_cfg)
        if self.cfg["busqueda"].get("verificar_vigencia", True):
            try:
                orden = sorted(todas, key=lambda j: (j.get("match_estimado") or 0), reverse=True)
                calidad.verificar_vigencia(orden, self.ui.info)
                todas = [j for j in todas if j.get("cerrada") is not True]
            except Exception as e:
                self.ui.warn(f"  Vigencia: no se pudo revisar ({e.__class__.__name__})")
        todas.sort(key=lambda j: (j.get("match_estimado") or 0), reverse=True)
        # se guardan TODAS las evaluadas; el match mínimo es solo un filtro de vista
        RESULTS_PATH.write_text(json.dumps(todas, indent=2, ensure_ascii=False), encoding="utf-8")
        minimo = self.cfg["puntaje_minimo_mostrar"]
        res = [j for j in todas if (j.get("match_estimado") or 0) >= minimo or not j.get("match_estimado")]
        sin = sum(1 for j in todas if not j.get("match_estimado"))
        self.ui.info(f"Resultado: {len(todas)} ofertas válidas desde Costa Rica en tu lista · {len(res) - sin} con match ≥ {minimo}"
                     + (f" · {sin} sin evaluar (se muestran igual)" if sin else "")
                     + " (las demás quedan guardadas; baja el match mínimo para verlas)")
        return res

    # ---------- etapas (usadas por la consola y la interfaz gráfica) ----------
    def get_jd(self, job):
        """Devuelve el texto del JD (descarga el link si hace falta). Puede venir corto si el sitio bloquea."""
        jd = job.get("descripcion", "") or ""
        if len(jd) < 1200 and job.get("url"):
            full = jobs.fetch_jd_text(job["url"])
            if len(full) > len(jd):
                jd = full
        return jd

    @staticmethod
    def _suma(desglose, actual):
        """Aplica la rúbrica: la puntuación es la suma del desglose (si viene completo)."""
        try:
            lim = {"obligatorios": 50, "deseables": 20, "seniority": 15, "industria": 15}
            total = sum(max(0, min(lim[k], float(desglose.get(k, 0)))) for k in lim)
            return int(round(total)) if desglose else actual
        except Exception:
            return actual

    def analyze(self, jd):
        a = self.llm.ask_json(prompts.SYSTEM_RECLUTADOR, prompts.PROMPT_ANALISIS.format(
            jd=jd[:12000], cv=self.cv, hechos=self.facts.as_text()), max_tokens=6000)
        if a.get("desglose_puntuacion"):
            a["puntuacion_match"] = self._suma(a["desglose_puntuacion"], a.get("puntuacion_match"))
        return a

    def eliminatorios_fallidos(self, a):
        return [e for e in a.get("requisitos_eliminatorios", []) or [] if e.get("cumple") == "no"]

    def research_company(self, empresa, puesto, jd):
        """Contexto breve de la empresa (búsqueda web, con caché por empresa)."""
        if not self.cfg.get("investigar_empresa", True) or not empresa:
            return {}
        cache_f = DATA_DIR / "empresas.json"
        try:
            cache = json.loads(cache_f.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
        k = history.clave(empresa, "")
        if k in cache:
            return cache[k]
        try:
            info = self.llm.ask_json(prompts.SYSTEM_EMPRESA, prompts.PROMPT_EMPRESA.format(
                empresa=empresa, puesto=puesto, jd=jd[:2500]), max_tokens=2500, web=True,
                modelo=modelo_tarea(self.cfg, "empresa"))
        except Exception:
            return {}
        cache[k] = info
        cache_f.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
        return info

    def _linkedin(self):
        try:
            t = (DATA_DIR / "linkedin.txt").read_text(encoding="utf-8").strip()
            return t[:8000] or "(no proporcionado)"
        except Exception:
            return "(no proporcionado)"

    def _idiomas(self):
        v = (self.cfg.get("idiomas_declarados") or "").strip()
        return (f"\n- EXCEPCIÓN: en la línea de contacto, los idiomas deben declararse EXACTAMENTE así: \"{v}\" "
                "(el candidato lo definió).") if v else ""

    def reanalyze(self, jd, a):
        """Recalcula requisitos con las respuestas nuevas; el match inicial queda como el del CV tal cual."""
        a2 = self.analyze(jd)
        for k in ("puntuacion_match", "palabras_clave_faltantes", "red_flags", "justificacion_puntuacion"):
            a2[k] = a.get(k)
        return a2

    def pending_gaps(self, analysis):
        pendientes = []
        for r in analysis.get("requisitos", []):
            if r.get("estado") not in ("no_aparece", "parcial"):
                continue
            nombre = r.get("habilidad_corta") or r.get("requisito", "")
            if not nombre or self.facts.find(nombre):
                continue
            if any(nombre.lower() == p["nombre"].lower() for p in pendientes):
                continue
            pendientes.append({"nombre": nombre, "requisito": r.get("requisito", ""), "tipo": r.get("tipo", ""),
                               "pregunta": r.get("pregunta_para_candidato") or f"¿Tienes experiencia con {nombre}?"})
        for kw in analysis.get("palabras_clave_faltantes", []):
            if kw and not self.facts.find(kw) and all(kw.lower() != p["nombre"].lower() for p in pendientes):
                pendientes.append({"nombre": kw, "requisito": kw, "tipo": "palabra clave",
                                   "pregunta": f"¿Tienes experiencia con {kw}?"})
        # Antes de preguntarte: ¿alguna respuesta guardada ya cubre estos requisitos (por significado)?
        self.respuestas_usadas = []
        if pendientes and self.facts.items:
            pendientes, self.respuestas_usadas = self._usar_respuestas_previas(pendientes)
        return pendientes

    def _ia_barata(self, system, user, max_tokens=2500):
        """Ollama local (gratis); si no, Gemini sin búsqueda (gratis); si no, Claude Haiku."""
        oc = self.cfg.get("ollama") or {}
        if oc.get("usar_para_evaluar_ofertas"):
            try:
                from . import ollama
                ok, inst = ollama.disponible(oc.get("url", "http://localhost:11434"))
                mod = ollama.elegir_modelo(oc.get("modelo", ""), inst) if ok else None
                if mod:
                    return ollama.ask_json(system, user, mod, oc.get("url", "http://localhost:11434"), timeout=300)
            except Exception:
                pass
        from . import gemini
        if gemini.disponible():
            try:
                return gemini.ask_json(system, user)
            except Exception:
                pass
        if not self.llm:
            return {}
        return self.llm.ask_json(system, user, max_tokens=max_tokens, modelo=modelo_tarea(self.cfg, "ranking"))

    def refrasear(self, texto, requisito, pregunta, nivel):
        """Mejora la redacción de una respuesta sin agregar datos (Ollama → Gemini → Haiku)."""
        data = self._ia_barata(prompts.SYSTEM_REFRASEO, prompts.PROMPT_REFRASEO.format(
            requisito=requisito, pregunta=pregunta, nivel=nivel, texto=texto[:3000]), max_tokens=800) or {}
        nuevo = (data.get("texto") or "").strip()
        falta = [f for f in (data.get("falta") or []) if isinstance(f, str) and f.strip()][:3]
        return nuevo, falta

    def _usar_respuestas_previas(self, pendientes):
        nombres = {f["habilidad"]: f for f in self.facts.items}
        lista_hechos = "\n".join(f"- {f['habilidad']} | {f['tiene']} | {f.get('detalle', '')[:160]}" for f in self.facts.items)
        lista_req = "\n".join(f"- {p['nombre']} (requisito: {p['requisito']})" for p in pendientes)
        try:
            data = self._ia_barata(prompts.SYSTEM_COINCIDENCIAS,
                                   prompts.PROMPT_COINCIDENCIAS.format(requisitos=lista_req, hechos=lista_hechos))
        except Exception:
            return pendientes, []
        por_req = {}
        for c in data.get("coincidencias", []) or []:
            hecho = (c.get("hecho") or "").strip()
            if c.get("cubre") in ("si", "parcial", "no_tiene") and hecho in nombres:  # solo respuestas que existen
                por_req[(c.get("requisito") or "").strip().lower()] = c
        quedan, usadas = [], []
        for p in pendientes:
            c = por_req.get(p["nombre"].strip().lower())
            if c:
                usadas.append({"requisito": p["nombre"], "hecho": c["hecho"], "cubre": c["cubre"],
                               "motivo": c.get("motivo", ""), "tiene": nombres[c["hecho"]]["tiene"]})
            else:
                quedan.append(p)
        return quedan, usadas

    def generate(self, job, jd, a, progress=lambda m: None):
        """Reescritura XYZ → ATS/100 CVs → auditoría → DOCX, reporte e historial. Devuelve un dict con todo."""
        job["empresa"] = a.get("empresa") or job.get("empresa") or "Empresa"
        job["puesto"] = a.get("puesto") or job.get("puesto") or "Puesto"
        idioma = "español" if a.get("idioma_jd") == "es" else "inglés"
        lang = "es" if a.get("idioma_jd") == "es" else "en"

        empresa_info = {}
        if self.cfg.get("investigar_empresa", True):
            progress("Investigando la empresa para saber qué priorizar...")
            empresa_info = self.research_company(job["empresa"], job["puesto"], jd)
        progress("Reescribiendo tu experiencia con la fórmula XYZ (sin inventar)...")
        rw = self.llm.ask_json(prompts.SYSTEM_REDACTOR, prompts.PROMPT_REESCRITURA.format(
            jd=jd, keywords=", ".join(a.get("palabras_clave_faltantes", [])),
            redflags=json.dumps(a.get("red_flags", []), ensure_ascii=False),
            sugerencias=json.dumps(a.get("sugerencias_para_subir_match", []), ensure_ascii=False),
            cv=self.cv, hechos=self.facts.as_text(), idioma=idioma,
            paginas=self.cfg["max_paginas_cv"], esquema=prompts.ESQUEMA_CV, muestra=self._muestra(),
            contexto_empresa=json.dumps(empresa_info, ensure_ascii=False) if empresa_info else "(sin datos)",
            idiomas=self._idiomas()),
            redaccion=True, max_tokens=12000)

        progress("Escaneando como filtro ATS y como reclutador que lee 100 CVs...")
        sc = self.llm.ask_json(prompts.SYSTEM_ESCANER, prompts.PROMPT_ESCANEO.format(
            jd=jd, cv_json=json.dumps(rw["cv"], ensure_ascii=False), cv=self.cv, hechos=self.facts.as_text(),
            esquema=prompts.ESQUEMA_CV), redaccion=True, max_tokens=12000)

        progress("Auditando que nada sea inventado y puntuando el CV final...")
        vf = self.llm.ask_json(prompts.SYSTEM_VERIFICADOR, prompts.PROMPT_VERIFICACION.format(
            cv=self.cv, hechos=self.facts.as_text(), cv_json=json.dumps(sc.get("cv") or rw["cv"], ensure_ascii=False),
            jd=jd, esquema=prompts.ESQUEMA_CV, linkedin=self._linkedin()), redaccion=True, max_tokens=12000)
        if vf.get("desglose_final"):
            vf["puntuacion_match_final"] = self._suma(vf["desglose_final"], vf.get("puntuacion_match_final"))
        cv_final = vf.get("cv") or sc.get("cv") or rw["cv"]

        # Estilo humano: detector local; solo si hay marcas, una pasada corta de pulido
        marcas = estilo.detectar(cv_final)
        info_estilo = {"detectadas": len(marcas), "corregidas": 0, "restantes": [], "cambios": []}
        if marcas:
            progress(f"Puliendo {len(marcas)} línea(s) que sonaban a IA...")
            try:
                lineas = "\n".join(f"- {m['texto']}\n  (marcas: {', '.join(m['marcas'])})" for m in marcas)
                pl = self.llm.ask_json(prompts.SYSTEM_PULIDO, prompts.PROMPT_PULIDO.format(
                    idioma=idioma, lineas=lineas, cv=self.cv, hechos=self.facts.as_text()),
                    max_tokens=4000, modelo=modelo_tarea(self.cfg, "pulido_estilo"))
                cambios = pl.get("cambios", [])
                cv_final = estilo.aplicar(cv_final, cambios)
                info_estilo["cambios"] = cambios
            except Exception as e:
                progress(f"(No se pudo pulir el estilo: {e})")
        restantes = estilo.detectar(cv_final)
        info_estilo["restantes"] = restantes
        info_estilo["corregidas"] = max(0, len(marcas) - len(restantes))

        progress("Generando el CV, el reporte y el registro en el historial...")
        hoy = date.today().isoformat()
        folder = company_folder(self.cfg["_salida_path"], job["empresa"])
        apellido = safe_name(cv_final.get("nombre", "CV"), ascii_only=True).replace(" ", "_")
        base = f"CV_{apellido}_{safe_name(job['puesto'], 45, ascii_only=True).replace(' ', '_')}_{hoy}"
        docx_path = folder / f"{base}.docx"
        k = 2
        while docx_path.exists():
            docx_path = folder / f"{base}_v{k}.docx"
            k += 1
        maxp = int(self.cfg["max_paginas_cv"])
        cv_final, recortes = fit_pages(cv_final, maxp)
        build_docx(cv_final, docx_path, lang)
        pdf_path = try_pdf(docx_path) if self.cfg.get("generar_pdf") else None
        paginas = count_pdf_pages(pdf_path)
        intentos = 0
        while paginas and paginas > maxp and intentos < 3:
            cv_final, mas = fit_pages(cv_final, maxp, forzar=True)
            if not mas:
                break
            recortes += mas
            build_docx(cv_final, docx_path, lang)
            pdf_path = try_pdf(docx_path)
            paginas = count_pdf_pages(pdf_path)
            intentos += 1
        if recortes:
            progress(f"Ajusté el largo a {maxp} página(s): quité {len(recortes)} bullet(s) de menor relevancia.")

        entrevista = {}
        if self.cfg.get("preparar_entrevista", True):
            progress("Preparando preguntas probables de entrevista (STAR)...")
            try:
                entrevista = self.llm.ask_json(prompts.SYSTEM_ENTREVISTA, prompts.PROMPT_ENTREVISTA.format(
                    jd=jd, cv_json=json.dumps(cv_final, ensure_ascii=False), cv=self.cv, hechos=self.facts.as_text()),
                    max_tokens=6000)
            except Exception as e:
                progress(f"(No se pudo preparar la entrevista: {e})")

        JD_DIR.mkdir(parents=True, exist_ok=True)
        jd_path = JD_DIR / f"{hoy}_{safe_name(job['empresa'], 30)}_{safe_name(job['puesto'], 40)}.txt".replace(" ", "_")
        jd_path.write_text(f"{job.get('url', '')}\n\n{jd}", encoding="utf-8")

        faltan = list(dict.fromkeys(
            a.get("palabras_clave_faltantes", []) +
            [x.get("palabra", "") for x in rw.get("palabras_clave_no_incluidas", [])]))
        tr = {kw: trainings.trainings_for(kw) for kw in faltan if kw}
        rep_path = docx_path.with_name(docx_path.stem.replace("CV_", "Reporte_", 1) + ".html")
        extras = {"areas": job.get("areas") or [], "eliminatorios": a.get("requisitos_eliminatorios", []), "empresa": empresa_info,
                  "entrevista": entrevista, "linkedin": vf.get("discrepancias_linkedin", []),
                  "desglose_inicial": a.get("desglose_puntuacion"), "desglose_final": vf.get("desglose_final"),
                  "paginas": paginas, "recortes": recortes, "idioma": lang}
        job_report(rep_path, job, a, rw, sc, vf, tr, {"docx": str(docx_path), "pdf": pdf_path}, info_estilo, extras)

        brechas = []
        for r in a.get("requisitos", []):
            if r.get("estado") in ("no_aparece", "parcial", "no_tiene_confirmado"):
                brechas.append({"habilidad": r.get("habilidad_corta") or r.get("requisito"),
                                "tipo": r.get("tipo", "deseable"), "estado": r.get("estado")})
        rid = history.add({
            "fecha": hoy, "empresa": job["empresa"], "puesto": job["puesto"], "url": job.get("url", ""),
            "ubicacion": a.get("ubicacion") or job.get("ubicacion", ""), "modalidad": a.get("modalidad", ""),
            "fuente": job.get("fuente", "Manual"), "match_inicial": a.get("puntuacion_match"),
            "match_final": vf.get("puntuacion_match_final"), "cv_docx": str(docx_path), "cv_pdf": pdf_path or "",
            "reporte": str(rep_path), "jd_path": str(jd_path), "estado": "Por aplicar",
            "palabras_faltantes": a.get("palabras_clave_faltantes", []), "brechas": brechas,
            "habilidades_jd": a.get("habilidades_jd", []), "extras": extras})
        (JD_DIR / f"cv_{rid}.json").write_text(json.dumps(cv_final, ensure_ascii=False, indent=2), encoding="utf-8")
        self.export_history()
        return {"id": rid, "analisis": a, "reescritura": rw, "escaneo": sc, "auditoria": vf, "cv": cv_final,
                "docx": str(docx_path), "pdf": pdf_path, "reporte": str(rep_path), "trainings": tr,
                "estilo": info_estilo, "extras": extras, "jd": jd}

    # ---------- banco de métricas ----------
    def metric_questions(self, regenerar=False):
        f = DATA_DIR / "preguntas_metricas.json"
        if f.exists() and not regenerar:
            return json.loads(f.read_text(encoding="utf-8"))
        data = self.llm.ask_json(prompts.SYSTEM_METRICAS, prompts.PROMPT_METRICAS.format(
            cv=self.cv, hechos=self.facts.as_text()), max_tokens=4000)
        preguntas = data.get("preguntas", [])
        f.write_text(json.dumps(preguntas, indent=2, ensure_ascii=False), encoding="utf-8")
        return preguntas

    def save_metric(self, pregunta, respuesta):
        nombre = f"Métrica: {pregunta.get('rol', '')} — {pregunta.get('logro', '')}".strip(" —:")
        self.facts.add(nombre, "si", respuesta.strip(), "Banco de métricas")

    # ---------- cover letter ----------
    def cover_letter(self, row):
        """Genera cover letter (DOCX) + mensaje LinkedIn para una solicitud del historial."""
        cvf = JD_DIR / f"cv_{row['id']}.json"
        cv_json = cvf.read_text(encoding="utf-8") if cvf.exists() else ""
        jd = ""
        try:
            jd = open(row["jd_path"], encoding="utf-8").read()
        except Exception:
            pass
        extras = json.loads(row.get("extras") or "{}")
        lang = extras.get("idioma", "en")
        data = self.llm.ask_json(prompts.SYSTEM_COVER, prompts.PROMPT_COVER.format(
            idioma="español" if lang == "es" else "inglés", empresa=row["empresa"], puesto=row["puesto"],
            jd=jd[:6000], cv_json=cv_json or self.cv, hechos=self.facts.as_text()), redaccion=True, max_tokens=3000)
        cv = json.loads(cv_json) if cv_json else {}
        path = Path(row["cv_docx"]).with_name(Path(row["cv_docx"]).stem.replace("CV_", "CoverLetter_", 1) + ".docx")
        build_cover_docx(cv.get("nombre", ""), cv.get("contacto", ""), row["empresa"], row["puesto"],
                         data.get("cover_letter", ""), path)
        extras["cover"] = {"docx": str(path), "asunto": data.get("asunto", ""),
                           "mensaje_linkedin": data.get("mensaje_linkedin", ""), "texto": data.get("cover_letter", "")}
        history.update(row["id"], extras=json.dumps(extras, ensure_ascii=False))
        return extras["cover"]

    # ---------- seguimiento ----------
    def followup_email(self, row):
        extras = json.loads(row.get("extras") or "{}")
        lang = extras.get("idioma", "en")
        cvf = JD_DIR / f"cv_{row['id']}.json"
        resumen = ""
        if cvf.exists():
            cv = json.loads(cvf.read_text(encoding="utf-8"))
            resumen = cv.get("perfil", "")[:600]
            nombre = cv.get("nombre", "")
        else:
            nombre = ""
        return self.llm.ask_json(prompts.SYSTEM_SEGUIMIENTO, prompts.PROMPT_SEGUIMIENTO.format(
            nombre=nombre, puesto=row["puesto"], empresa=row["empresa"], dias=row.get("dias", 7),
            idioma="español" if lang == "es" else "inglés", resumen=resumen or self.cv[:600]),
            max_tokens=1200, modelo=modelo_tarea(self.cfg, "seguimiento"))

    def _muestra(self):
        """Muestra opcional de cómo escribe el candidato (datos/muestra_estilo.txt) para imitar su voz."""
        f = DATA_DIR / "muestra_estilo.txt"
        try:
            t = f.read_text(encoding="utf-8").strip()
        except Exception:
            return ""
        if not t:
            return ""
        return ("\n- Imita el tono y vocabulario de esta muestra escrita por el candidato (solo el estilo, NO tomes "
                "hechos de aquí):\n<<<\n" + t[:3000] + "\n>>>")

    # ---------- flujo de consola ----------
    def ask_gaps(self, analysis, origen):
        pendientes = self.pending_gaps(analysis)
        for u in self.respuestas_usadas:
            self.ui.info(f"✔ {u['requisito']}: uso tu respuesta «{u['hecho']}» ({u['cubre']})")
        if not pendientes:
            self.ui.ok("No hay requisitos pendientes de confirmar: todo está en tu CV o en tus respuestas previas.")
            return 0
        self.ui.title(f"Antes de adaptar tu CV: {len(pendientes)} requisitos no aparecen (o solo parcialmente)")
        self.ui.info("Responde con la verdad; solo lo que confirmes se usará. "
                     "[s]í · [p]arcial · [n]o · Enter = saltar · [x] = saltar todas")
        n = 0
        for p in pendientes:
            ans = self.ui.ask(f"\n• {p['nombre']}\n  {p['pregunta']}\n  Requisito: {p['requisito']}\n  Respuesta",
                              choices=["s", "p", "n", "", "x"])
            if ans == "x":
                break
            if ans == "":
                continue
            tiene = {"s": "si", "p": "parcial", "n": "no"}[ans]
            detalle = ""
            if tiene != "no":
                detalle = self.ui.ask("  Cuéntame dónde, cuándo, qué hiciste y alguna cifra real si la tienes "
                                      "(esto se usará textualmente como evidencia)")
            self.facts.add(p["nombre"], tiene, detalle, origen)
            n += 1
        return n

    def process(self, job):
        ui = self.ui
        if job.get("url"):
            ui.info("Descargando la descripción completa de la oferta...")
        jd = self.get_jd(job)
        if len(jd) < 600:
            ui.warn("No pude obtener la descripción completa (algunos sitios como LinkedIn la bloquean).")
            jd = ui.paste("Pega aquí la descripción del puesto (JD)") or jd
        if len(jd) < 200:
            ui.warn("Sin descripción suficiente; se cancela esta oferta.")
            return None
        prev = history.find_by_url(job.get("url"))
        if prev and not ui.confirm(f"Esta oferta ya está en tu historial (ID {prev['id']}). ¿Generar otra versión?"):
            return None
        ui.step("1/5 Analizando como reclutador de la empresa...")
        a = self.analyze(jd)
        ui.show_analysis(a)
        fallidos = self.eliminatorios_fallidos(a)
        if fallidos:
            ui.warn("Requisitos ELIMINATORIOS que no cumples: " + "; ".join(e.get("requisito", "") for e in fallidos))
            if not ui.confirm("Un ATS podría descartarte automáticamente. ¿Generar el CV de todos modos?"):
                return None
        if a.get("elegible_desde_costa_rica") is False and not ui.confirm(
                "Parece NO elegible desde Costa Rica. ¿Continuar de todos modos?"):
            return None
        ui.step("2/5 Verificando requisitos que no están en tu CV...")
        if self.ask_gaps(a, f"{a.get('empresa') or job.get('empresa')} — {a.get('puesto') or job.get('puesto')}"):
            ui.info("Recalculando el estado de los requisitos con tus respuestas...")
            a = self.reanalyze(jd, a)
        res = self.generate(job, jd, a, progress=ui.step)
        ui.show_scan(res["escaneo"])
        ui.show_result(res["id"], a, res["auditoria"], res["docx"], res["pdf"], res["reporte"],
                       res["reescritura"], res["trainings"])
        return res["id"]

    def export_history(self):
        path = self.cfg["_salida_path"] / "Historial_Solicitudes.xlsx"
        try:
            history.export_excel(path)
        except PermissionError:
            alt = DATA_DIR / "Historial_Solicitudes.xlsx"
            history.export_excel(alt)
            if self.ui:
                self.ui.warn(f"El Excel estaba abierto; lo guardé en {alt}")
            return alt
        return path

    # ---------- top 5 habilidades ----------
    def gap_counts(self):
        """Cuenta local (sin IA) de brechas en todo el historial. Devuelve (Counter de pesos, ofertas por skill, filas)."""
        rows = history.all_rows()
        cnt, ofertas_por_skill = Counter(), {}
        for r in rows:
            vistos = set()
            for b in json.loads(r["brechas"] or "[]"):
                h = (b.get("habilidad") or "").strip()
                if not h or b.get("estado") == "cumple":
                    continue
                f = self.facts.find(h)
                if f and f["tiene"] == "si":
                    continue
                cnt[h] += 2 if b.get("tipo") == "obligatorio" else 1
                vistos.add(h)
            for kw in json.loads(r["palabras_faltantes"] or "[]"):
                f = self.facts.find(kw)
                if f and f["tiene"] == "si":
                    continue
                cnt[kw] += 1.5
                vistos.add(kw)
            for h in vistos:
                ofertas_por_skill[h] = ofertas_por_skill.get(h, 0) + 1
        return cnt, ofertas_por_skill, rows

    def top_skills(self):
        cnt, ofertas_por_skill, rows = self.gap_counts()
        if not rows:
            self.ui.warn("Aún no hay ofertas en el historial.")
            return None
        if not cnt:
            self.ui.ok("No hay brechas registradas.")
            return None
        brechas = "\n".join(f"- {h}: peso {w}, en {ofertas_por_skill.get(h, 0)} ofertas" for h, w in cnt.most_common(60))
        web = self.cfg.get("trainings_con_busqueda_web", True)
        try:
            data = self.llm.ask_json(prompts.SYSTEM_SKILLS, prompts.PROMPT_TOP_SKILLS.format(
                brechas=brechas, hechos=self.facts.as_text(),
                web_instr=prompts.WEB_INSTR_SKILLS if web else "No incluyas cursos (se agregan aparte)."),
                max_tokens=8000, web=web, modelo=modelo_tarea(self.cfg, "top5"))
            top5 = data.get("top5", [])[:5]
        except Exception as e:
            self.ui.warn(f"No pude consolidar con IA ({e}); uso el conteo directo.")
            top5 = [{"habilidad": h, "puntaje": w, "aparece_en_ofertas": ofertas_por_skill.get(h, 0),
                     "por_que": "Brecha más frecuente en tus ofertas.", "cursos": []}
                    for h, w in cnt.most_common(5)]
        for s in top5:  # siempre añadir enlaces estables del catálogo + búsquedas Udemy/Coursera
            urls = {c.get("url") for c in s.get("cursos", [])}
            for t in trainings.trainings_for(s["habilidad"]):
                if t["url"] not in urls:
                    s.setdefault("cursos", []).append(t)
        path = self.cfg["_salida_path"] / "Top5_Habilidades.html"
        skills_report(path, top5, len(rows))
        (DATA_DIR / "top5_habilidades.json").write_text(json.dumps(top5, indent=2, ensure_ascii=False), encoding="utf-8")
        return top5, path

"""CV Match — interfaz gráfica (se abre en el navegador). Ejecutar con ejecutar_gui.bat."""
import json
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _recargar_si_cambiaron():
    """Si actualizaste archivos de la app con la ventana abierta, recarga los módulos internos (evita errores de
    'cannot import name')."""
    import importlib
    orden = ["config", "gasto", "acceso", "estilo", "llm", "ollama", "gemini", "facts", "history", "backup", "trainings",
             "cv_reader", "docx_builder", "report", "prompts", "jobs", "buscador_web", "correo", "scheduler", "extras", "calidad", "portales", "usuarios", "pipeline"]
    base = Path(__file__).resolve().parent / "cvmatch"
    cambiado = False
    for nombre in orden:
        mod = sys.modules.get(f"cvmatch.{nombre}")
        f = base / f"{nombre}.py"
        if mod is not None and f.exists() and f.stat().st_mtime > getattr(mod, "__cargado__", 0):
            cambiado = True
    if cambiado:
        for nombre in orden:
            mod = sys.modules.get(f"cvmatch.{nombre}")
            if mod is not None:
                importlib.reload(mod)
    import time
    for nombre in orden:
        mod = sys.modules.get(f"cvmatch.{nombre}")
        if mod is not None:
            mod.__cargado__ = time.time()


try:
    _recargar_si_cambiaron()
except Exception:
    pass

from cvmatch import history  # noqa: E402
from cvmatch.config import APP_DIR, CONFIG_PATH, DATA_DIR, get_api_key, load_config, save_api_key  # noqa: E402
from cvmatch.config import dir_usuario_app, multiusuario  # noqa: E402
from cvmatch.cv_reader import read_cv  # noqa: E402
from cvmatch.facts import Facts  # noqa: E402
from cvmatch.pipeline import Pipeline  # noqa: E402

st.set_page_config(page_title="CV Match", page_icon="📄", layout="wide")

PAGINAS = ["🏠 Panel", "🔎 Buscar ofertas", "✍️ Adaptar CV", "📋 Historial",
           "🎯 Top 5 habilidades", "✅ Mis respuestas", "⚙️ Configuración", "📝 Formularios", "🎤 Simular entrevista"]
MODELOS = ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"]

st.markdown("""<style>
.block-container{padding-top:1.6rem;padding-left:1.5rem;padding-right:1.5rem;max-width:1500px}
.kw{display:inline-block;border:1px solid rgba(128,128,128,.45);border-radius:999px;padding:2px 10px;margin:2px 4px 2px 0;font-size:.88rem}
.antes{opacity:.6;text-decoration:line-through}
</style>""", unsafe_allow_html=True)


# ---------------- utilidades ----------------
def abrir(path):
    if not path:
        return
    if st.session_state.get("_remoto"):
        st.info("Esto abriría el archivo en la laptop. Desde el celular usa el botón ⬇️ Descargar.")
        return
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # noqa
        else:
            st.toast(f"Abrir: {path}")
    except Exception as e:
        st.error(f"No pude abrir {path}: {e}")


class GuiUI:
    """Adaptador para que el pipeline escriba mensajes en la interfaz."""
    def __init__(self, box=None):
        self.box = box

    def _w(self, fn, m):
        (getattr(self.box, fn) if self.box else getattr(st, fn))(m)

    def info(self, m): self._w("write", m)
    def warn(self, m): self._w("warning", m)
    def ok(self, m): self._w("success", m)
    step = title = info


@st.cache_resource(show_spinner=False)
def get_llm(key, m1, m2):
    from cvmatch.llm import LLM
    return LLM(key, m1, m2)


@st.cache_data(show_spinner=False)
def get_cv(path, mtime):
    return read_cv(path)


def contexto():
    cfg = load_config()
    facts = Facts()
    try:
        cv = get_cv(str(cfg["_cv_base_path"]), cfg["_cv_base_path"].stat().st_mtime)
        cv_error = None
    except Exception as e:
        cv, cv_error = "", str(e)
    key = get_api_key()
    llm = get_llm(key, cfg["modelo_analisis"], cfg["modelo_redaccion"]) if key else None
    if llm:
        llm.cfg = cfg
    return cfg, facts, cv, cv_error, llm


def pipe_for(cfg, facts, cv, llm, box=None):
    return Pipeline(cfg, llm, facts, cv, GuiUI(box))


def tags(items):
    st.markdown(" ".join(f"<span class='kw'>{x}</span>" for x in items if x) or "—", unsafe_allow_html=True)


def cv_markdown(cv):
    md = [f"### {cv.get('nombre', '')}", f"**{cv.get('titular', '')}**  ", f"<small>{cv.get('contacto', '')}</small>", ""]
    if cv.get("perfil"):
        md += ["**Perfil**", "", cv["perfil"], ""]
    if cv.get("competencias"):
        md += ["**Competencias:** " + " · ".join(cv["competencias"]), ""]
    for e in cv.get("experiencia", []):
        md.append(f"**{e.get('empresa', '')} — {e.get('puesto', '')}** · _{e.get('ubicacion', '')} · {e.get('fechas', '')}_")
        md += [f"- {b}" for b in e.get("bullets", [])]
        md.append("")
    if cv.get("habilidades_tecnicas"):
        md.append("**Habilidades técnicas**")
        md += [f"- **{h.get('categoria', '')}:** {h.get('items', '')}" for h in cv["habilidades_tecnicas"]]
    for k, t in (("certificaciones", "Certificaciones"), ("formacion", "Formación"), ("educacion", "Educación")):
        if cv.get(k):
            md += ["", f"**{t}**"] + [f"- {x}" for x in cv[k]]
    return "\n".join(md)


def crear_acceso_directo():
    import subprocess
    bat = APP_DIR / "ejecutar_gui.bat"
    ps = ("$d=[Environment]::GetFolderPath('Desktop'); $w=New-Object -ComObject WScript.Shell;"
          "$s=$w.CreateShortcut((Join-Path $d 'CV Match.lnk'));"
          f"$s.TargetPath='{bat}'; $s.WorkingDirectory='{APP_DIR}'; $s.WindowStyle=7;"
          "$s.IconLocation='imageres.dll,109'; $s.Save(); 'ok'")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                           capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


def estado_auto():
    f = DATA_DIR / "estado_auto.json"
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None


def ir_a(pagina):
    st.session_state.nav = pagina


def requiere_ia(llm):
    if not llm:
        st.warning("Falta tu API key. Agrégala en ⚙️ Configuración.")
        return False
    return True


# ---------------- páginas ----------------
def pagina_panel(cfg, facts, cv, llm):
    st.title("Panel")
    _caja_gasto(cfg)
    ea = estado_auto()
    if ea:
        if ea.get("error"):
            st.error(f"La última búsqueda automática ({ea['ultima']}) falló: {ea['error']}")
        elif ea.get("nuevas"):
            st.success(f"🆕 **{ea['nuevas']} ofertas nuevas** en la búsqueda automática de {ea['ultima']}.")
            st.button("Ver ofertas nuevas", on_click=ir_a, args=("🔎 Buscar ofertas",), key="ver_nuevas")
        else:
            st.caption(f"Última búsqueda automática: {ea['ultima']} — sin ofertas nuevas.")
    rows = history.all_rows()
    df = pd.DataFrame(rows)
    c = st.columns(5)
    total = len(df)
    c[0].metric("Ofertas trabajadas", total)
    c[1].metric("Por aplicar", int((df["estado"] == "Por aplicar").sum()) if total else 0)
    c[2].metric("Aplicadas", int(df["estado"].isin(["Aplicado", "Entrevista", "Prueba técnica", "Oferta"]).sum()) if total else 0)
    c[3].metric("Entrevistas", int(df["estado"].isin(["Entrevista", "Prueba técnica", "Oferta"]).sum()) if total else 0)
    if total and df["match_final"].notna().any():
        c[4].metric("Match promedio", f"{df['match_final'].mean():.0f}",
                    delta=f"{df['match_final'].mean() - df['match_inicial'].mean():+.0f} vs CV general")
    else:
        c[4].metric("Match promedio", "—")
    if not total:
        st.info("Todavía no hay ofertas. Empieza por **🔎 Buscar ofertas** o **✍️ Adaptar CV**.")
        b1, b2 = st.columns(2)
        b1.button("🔎 Buscar ofertas", on_click=ir_a, args=("🔎 Buscar ofertas",))
        b2.button("✍️ Adaptar CV a una oferta", on_click=ir_a, args=("✍️ Adaptar CV",))
        return
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Últimas solicitudes")
        st.dataframe(df[["fecha", "empresa", "puesto", "match_inicial", "match_final", "estado"]].head(8),
                     hide_index=True, column_config={"fecha": "Fecha", "empresa": "Empresa", "puesto": "Puesto",
                                                     "match_inicial": "Antes", "match_final": "Después", "estado": "Estado"})
    with right:
        st.subheader("Por estado")
        st.bar_chart(df["estado"].value_counts(), horizontal=True)
    _novedades_correo(cfg, facts, cv, llm)

    # Seguimientos pendientes
    pend = history.seguimientos_pendientes(int(cfg.get("dias_para_seguimiento", 7)))
    if pend:
        st.subheader(f"⏰ Seguimientos pendientes ({len(pend)})")
        st.caption(f"Solicitudes en 'Aplicado' sin respuesta hace {cfg.get('dias_para_seguimiento', 7)} días o más.")
        for r in pend:
            with st.container(border=True):
                st.markdown(f"**{r['empresa']} — {r['puesto']}** · hace {r['dias']} días · {r['url'] or ''}")
                k1, k2, k3 = st.columns(3)
                if k1.button("✉️ Redactar correo de seguimiento", key=f"seg_{r['id']}") and requiere_ia(llm):
                    with st.spinner("Redactando…"):
                        st.session_state[f"seg_txt_{r['id']}"] = pipe_for(cfg, facts, cv, llm).followup_email(r)
                if k2.button("✅ Ya di seguimiento", key=f"segok_{r['id']}"):
                    from datetime import date
                    history.update(r["id"], fecha_estado=date.today().isoformat(),
                                   notas=((r["notas"] or "") + f" | Seguimiento {date.today().isoformat()}").strip(" |"))
                    st.rerun()
                if k3.button("Cambiar estado en Historial", key=f"seghist_{r['id']}", on_click=ir_a, args=("📋 Historial",)):
                    pass
                txt = st.session_state.get(f"seg_txt_{r['id']}")
                if txt:
                    st.text_input("Asunto", txt.get("asunto", ""), key=f"sega_{r['id']}")
                    st.text_area("Correo", txt.get("cuerpo", ""), height=180, key=f"segc_{r['id']}")

    cnt, ofertas, _ = pipe_for(cfg, facts, cv, llm).gap_counts()
    if cnt:
        st.subheader("Brechas más repetidas en tus ofertas")
        tags([f"{h} ({ofertas.get(h, 0)})" for h, _ in cnt.most_common(10)])

    # Embudo
    aplicadas = df[df["estado"].isin(["Aplicado", "Entrevista", "Prueba técnica", "Oferta", "Rechazado"])].copy()
    if len(aplicadas):
        st.subheader("Embudo: ¿dónde te está yendo mejor?")
        def tipo(t):
            t = (t or "").lower()
            for k, v in (("architect", "Arquitectura"), ("arquitect", "Arquitectura"), ("identity", "Identidad/Seguridad"),
                         ("security", "Identidad/Seguridad"), ("iam", "Identidad/Seguridad"), ("manager", "Gestión"),
                         ("lead", "Gestión"), ("sre", "SRE/DevOps"), ("devops", "SRE/DevOps"), ("platform", "SRE/DevOps"),
                         ("migration", "Migración"), ("engineer", "Ingeniería"), ("ingenier", "Ingeniería"), ("admin", "Ingeniería")):
                if k in t:
                    return v
            return "Otro"
        def rango(m):
            m = m or 0
            return "<60" if m < 60 else "60-69" if m < 70 else "70-79" if m < 80 else "80+"
        aplicadas["Tipo de puesto"] = aplicadas["puesto"].map(tipo)
        aplicadas["Match inicial"] = aplicadas["match_inicial"].map(rango)
        aplicadas["entrevista"] = aplicadas["estado"].isin(["Entrevista", "Prueba técnica", "Oferta"])
        def _areas(x):
            try:
                return ", ".join(json.loads(x or "{}").get("areas") or []) or "Sin área"
            except Exception:
                return "Sin área"
        aplicadas["Área"] = aplicadas["extras"].map(_areas) if "extras" in aplicadas else "Sin área"
        aplicadas["Fuente"] = aplicadas["fuente"].fillna("—").map(lambda f: str(f).replace("Web: ", "")[:30]) \
            if "fuente" in aplicadas else "—"
        e1, e2 = st.columns(2)
        e3, e4 = st.columns(2)
        for col, campo in ((e1, "Tipo de puesto"), (e2, "Match inicial"), (e3, "Área"), (e4, "Fuente")):
            g = aplicadas.groupby(campo).agg(Aplicadas=("id", "count"), Entrevistas=("entrevista", "sum")).reset_index()
            g["Tasa"] = (g["Entrevistas"] / g["Aplicadas"] * 100).round(0).astype(int).astype(str) + " %"
            col.dataframe(g, hide_index=True)


def _caja_gasto(cfg):
    from cvmatch import gasto
    tope = float(cfg.get("presupuesto_mensual_usd") or 0)
    mes, hoy = gasto.total_mes(), gasto.total_hoy()
    with st.container(border=True):
        c = st.columns([1, 1, 2])
        c[0].metric("💵 Gasto hoy", f"${hoy:.2f}")
        c[1].metric("Este mes", f"${mes:.2f}", help="Calculado con el uso real que reporta la API en cada llamada.")
        if tope > 0:
            c[2].progress(min(mes / tope, 1.0), text=f"Presupuesto mensual: USD {mes:.2f} de {tope:.2f}")
            if mes >= tope:
                c[2].error("Llegaste al tope: la app no hará más llamadas a Claude este mes (súbelo en Configuración).")
            elif mes >= 0.8 * tope:
                c[2].warning("Vas por el 80 % de tu presupuesto mensual.")
        pt = gasto.por_tarea()
        if pt:
            with st.expander("¿En qué se fue el gasto este mes?"):
                st.dataframe(pd.DataFrame([{"Tarea": k, "USD": round(v["usd"], 3), "Llamadas": v["llamadas"],
                                            "Búsquedas web": v["busquedas_web"]} for k, v in
                                           sorted(pt.items(), key=lambda x: -x[1]["usd"])]), hide_index=True)


def _novedades_correo(cfg, facts, cv, llm):
    from cvmatch import correo
    oc = cfg.get("outlook") or {}
    if not oc.get("client_id"):
        return
    sug = correo.sugerencias()
    cab1, cab2 = st.columns([3, 1])
    cab1.subheader(f"📧 Novedades en tu correo ({len(sug)})")
    if cab2.button("🔄 Revisar correo ahora"):
        with st.spinner("Leyendo Outlook…"):
            try:
                sug = correo.revisar(pipe_for(cfg, facts, cv, llm), log=lambda m: None)
                st.toast(f"Listo: {len(sug)} sugerencia(s)")
            except Exception as e:
                st.error(str(e))
    if not sug:
        st.caption("Sin respuestas nuevas de las empresas a las que aplicaste.")
        return
    iconos = {"entrevista": "🗓️", "prueba_tecnica": "🧪", "oferta": "🎉", "rechazo": "✖️", "acuse_recibo": "📨"}
    for x in sug:
        with st.container(border=True):
            st.markdown(f"{iconos.get(x['categoria'], '📧')} **{x['empresa']} — {x['puesto']}** · {x['fecha']}  \n"
                        f"_{x['asunto']}_  \n{x['resumen']}  \n"
                        f"Sugerencia: **{x['estado_actual']} → {x['estado_sugerido']}**"
                        + (" · (estaba en No deseado)" if x.get("carpeta") == "junkemail" else ""))
            k1, k2, k3 = st.columns(3)
            if k1.button("✅ Aplicar cambio", key=f"ok_{x['msg_id']}"):
                correo.resolver(x["msg_id"], True)
                pipe_for(cfg, facts, cv, llm).export_history()
                st.rerun()
            if k2.button("Ignorar", key=f"no_{x['msg_id']}"):
                correo.resolver(x["msg_id"], False)
                st.rerun()
            if x.get("link"):
                k3.link_button("Abrir correo", x["link"])


def _mtime():
    f = DATA_DIR / "ultima_busqueda.json"
    return f.stat().st_mtime if f.exists() else 0


def pagina_buscar(cfg, facts, cv, llm):
    st.title("Buscar ofertas")
    st.caption("Solo puestos en Costa Rica o 100 % remotos contratables desde Costa Rica. Se descartan ofertas en otros "
               "países (aunque digan LATAM), con relocation o presenciales/híbridas fuera de Costa Rica.")
    from cvmatch.jobs import areas_config
    areas = areas_config(cfg)
    nombres_areas = [a["nombre"] for a in areas]
    st.markdown("**Tus áreas** (cada una se busca por separado, con su propio cupo de ofertas):")
    tags(nombres_areas)
    st.caption("Se editan en ⚙️ Configuración → Preferencias → Áreas de búsqueda.")
    pipe0 = pipe_for(cfg, facts, cv, llm)
    with st.form("buscar"):
        extra = st.text_input("Palabras clave extra (se buscan como un área más)", placeholder="ej. landing zone, aws")
        c1, c2 = st.columns(2)
        cr = c1.checkbox("Incluir búsqueda web en Costa Rica (IA)", value=cfg["busqueda"].get("buscar_costa_rica_con_ia", True))
        disp = [n for n in nombres_areas if pipe0.web_disponible(n)[0]]
        areas_web = c1.multiselect("Áreas para la búsqueda web (una búsqueda por área)", nombres_areas, default=disp,
                                   help="Las bolsas remotas buscan siempre todas las áreas gratis. La búsqueda web cuesta "
                                        "por área; las que se buscaron hace poco vienen desmarcadas.")
        forzar = c1.checkbox("Repetir también las áreas buscadas hace menos de "
                             f"{cfg.get('horas_entre_busquedas_web', 6)} h", value=False)
        from cvmatch import buscador_web as _bw
        _est = [("Tavily", "✅ gratis" if _bw.get_key("tavily") else "❌ sin clave"),
                ("Claude", f"~USD {pipe0.costo_web_estimado(1):.3f}/área" if (cfg.get('busqueda_web') or {}).get('claude_respaldo', True)
                 else "desactivado")]
        c1.caption("Búsqueda web por necesidad: " + " → ".join(f"{n} ({e})" for n, e in _est)
                   + ". Solo pasa al siguiente si el anterior falla. Claves en ⚙️ Configuración.")
        c2.caption("El match mínimo y el filtro por área se ajustan en vivo debajo, sobre la lista guardada.")
        go = st.form_submit_button("🔎 Buscar", type="primary")
    if go and requiere_ia(llm):
        cfg["busqueda"]["buscar_costa_rica_con_ia"] = cr and bool(areas_web)
        with st.status("Buscando y evaluando ofertas por área…", expanded=True) as box:
            try:
                res = pipe_for(cfg, facts, cv, llm, box).search([k.strip() for k in extra.split(",") if k.strip()],
                                                                forzar_web=forzar, areas_web=areas_web)
                st.session_state.resultados = res
                _guardar_json(SELECCION_PATH, [])  # nueva búsqueda: se limpian las casillas (la cola se mantiene)
                box.update(label=f"Listo: {len(res)} ofertas encajan con tu CV", state="complete", expanded=False)
            except Exception as e:
                box.update(label="Error en la búsqueda", state="error")
                st.error(str(e))
    ea = estado_auto()
    if ea:
        st.caption(f"🤖 Última búsqueda automática: {ea['ultima']} · {ea.get('nuevas', 0)} nuevas"
                   + (f" · ⚠️ {ea['error']}" if ea.get("error") else ""))
    from cvmatch.pipeline import load_results
    if "resultados" not in st.session_state or st.session_state.get("_res_mtime") != _mtime():
        st.session_state.resultados = load_results()
        st.session_state._res_mtime = _mtime()
    from cvmatch.jobs import location_ok
    _validas = cfg["busqueda"]["ubicaciones_remotas_validas"] + ["remote", "remoto"]
    from cvmatch.jobs import titulo_excluido
    todas = [j for j in st.session_state.resultados if not history.find_by_url(j["url"])
             and location_ok(j.get("ubicacion", ""), _validas, j.get("descripcion", "")) is not False
             and not titulo_excluido(j.get("puesto"), cfg)]
    from cvmatch.pipeline import CRITERIO
    viejas = [j for j in todas if j.get("match_estimado") and j.get("criterio") != CRITERIO]
    if viejas:
        r1, r2 = st.columns([3, 1])
        r1.info(f"🎯 {len(viejas)} oferta(s) tienen el match calculado con el criterio anterior (sin tu perfil objetivo "
                "ni la rúbrica tipo de rol / tecnologías / seniority). Re-evalúalas para ordenar mejor la lista: es "
                "gratis con Ollama o Gemini.")
        if r2.button("Re-evaluar todas", key="reeval_todas", type="primary"):
            ok_re = False
            with st.status("Re-evaluando con el criterio nuevo…", expanded=True) as box:
                try:
                    q, n = pipe_for(cfg, facts, cv, llm, box).reevaluar_todas()
                    box.update(label=f"Listo: {n} re-evaluadas, {q} quitadas", state="complete", expanded=False)
                    ok_re = True
                except Exception as e:
                    box.update(label="Error al re-evaluar", state="error")
                    st.error(str(e))
            if ok_re:
                st.session_state.pop("resultados", None)
                st.rerun()
    minimo = st.slider("Mostrar ofertas con match ≥", 0, 100, int(cfg["puntaje_minimo_mostrar"]), key="min_vivo",
                       help="Filtra la lista guardada al instante; no vuelve a buscar ni cuesta nada. "
                            "Las ofertas sin evaluar se muestran siempre.")
    from cvmatch.jobs import areas_de_oferta
    for j in todas:
        if not j.get("areas"):
            j["areas"] = areas_de_oferta(j, areas)
    filtro_areas = st.multiselect("Ver solo estas áreas", nombres_areas, default=[], key="filtro_areas",
                                  placeholder="Todas las áreas")
    if filtro_areas:
        todas = [j for j in todas if set(j.get("areas") or []) & set(filtro_areas)]
    cuenta = {n: sum(1 for j in todas if n in (j.get("areas") or [])) for n in nombres_areas}
    st.caption("Ofertas por área: " + " · ".join(f"{k} **{v}**" for k, v in cuenta.items()))
    from cvmatch import extras as _ex
    res = [j for j in todas if not j.get("match_estimado") or j["match_estimado"] >= minimo
           or _ex.es_favorita(j.get("empresa"), cfg)]  # las de tus empresas favoritas se muestran siempre
    res.sort(key=lambda j: _ex.orden_lista(j, cfg), reverse=True)
    sin_eval = [j for j in todas if not j.get("match_estimado")]
    if len(res) < len(todas):
        st.caption(f"Mostrando {len(res)} de {len(todas)} ofertas guardadas ({len(todas) - len(res)} con match menor a {minimo}).")
    if sin_eval:
        c_a, c_b = st.columns([3, 1])
        c_a.warning(f"{len(sin_eval)} oferta(s) quedaron **sin evaluar** (la IA local no les dio puntaje). "
                    "Aparecen con «—» en Match. Puedes evaluarlas ahora con Claude Haiku (menos de USD 0.01).")
        if c_b.button("Evaluar ahora", key="eval_sin") and requiere_ia(llm):
            ok_eval = False
            with st.status("Evaluando ofertas sin match…", expanded=True) as box:
                try:
                    n = pipe_for(cfg, facts, cv, llm, box).evaluar_sin_puntaje()
                    box.update(label=f"Listo: {n} evaluadas", state="complete", expanded=False)
                    ok_eval = True
                except Exception as e:
                    box.update(label="Error al evaluar", state="error")
                    st.error(str(e))
            if ok_eval:
                st.session_state.pop("resultados", None)
                st.rerun()
    if not res:
        st.info("Sin resultados todavía. Pulsa **Buscar**.")
        return
    st.subheader(f"{len(res)} ofertas, ordenadas por match")
    from cvmatch.jobs import link_busqueda, normalizar_link, tipo_link
    for j in res:
        j["url"] = normalizar_link(j["url"])
        j["tipo_link"] = tipo_link(j["url"])
    n_lista = sum(1 for j in res if j["tipo_link"] == "lista")
    if n_lista:
        st.info(f"{n_lista} oferta(s) solo tienen un link a una lista de resultados. En esas, la columna **Abrir** te lleva "
                "a una búsqueda filtrada por puesto y empresa para encontrarla rápido.")
    marcadas = set(_leer_json(SELECCION_PATH, []))
    en_cola = {j.get("url") for j in st.session_state.get("cola", [])}
    df = pd.DataFrame([{"Elegir": j["url"] in marcadas, "Match": j.get("match_estimado") or None,
                        "CR": "✅" if (j.get("elegible_cr") is True and j.get("elegible_ubicacion") is not None) else "⚠️",
                        "Puesto": j["puesto"], "Área": ", ".join(j.get("areas") or []),
                        "Empresa": ("⭐ " if _ex.es_favorita(j.get("empresa"), cfg) else "") + (j["empresa"] or ""),
                        "Ubicación": j["ubicacion"], "Fuente": j["fuente"].replace("Web: ", ""),
                        "Fecha": _texto_publicada(j, cfg) + (" 📌" if j["url"] in en_cola else ""),
                        "Motivo": j.get("motivo", "") or ("Sin evaluar todavía" if not j.get("match_estimado") else ""),
                        "Link": link_busqueda(j) if j["tipo_link"] == "lista" else j["url"]}
                       for j in res])
    col = st.column_config
    import inspect
    _ancho = ({"width": "stretch"} if "width" in inspect.signature(st.data_editor).parameters
              else {"use_container_width": True})
    ed = st.data_editor(df, hide_index=True, **_ancho,
                        disabled=[c for c in df.columns if c != "Elegir"],
                        column_config={"Elegir": col.CheckboxColumn("✔", width=34),
                                       "Match": col.ProgressColumn(min_value=0, max_value=100, format="%d", width=60),
                                       "CR": col.TextColumn("CR", width=32, help="✅ contratable desde Costa Rica · ⚠️ verificar"),
                                       "Puesto": col.TextColumn(width=175),
                                       "Área": col.TextColumn(width=105),
                                       "Empresa": col.TextColumn(width=100),
                                       "Ubicación": col.TextColumn(width=95),
                                       "Fuente": col.TextColumn(width=80),
                                       "Fecha": col.TextColumn("Publ.", width=62, help="Hace cuántos días se publicó (⚠️ = más de "
                                                               f"{cfg.get('dias_oferta_vieja', 30)} días, suele estar cerrada; "
                                                               "sin dato: fecha en que la encontró la app) · 📌 = en tu cola"),
                                       "Motivo": col.TextColumn(width=140, help="Pasa el mouse sobre la celda para leerlo completo"),
                                       "Link": col.LinkColumn("Abrir", display_text="abrir", width=45)},
                        key="ed_busqueda_" + str(abs(hash(tuple(j["url"] for j in res)))))
    sel = [res[i] for i in ed.index[ed["Elegir"]].tolist()]
    urls_sel = [j["url"] for j in sel]
    visibles = {j["url"] for j in res}
    nueva_sel = [u for u in marcadas if u not in visibles] + urls_sel  # las ocultas por el filtro también se guardan
    if set(nueva_sel) != marcadas:
        _guardar_json(SELECCION_PATH, nueva_sel)

    def encolar():
        actual = list(st.session_state.get("cola", []))
        ya = {j.get("url") for j in actual}
        _set_cola(actual + [j for j in sel if j["url"] not in ya])  # se suman a la cola, no la reemplazan
        st.session_state.adapt = None
        st.session_state.nav = "✍️ Adaptar CV"
    bq1, bq2, bq3 = st.columns([2, 1.3, 1.7])
    bq1.button(f"✍️ Agregar {len(sel)} oferta(s) a mi cola y adaptar", type="primary", disabled=not sel, on_click=encolar)
    motivo_desc = bq3.text_input("Motivo (opcional, ayuda a la IA a aprender)", key="motivo_desc",
                                 placeholder="ej. es de desarrollo, muy junior…", label_visibility="collapsed")
    if bq2.button(f"🚫 No me interesa ({len(sel)})", disabled=not sel,
                  help="No vuelven a aparecer y la app aprende qué tipo de ofertas no quieres"):
        from cvmatch import calidad
        calidad.descartar(sel, motivo_desc.strip())
        _guardar_json(SELECCION_PATH, [u for u in _leer_json(SELECCION_PATH, []) if u not in {j["url"] for j in sel}])
        st.session_state.pop("resultados", None)
        st.rerun()
    _paneles_calidad()
    if st.session_state.get("cola"):
        st.caption(f"📌 Tienes {len(st.session_state.cola)} oferta(s) en tu cola (se guardan aunque cierres la app).")


BORRADOR = DATA_DIR / "adaptacion_en_curso.json"


def _refrasear_cb(i, g, pipe):
    """Se ejecuta antes de redibujar: reemplaza el texto del cuadro por la versión mejorada (sin datos nuevos)."""
    texto = (st.session_state.get(f"det_{i}") or "").strip()
    if not texto:
        st.session_state[f"ref_msg_{i}"] = ("warn", "Escribe primero tu respuesta (aunque sea en borrador) y luego refrasea.")
        return
    try:
        nivel = st.session_state.get(f"gap_{i}", "Saltar")
        nuevo, falta = pipe.refrasear(texto, g.get("requisito", g["nombre"]), g.get("pregunta", ""),
                                      {"Sí": "dice que sí lo tiene", "Parcial": "dice que lo tiene en parte",
                                       "No": "dice que no lo tiene"}.get(nivel, "sin marcar"))
    except Exception as e:
        st.session_state[f"ref_msg_{i}"] = ("err", f"No pude refrasear: {e}")
        return
    if not nuevo:
        st.session_state[f"ref_msg_{i}"] = ("warn", "La IA no devolvió una versión mejor; deja tu texto tal cual.")
        return
    st.session_state[f"det_prev_{i}"] = texto
    st.session_state[f"det_{i}"] = nuevo
    st.session_state[f"ref_msg_{i}"] = ("ok", ("Para hacerla más fuerte, podrías agregar: " + " · ".join(falta))
                                        if falta else "Revisa que diga exactamente lo que hiciste.")


def _deshacer_cb(i):
    if f"det_prev_{i}" in st.session_state:
        st.session_state[f"det_{i}"] = st.session_state.pop(f"det_prev_{i}")
        st.session_state.pop(f"ref_msg_{i}", None)


def _botones_refraseo(col, i, g, pipe):
    import inspect
    con_key = "key" in inspect.signature(st.form_submit_button).parameters
    b1, b2 = col.columns([1, 1])
    kw = {"key": f"ref_{i}"} if con_key else {}
    b1.form_submit_button("✨ Refrasear con IA" if con_key else f"✨ Refrasear: {g['nombre'][:30]}",
                          on_click=_refrasear_cb, args=(i, g, pipe),
                          help="Mejora la redacción sin agregar datos (Ollama → Gemini → Haiku, normalmente gratis)", **kw)
    if f"det_prev_{i}" in st.session_state:
        kw2 = {"key": f"undo_{i}"} if con_key else {}
        b2.form_submit_button("↩️ Volver a mi texto" if con_key else f"↩️ Mi texto: {g['nombre'][:30]}",
                              on_click=_deshacer_cb, args=(i,), **kw2)
    m = st.session_state.get(f"ref_msg_{i}")
    if m:
        {"ok": col.caption, "warn": col.warning, "err": col.error}[m[0]](m[1])


def _guardar_borrador(ad):
    from datetime import datetime
    d = {k: v for k, v in ad.items() if k in ("stage", "job", "jd", "a", "gaps", "usadas", "respuestas",
                                               "pendiente_recalcular")}
    d["guardado"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    BORRADOR.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _reset_adapt():
    st.session_state.adapt = None


COLA_PATH = DATA_DIR / "cola.json"
SELECCION_PATH = DATA_DIR / "seleccion.json"


def _guardar_json(path, data):
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _leer_json(path, defecto):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return defecto


def _set_cola(cola):
    """La cola se guarda en disco: sobrevive aunque cierres la app, hasta que la proceses o la quites."""
    st.session_state.cola = cola
    _guardar_json(COLA_PATH, cola)


def _paneles_calidad():
    from cvmatch import calidad
    tot, n = calidad.resumen_rendimiento()
    if n:
        with st.expander(f"📊 Rendimiento de las últimas {n} búsquedas (qué fuente y qué área aportan ofertas útiles, match ≥ 70)"):
            c1, c2 = st.columns(2)
            for col, grupo, titulo in ((c1, "fuentes", "Fuente"), (c2, "areas", "Área")):
                filas = [{titulo: k, "Ofertas": a, "Útiles": u, "% útil": f"{(u / a * 100) if a else 0:.0f} %"}
                         for k, (a, u) in sorted(tot[grupo].items(), key=lambda x: -x[1][1])]
                col.dataframe(pd.DataFrame(filas), hide_index=True)
            apag = calidad.bolsas_sin_rendimiento()
            if apag:
                st.caption("Se están omitiendo por no aportar nada útil: " + ", ".join(apag) +
                           " (vuelven solas cuando pasen unas búsquedas; se desactiva en ⚙️ Configuración).")
    d = calidad.descartadas()
    if d:
        with st.expander(f"🚫 Ofertas que marcaste «No me interesa» ({len(d)})"):
            for i, x in enumerate(d[:50]):
                a, b = st.columns([5, 1])
                a.write(f"{x['puesto']} — {x['empresa']}" + (f" · _{x['motivo']}_" if x.get("motivo") else "") + f" · {x['fecha']}")
                if b.button("Restaurar", key=f"rest_{i}"):
                    calidad.restaurar(x["url"])
                    st.session_state.pop("resultados", None)
                    st.rerun()


def _texto_publicada(j, cfg):
    from cvmatch import extras as _ex
    d = _ex.dias_publicada(j)
    if d is None:
        return "~" + (j.get("encontrada") or "")[5:10]
    return ("⚠️ " if d > int(cfg.get("dias_oferta_vieja", 30)) else "") + ("hoy" if d <= 0 else f"{d} d")


def _fuera_de_cr(cfg, job, jd=None):
    """True si el texto/ubicación de la oferta dice que no se puede tomar desde Costa Rica (revisión gratis, sin IA)."""
    from cvmatch.jobs import location_ok
    validas = cfg["busqueda"]["ubicaciones_remotas_validas"] + ["remote", "remoto"]
    ubic = job.get("ubicacion", "") or ""
    texto = jd if jd is not None else job.get("descripcion", "")
    if not ubic and job.get("fuente") == "Manual":
        ubic = "remote"  # link o texto pegado: se decide solo por lo que diga la descripción
    return location_ok(ubic, validas, texto) is False


def pagina_adaptar(cfg, facts, cv, llm):
    st.title("Adaptar CV a una oferta")
    pipe = pipe_for(cfg, facts, cv, llm)
    ad = st.session_state.get("adapt")
    cola = st.session_state.get("cola", [])
    # la cola puede traer ofertas elegidas antes del filtro nuevo: se quitan las que no son contratables desde CR (gratis)
    if cola:
        limpia = [j for j in cola if _fuera_de_cr(cfg, j) is False]
        if len(limpia) < len(cola):
            quitadas = [f"{j.get('puesto')} — {j.get('empresa')}" for j in cola if j not in limpia]
            _set_cola(limpia)
            cola = limpia
            st.info("Quité de la cola " + str(len(quitadas)) + " oferta(s) que no se pueden tomar desde Costa Rica "
                    "(el texto limita el país): " + "; ".join(quitadas))

    # ---- Borrador guardado (análisis y respuestas sin generar) ----
    if not ad and BORRADOR.exists():
        try:
            b = json.loads(BORRADOR.read_text(encoding="utf-8"))
            ba = b.get("a", {})
            with st.container(border=True):
                st.markdown(f"💾 **Tienes una adaptación guardada sin generar:** {ba.get('puesto', '')} — "
                            f"{ba.get('empresa', '')} (match {ba.get('puntuacion_match', '?')}/100, guardada {b.get('guardado', '')})")
                k1, k2 = st.columns([1, 3])
                if k1.button("▶️ Continuar donde quedé", type="primary"):
                    st.session_state.adapt = b
                    for i, r in (b.get("respuestas") or {}).items():
                        st.session_state[f"gap_{i}"] = r.get("ans", "Saltar")
                        st.session_state[f"det_{i}"] = r.get("det", "")
                    st.rerun()
                if k2.button("Descartar borrador"):
                    BORRADOR.unlink(missing_ok=True)
                    st.rerun()
        except Exception:
            BORRADOR.unlink(missing_ok=True)

    # ---- Etapa 1: elegir oferta ----
    if not ad:
        if cola:
            st.subheader(f"Cola de búsqueda ({len(cola)})")
            opciones = [f"{j['puesto']} — {j['empresa']}" for j in cola]
            q1, q2 = st.columns([5, 1])
            i = q1.selectbox("Oferta", range(len(cola)), format_func=lambda k: opciones[k])
            job = dict(cola[i])
            q2.write("")
            if q2.button("🗑️ Quitar", key="quitar_cola", help="Saca esta oferta de tu cola"):
                _set_cola([j for k, j in enumerate(cola) if k != i])
                st.rerun()
            from cvmatch.jobs import link_busqueda, tipo_link
            if tipo_link(job.get("url")) == "lista":
                st.warning("Esta oferta solo tiene un link a una lista de resultados. Ábrela con la búsqueda filtrada, "
                           "copia el texto del puesto y pégalo abajo para analizarla.")
                st.link_button("🔎 Buscar esta oferta", link_busqueda(job))
            else:
                st.caption(job.get("url", ""))
        else:
            job = None
        st.subheader("O una oferta específica")
        url = st.text_input("Link de la oferta", value="" if not job else "", placeholder="https://…")
        jd_txt = st.text_area("…o pega aquí la descripción del puesto (necesario si el sitio bloquea la descarga, ej. LinkedIn)",
                              height=200)
        forzar_ubic = st.checkbox("Analizar aunque la oferta parezca NO contratable desde Costa Rica (cuesta igual)",
                                  value=False, key="forzar_ubic",
                                  help="Antes de pagar el análisis, la app revisa gratis el texto de la oferta. Si dice que "
                                       "solo contratan en otro país, se detiene salvo que marques esto.")
        if st.button("1️⃣ Analizar como reclutador", type="primary") and requiere_ia(llm):
            if url or jd_txt.strip():
                job = {"url": url.strip(), "fuente": "Manual", "descripcion": jd_txt.strip(), "empresa": "", "puesto": ""}
            if not job:
                st.error("Elige una oferta de la cola, pon un link o pega el texto.")
                return
            with st.spinner("Obteniendo la descripción…"):
                jd = pipe.get_jd(job)
            if len(jd) < 600:
                st.error("No pude obtener la descripción completa desde el link. Pega el texto del puesto en el cuadro y vuelve a analizar.")
                return
            if not forzar_ubic and _fuera_de_cr(cfg, job, jd):
                st.error("⛔ No analicé esta oferta (no se gastó nada): el texto indica que solo contratan en otro país o "
                         "es presencial fuera de Costa Rica. Si estás seguro de que sí aceptan Costa Rica, marca la casilla "
                         "de arriba y vuelve a pulsar Analizar.")
                return
            prev = history.find_by_url(job.get("url")) or (
                history.find_similar(job.get("empresa"), job.get("puesto")) if job.get("empresa") else None)
            if prev:
                st.warning(f"Esta oferta ya está en tu historial (ID {prev['id']}). Se generará otra versión.")
            with st.spinner("Analizando como reclutador de la empresa…"):
                try:
                    a = pipe.analyze(jd)
                except Exception as e:
                    st.error(f"Error en el análisis: {e}")
                    return
            with st.spinner("Revisando tus respuestas guardadas antes de preguntarte…"):
                gaps = pipe.pending_gaps(a)
            st.session_state.adapt = {"stage": "analizado", "job": job, "jd": jd, "a": a,
                                      "gaps": gaps, "usadas": pipe.respuestas_usadas, "respuestas": {}}
            _guardar_borrador(st.session_state.adapt)
            st.rerun()
        return

    a, job = ad["a"], ad["job"]
    st.subheader(f"{a.get('puesto') or job.get('puesto')} — {a.get('empresa') or job.get('empresa')}")
    st.caption(f"{a.get('ubicacion', '')} · {a.get('modalidad', '')} · {job.get('url', '')}")

    # ---- Etapa 2: análisis + preguntas ----
    if ad["stage"] == "analizado":
        c = st.columns(3)
        c[0].metric("Match de tu CV general", f"{a.get('puntuacion_match', '?')}/100")
        el = a.get("elegible_desde_costa_rica")
        c[1].metric("Elegible desde Costa Rica", {True: "Sí", False: "No", None: "No se sabe"}.get(el, str(el)))
        c[2].metric("Requisitos a confirmar", len(ad["gaps"]))
        if el is False:
            st.error(f"Parece NO elegible desde Costa Rica: {a.get('motivo_elegibilidad', '')}")
        d = a.get("desglose_puntuacion") or {}
        if d:
            st.caption(f"Rúbrica: obligatorios {d.get('obligatorios', '?')}/50 · deseables {d.get('deseables', '?')}/20 · "
                       f"seniority {d.get('seniority', '?')}/15 · industria {d.get('industria', '?')}/15")
        sim = history.find_similar(a.get("empresa"), a.get("puesto"))
        if sim and sim.get("url") != job.get("url"):
            st.warning(f"Ya trabajaste una oferta igual o muy parecida: #{sim['id']} {sim['empresa']} — {sim['puesto']} "
                       f"({sim['estado']}). Revisa el historial antes de aplicar de nuevo.")
        elim = a.get("requisitos_eliminatorios") or []
        fallidos = [e for e in elim if e.get("cumple") == "no"]
        dudosos = [e for e in elim if e.get("cumple") == "desconocido"]
        if fallidos:
            st.error("⛔ **Requisitos eliminatorios que NO cumples** (un ATS podría descartarte automáticamente):\n\n" +
                     "\n".join(f"- **{e.get('requisito')}** — {e.get('detalle', '')}" for e in fallidos) +
                     "\n\nPuedes generar el CV igual, pero considera si vale la pena aplicar.")
        if dudosos:
            st.warning("Requisitos eliminatorios por confirmar:\n\n" +
                       "\n".join(f"- **{e.get('requisito')}** — {e.get('detalle', '')}" for e in dudosos))
        if elim and not fallidos and not dudosos:
            st.success("Cumples todos los requisitos eliminatorios detectados.")
        st.write(a.get("justificacion_puntuacion", ""))
        l, r = st.columns(2)
        with l:
            st.markdown("**5 palabras clave que te faltan**")
            tags(a.get("palabras_clave_faltantes", []))
            st.markdown("**Cómo subir el match**")
            for s in a.get("sugerencias_para_subir_match", []):
                st.markdown(f"- {s}")
        with r:
            st.markdown("**3 red flags (10 segundos)**")
            for f in a.get("red_flags", []):
                with st.expander(f"🚩 {f.get('flag', '')}"):
                    st.write(f.get("por_que", ""))
                    st.caption(f"Cómo corregir: {f.get('como_corregir', '')}")
        with st.expander("Requisitos de la oferta y evidencia"):
            if a.get("requisitos"):
                st.dataframe(pd.DataFrame(a["requisitos"]).reindex(columns=["requisito", "tipo", "estado", "evidencia"]),
                             hide_index=True, column_config={"requisito": "Requisito", "tipo": "Tipo",
                                                             "estado": "Estado", "evidencia": "Evidencia"})

        st.divider()
        usadas = ad.get("usadas") or []
        if usadas:
            etiqueta = {"si": "✅ cubre", "parcial": "🟡 cubre en parte", "no_tiene": "⛔ ya dijiste que no"}
            with st.expander(f"♻️ {len(usadas)} requisito(s) respondidos con tus respuestas guardadas (no te los pregunto)",
                             expanded=True):
                for u in usadas:
                    st.markdown(f"- **{u['requisito']}** ← «{u['hecho']}» · {etiqueta.get(u['cubre'], u['cubre'])}  \n"
                                f"<small>{u.get('motivo', '')}</small>", unsafe_allow_html=True)
                st.caption("Si alguna no corresponde, corrígela en ✅ Mis respuestas y vuelve a analizar.")
        with st.form("brechas"):
            if ad["gaps"]:
                st.subheader("2️⃣ Solo falta confirmar esto (no está en tu CV ni en tus respuestas)")
                st.caption("Solo lo que confirmes se usará en el CV. Tus respuestas se guardan y no se vuelven a preguntar.")
                for i, g in enumerate(ad["gaps"]):
                    st.markdown(f"**{g['nombre']}** · <small>{g['tipo']} · {g['requisito']}</small>", unsafe_allow_html=True)
                    cc = st.columns([2, 5])
                    cc[0].radio(g["pregunta"], ["Saltar", "Sí", "Parcial", "No"], key=f"gap_{i}", horizontal=True)
                    cc[1].text_area("Detalle (dónde, cuándo, qué hiciste, cifras reales)", key=f"det_{i}", height=68)
                    _botones_refraseo(cc[1], i, g, pipe)
            else:
                st.success("Todo lo que pide la oferta está en tu CV o en tus respuestas previas.")
            forzar_gen = False
            if el is False:
                forzar_gen = st.checkbox("Generar igual aunque NO sea elegible desde Costa Rica (gasta crédito)", value=False)
            b1, b2, b3 = st.columns([2, 2, 2])
            gen = b1.form_submit_button("3️⃣ Generar CV adaptado", type="primary")
            guardar = b2.form_submit_button("💾 Guardar sin generar")
            desc = b3.form_submit_button("Descartar esta oferta")
        if desc:
            BORRADOR.unlink(missing_ok=True)
            _reset_adapt()
            st.rerun()
        if guardar or gen:
            # guarda respuestas (como hechos confirmados) y el borrador, antes de gastar nada
            origen = f"{a.get('empresa')} — {a.get('puesto')}"
            n = 0
            for i, g in enumerate(ad["gaps"]):
                ans = st.session_state.get(f"gap_{i}", "Saltar")
                det = st.session_state.get(f"det_{i}", "")
                ad.setdefault("respuestas", {})[str(i)] = {"ans": ans, "det": det}
                if ans != "Saltar":
                    tiene = {"Sí": "si", "Parcial": "parcial", "No": "no"}[ans]
                    facts.add(g["nombre"], tiene, det if tiene != "no" else "", origen)
                    n += 1
            if n:
                ad["pendiente_recalcular"] = True
            _guardar_borrador(ad)
            if guardar:
                st.success(f"Guardado: {n} respuesta(s) confirmada(s) y el análisis de esta oferta. Puedes cerrar la app "
                           "y continuar después desde ✍️ Adaptar CV, sin volver a pagar el análisis.")
        if gen and el is False and not forzar_gen:
            st.error("⛔ No generé el CV (no se gastó nada): esta oferta no es contratable desde Costa Rica. "
                     "Te recomiendo **Descartar esta oferta**. Si aun así quieres el CV, marca la casilla y vuelve a generar.")
            gen = False
        if gen:
            with st.status("Generando tu CV adaptado…", expanded=True) as box:
                try:
                    if ad.get("pendiente_recalcular"):
                        box.write("Recalculando requisitos con tus respuestas…")
                        a = pipe.reanalyze(ad["jd"], a)
                        ad.update({"a": a, "pendiente_recalcular": False})
                        _guardar_borrador(ad)
                    res = pipe.generate(job, ad["jd"], a, progress=box.write)
                    box.update(label="CV listo", state="complete", expanded=False)
                except Exception as e:
                    box.update(label="Error al generar", state="error")
                    st.error(f"{e}\n\nTu análisis y tus respuestas quedaron guardados: cuando lo resuelvas, vuelve a "
                             "✍️ Adaptar CV → **Continuar donde quedé**.")
                    return
            BORRADOR.unlink(missing_ok=True)
            ad.update({"stage": "listo", "res": res, "a": a})
            _set_cola([j for j in st.session_state.get("cola", []) if j.get("url") != job.get("url")])
            st.rerun()
        return

    # ---- Etapa 3: resultado ----
    res = ad["res"]
    sc, vf, rw = res["escaneo"], res["auditoria"], res["reescritura"]
    c = st.columns(4)
    c[0].metric("Match CV general", f"{a.get('puntuacion_match', '?')}")
    c[1].metric("Match CV adaptado", f"{vf.get('puntuacion_match_final', '?')}",
                delta=(vf.get("puntuacion_match_final") or 0) - (a.get("puntuacion_match") or 0))
    c[2].metric("ATS", f"{sc.get('ats', {}).get('puntuacion', '?')}")
    c[3].metric("Historial", f"ID {res['id']}")
    b = st.columns(5)
    if b[0].button("📄 Abrir CV en Word"):
        abrir(res["docx"])
    if b[1].button("🌐 Abrir reporte"):
        abrir(res["reporte"])
    if b[2].button("📁 Abrir carpeta"):
        abrir(Path(res["docx"]).parent)
    with open(res["docx"], "rb") as fh:
        b[3].download_button("⬇️ Descargar DOCX", fh.read(), file_name=Path(res["docx"]).name)
    b[4].button("➕ Siguiente oferta", on_click=_reset_adapt, type="primary")
    st.caption(f"Guardado en: {res['docx']}" + (f" · PDF: {res['pdf']}" if res.get("pdf") else ""))

    ex = res.get("extras") or {}
    if ex.get("paginas") or ex.get("recortes"):
        st.caption(f"Páginas: {ex.get('paginas') or 'estimado ≤ ' + str(cfg['max_paginas_cv'])}"
                   + (f" · se quitaron {len(ex['recortes'])} bullet(s) de menor relevancia para caber" if ex.get("recortes") else ""))
    t = st.tabs(["CV final", "ATS + lector de 100 CVs", "Reescritura XYZ", "Auditoría", "Naturalidad", "Entrevista",
                 "Empresa", "Cover letter", "Subir el match", "Trainings"])
    with t[0]:
        st.markdown(cv_markdown(res["cv"]), unsafe_allow_html=True)
    with t[1]:
        st.info(f"**En 6 segundos ve:** {sc.get('lo_que_veo_en_6_segundos', '')}")
        st.markdown("**Palabras ausentes para el ATS:**")
        tags(sc.get("ats", {}).get("palabras_ausentes", []))
        for p in sc.get("partes_que_saltaria", []):
            with st.expander(f"Se saltaría: {p.get('parte', '')}"):
                st.caption(p.get("por_que", ""))
                st.markdown(f"<p class='antes'>{p.get('original', '')}</p>", unsafe_allow_html=True)
                st.markdown(f"✅ {p.get('reescritura', '')}")
    with t[2]:
        st.markdown("**Palabras clave incluidas**")
        tags(rw.get("palabras_clave_incluidas", []))
        st.markdown("**No incluidas por falta de evidencia (no se inventaron)**")
        for x in rw.get("palabras_clave_no_incluidas", []):
            st.markdown(f"- **{x.get('palabra')}**: {x.get('motivo')}")
        st.markdown("**Red flags eliminadas**")
        for x in rw.get("red_flags_eliminadas", []):
            st.markdown(f"- **{x.get('flag')}**: {x.get('como')}")
    with t[3]:
        nr = vf.get("afirmaciones_no_respaldadas", [])
        if not nr:
            st.success("No se encontraron afirmaciones sin respaldo.")
        for x in nr:
            st.warning(f"**{x.get('texto')}** — {x.get('problema')}\n\nCorrección: {x.get('correccion')}")
        st.caption(vf.get("comentario_puntuacion", ""))
        li = ex.get("linkedin") or []
        if li:
            st.markdown("**Diferencias con tu LinkedIn** (un reclutador las notaría):")
            st.dataframe(pd.DataFrame(li), hide_index=True)
        elif not (DATA_DIR / "linkedin.txt").exists():
            st.caption("Tip: pega tu perfil de LinkedIn en ⚙️ Configuración para detectar diferencias con el CV.")
    with t[4]:
        ie = res.get("estilo") or {}
        c1, c2, c3 = st.columns(3)
        c1.metric("Marcas de IA detectadas", ie.get("detectadas", 0))
        c2.metric("Corregidas", ie.get("corregidas", 0))
        c3.metric("Pendientes", len(ie.get("restantes", [])))
        for ch in ie.get("cambios", []):
            st.markdown(f"<p class='antes'>{ch.get('original', '')}</p>", unsafe_allow_html=True)
            st.markdown(f"✅ {ch.get('nuevo', '')}")
        for r in ie.get("restantes", []):
            st.warning(f"{r['texto']}  \n_{', '.join(r['marcas'])}_ — revísalo a mano en Word.")
        if not ie.get("detectadas"):
            st.success("No se detectaron frases típicas de IA.")
    with t[5]:
        ent = ex.get("entrevista") or {}
        if not ent:
            st.info("No se generó la preparación de entrevista (actívala en ⚙️ Configuración).")
        for q in ent.get("preguntas", []):
            with st.expander(("⚠️ " if not q.get("defendible", True) else "") + q.get("pregunta", "")):
                st.caption(q.get("sobre", ""))
                st.markdown(f"**S:** {q.get('situacion', '')}  \n**T:** {q.get('tarea', '')}  \n"
                            f"**A:** {q.get('accion', '')}  \n**R:** {q.get('resultado', '')}")
                if q.get("riesgo"):
                    st.warning(q["riesgo"])
        for b in ent.get("bullets_debiles", []):
            st.warning(f"Bullet difícil de defender: **{b.get('bullet')}** — {b.get('por_que')}")
    with t[6]:
        emp = ex.get("empresa") or {}
        if not emp:
            st.info("Sin investigación de la empresa.")
        else:
            st.markdown(f"**Industria:** {emp.get('industria', '')} · **Regulada:** {emp.get('regulada', '')} · "
                        f"**Tamaño:** {emp.get('tamano', '')}  \n**En Costa Rica:** {emp.get('presencia_costa_rica', '')}  \n"
                        f"**Cultura:** {emp.get('cultura_valores', '')}")
            st.markdown("**Qué se priorizó en tu CV:**")
            for x in emp.get("que_priorizar_en_cv", []):
                st.markdown(f"- {x}")
    with t[7]:
        _cover_ui(cfg, facts, cv, llm, res["id"])
    with t[8]:
        for s in a.get("sugerencias_para_subir_match", []) + vf.get("acciones_para_subir_mas", []):
            st.markdown(f"- {s}")
    with t[9]:
        for kw, trs in res["trainings"].items():
            st.markdown(f"**{kw}**")
            for tr in trs:
                st.markdown(f"- [{tr['nombre']}]({tr['url']}) · {tr['plataforma']} · {'Gratis' if tr['gratis'] else 'Pago/suscripción'}")


def _cover_ui(cfg, facts, cv, llm, rid):
    row = next((r for r in history.all_rows() if r["id"] == rid), None)
    if not row:
        return
    extras = json.loads(row.get("extras") or "{}")
    cov = extras.get("cover")
    if st.button("✉️ Generar cover letter + mensaje para el reclutador" if not cov else "🔄 Regenerar cover letter",
                 key=f"cov_{rid}") and requiere_ia(llm):
        with st.spinner("Redactando…"):
            cov = pipe_for(cfg, facts, cv, llm).cover_letter(row)
    if cov:
        st.text_input("Asunto", cov.get("asunto", ""), key=f"cova_{rid}")
        st.text_area("Mensaje para LinkedIn (≤300 caracteres)", cov.get("mensaje_linkedin", ""), key=f"covm_{rid}", height=90)
        st.text_area("Cover letter", cov.get("texto", ""), key=f"covt_{rid}", height=300)
        c1, c2 = st.columns(2)
        if c1.button("📄 Abrir cover letter en Word", key=f"covo_{rid}"):
            abrir(cov.get("docx"))
        if cov.get("docx") and Path(cov["docx"]).exists():
            with open(cov["docx"], "rb") as fh:
                c2.download_button("⬇️ Descargar", fh.read(), file_name=Path(cov["docx"]).name, key=f"covd_{rid}")


def pagina_historial(cfg, facts, cv, llm):
    st.title("Historial de solicitudes")
    rows = history.all_rows()
    if not rows:
        st.info("Historial vacío.")
        return
    df = pd.DataFrame(rows)
    filtro = st.multiselect("Filtrar por estado", history.ESTADOS, placeholder="Todos los estados")
    if filtro:
        df = df[df["estado"].isin(filtro)]
    vista = df[["id", "fecha", "empresa", "puesto", "url", "match_inicial", "match_final", "estado", "notas", "cv_docx"]].copy()
    vista["cv_docx"] = vista["cv_docx"].map(lambda p: Path(p).name if p else "")
    ed = st.data_editor(
        vista, hide_index=True, key="ed_hist",
        disabled=["id", "fecha", "empresa", "puesto", "url", "match_inicial", "match_final", "cv_docx"],
        column_config={"id": "ID", "fecha": "Fecha", "empresa": "Empresa", "puesto": "Puesto",
                       "url": st.column_config.LinkColumn("Link", display_text="abrir"),
                       "match_inicial": "Antes", "match_final": "Después",
                       "estado": st.column_config.SelectboxColumn("Estado", options=history.ESTADOS, required=True),
                       "notas": st.column_config.TextColumn("Notas"), "cv_docx": "CV a usar"})
    c = st.columns(3)
    if c[0].button("💾 Guardar cambios", type="primary"):
        orig = vista.set_index("id")
        for _, r in ed.iterrows():
            o = orig.loc[r["id"]]
            if r["estado"] != o["estado"] or (r["notas"] or "") != (o["notas"] or ""):
                history.update(int(r["id"]), estado=r["estado"], notas=r["notas"] or "")
        p = pipe_for(cfg, facts, cv, llm).export_history()
        st.success(f"Guardado. Excel actualizado: {p}")
    xls = cfg["_salida_path"] / "Historial_Solicitudes.xlsx"
    if c[1].button("📊 Abrir Excel"):
        pipe_for(cfg, facts, cv, llm).export_history()
        abrir(xls)
    if c[2].button("📁 Abrir carpeta de salida"):
        abrir(cfg["_salida_path"])

    st.divider()
    st.subheader("Detalle")
    ids = df["id"].tolist()
    rid = st.selectbox("Solicitud", ids, format_func=lambda i: next(f"#{r['id']} · {r['empresa']} — {r['puesto']}" for r in rows if r["id"] == i))
    r = next(x for x in rows if x["id"] == rid)
    st.markdown(f"**Link:** {r['url'] or '—'}  \n**CV:** `{r['cv_docx']}`  \n**Reporte:** `{r['reporte']}`")
    st.markdown("**Palabras clave que faltaban:**")
    tags(json.loads(r["palabras_faltantes"] or "[]"))
    b = st.columns(4)
    if b[0].button("📄 Abrir CV"):
        abrir(r["cv_docx"])
    if b[1].button("🌐 Abrir reporte"):
        abrir(r["reporte"])
    if b[2].button("📝 Ver JD guardado"):
        abrir(r["jd_path"])
    if r["cv_docx"] and Path(r["cv_docx"]).exists():
        with open(r["cv_docx"], "rb") as fh:
            b[3].download_button("⬇️ Descargar CV", fh.read(), file_name=Path(r["cv_docx"]).name)
    with st.expander("✉️ Cover letter y mensaje al reclutador"):
        _cover_ui(cfg, facts, cv, llm, r["id"])


def pagina_skills(cfg, facts, cv, llm):
    st.title("Top 5 habilidades que debes aprender")
    pipe = pipe_for(cfg, facts, cv, llm)
    cnt, ofertas, rows = pipe.gap_counts()
    if not rows:
        st.info("Necesitas al menos una oferta analizada.")
        return
    st.caption(f"Basado en {len(rows)} ofertas de tu historial. Excluye lo que confirmaste que ya dominas.")
    if st.button("🔄 Calcular / actualizar Top 5 (con cursos buscados en la web)", type="primary") and requiere_ia(llm):
        with st.spinner("Agrupando brechas y buscando cursos vigentes…"):
            out = pipe.top_skills()
        if out:
            st.success(f"Reporte guardado en {out[1]}")
    f = DATA_DIR / "top5_habilidades.json"
    if f.exists():
        top5 = json.loads(f.read_text(encoding="utf-8"))
        for i, s in enumerate(top5, 1):
            with st.container(border=True):
                st.markdown(f"### {i}. {s.get('habilidad', '')}")
                st.caption(f"Aparece en {s.get('aparece_en_ofertas', '?')} de {len(rows)} ofertas")
                st.write(s.get("por_que", ""))
                if s.get("certificacion_sugerida"):
                    st.markdown(f"**Certificación sugerida:** {s['certificacion_sugerida']}")
                for c in s.get("cursos", []):
                    st.markdown(f"- [{c.get('nombre', '')}]({c.get('url', '')}) · {c.get('plataforma', '')} · "
                                f"{'Gratis' if c.get('gratis') else 'Pago/suscripción'}")
        if st.button("🌐 Abrir reporte HTML"):
            abrir(cfg["_salida_path"] / "Top5_Habilidades.html")
        _plan_estudio(cfg, facts, cv, llm, [s.get("habilidad", "") for s in top5])
    if cnt:
        with st.expander("Todas las brechas por frecuencia (conteo directo, sin IA)"):
            st.dataframe(pd.DataFrame([{"Habilidad": h, "Peso": w, "Ofertas": ofertas.get(h, 0)}
                                       for h, w in cnt.most_common(40)]), hide_index=True)


def _plan_estudio(cfg, facts, cv, llm, habilidades):
    from cvmatch import extras as ex
    st.subheader("📚 Mi plan de estudio")
    st.caption("Marca tu avance. Al poner **terminado** con el detalle real (curso, certificación, fecha), se guarda como "
               "respuesta confirmada: entra en tus próximos CVs y puedes recalcular el match de tus ofertas guardadas.")
    p = ex.plan()
    with st.form("plan_estudio"):
        for i, h in enumerate([x for x in habilidades if x]):
            act = p.get(h, {})
            c1, c2 = st.columns([1, 3])
            c1.selectbox(h, ["pendiente", "en curso", "terminado"], key=f"plan_e_{i}",
                         index=["pendiente", "en curso", "terminado"].index(act.get("estado", "pendiente")))
            c2.text_input("Detalle real (ej. 'AZ-305 aprobada, oct 2026' o 'Curso CKA de Udemy, 30 h, labs')",
                          value=act.get("detalle", ""), key=f"plan_d_{i}")
        guardar = st.form_submit_button("💾 Guardar avance", type="primary")
    if guardar:
        n_term = 0
        for i, h in enumerate([x for x in habilidades if x]):
            e, d = st.session_state.get(f"plan_e_{i}"), st.session_state.get(f"plan_d_{i}", "")
            if e == "terminado" and not d.strip():
                st.warning(f"«{h}»: escribe el detalle real para marcarlo terminado (no se guarda sin evidencia).")
                e = "en curso"
            ex.marcar_estudio(h, e, d, facts)
            n_term += e == "terminado"
        st.success(f"Avance guardado ({n_term} terminado(s)).")
    if any(v.get("estado") == "terminado" for v in ex.plan().values()):
        if st.button("📈 Recalcular el match de mis ofertas guardadas con lo aprendido (gratis)"):
            with st.status("Re-evaluando ofertas…", expanded=True) as box:
                q, n = pipe_for(cfg, facts, cv, llm, box).reevaluar_todas()
                box.update(label=f"Listo: {n} ofertas re-evaluadas", state="complete", expanded=False)


def _banco_metricas(cfg, facts, cv, llm):
    st.subheader("📏 Banco de métricas")
    st.caption("Cifras reales para tus logros (equipos, servidores, usuarios, presupuestos, SLAs…). "
               "Se guardan como respuestas y se usan en todos los CVs. Deja en blanco lo que no sepas.")
    pipe = pipe_for(cfg, facts, cv, llm)
    f = DATA_DIR / "preguntas_metricas.json"
    c1, c2 = st.columns(2)
    gen = c1.button("Generar preguntas" if not f.exists() else "🔄 Generar nuevas preguntas")
    if gen and requiere_ia(llm):
        with st.spinner("Revisando tu CV…"):
            pipe.metric_questions(regenerar=True)
    if not f.exists():
        return
    preguntas = json.loads(f.read_text(encoding="utf-8"))
    respondidas = {i["habilidad"] for i in facts.items if i.get("origen") == "Banco de métricas"}
    with st.form("metricas"):
        for q in preguntas:
            nombre = f"Métrica: {q.get('rol', '')} — {q.get('logro', '')}".strip(" —:")
            hecho = "✅ " if nombre in respondidas else ""
            st.text_input(f"{hecho}{q.get('rol', '')}: {q.get('pregunta', '')}", key=f"met_{q.get('id')}",
                          placeholder=q.get("ejemplo_respuesta", ""))
        if st.form_submit_button("💾 Guardar cifras", type="primary"):
            n = 0
            for q in preguntas:
                v = st.session_state.get(f"met_{q.get('id')}", "").strip()
                if v:
                    pipe.save_metric(q, v)
                    n += 1
            st.success(f"{n} cifra(s) guardada(s).")


def pagina_respuestas(cfg, facts, cv, llm):
    _banco_metricas(cfg, facts, cv, llm)
    st.divider()
    st.title("Mis respuestas confirmadas")
    st.caption("Esto es lo ÚNICO que se suma a tu CV base. Edita, agrega filas al final o bórralas (selecciona la fila y pulsa Supr).")
    df = pd.DataFrame(facts.items or [], columns=["habilidad", "tiene", "detalle", "fecha", "origen"])
    q = st.text_input("Buscar", placeholder="ej. kubernetes")
    if q:
        st.dataframe(df[df.apply(lambda r: q.lower() in " ".join(map(str, r.values)).lower(), axis=1)], hide_index=True)
    ed = st.data_editor(df, num_rows="dynamic", hide_index=True, key="ed_facts",
                        column_config={"habilidad": st.column_config.TextColumn("Habilidad", required=True),
                                       "tiene": st.column_config.SelectboxColumn("¿La tienes?", options=["si", "parcial", "no"], required=True),
                                       "detalle": st.column_config.TextColumn("Detalle / evidencia", width="large"),
                                       "fecha": st.column_config.TextColumn("Fecha", disabled=True),
                                       "origen": st.column_config.TextColumn("Origen", disabled=True)})
    if st.button("💾 Guardar respuestas", type="primary"):
        from datetime import date
        items = []
        for _, r in ed.iterrows():
            if not str(r.get("habilidad") or "").strip():
                continue
            items.append({"habilidad": str(r["habilidad"]).strip(), "tiene": r.get("tiene") or "si",
                          "detalle": str(r.get("detalle") or ""), "fecha": r.get("fecha") or date.today().isoformat(),
                          "origen": r.get("origen") or "Agregado en la interfaz"})
        facts.items = items
        facts.save()
        st.success(f"{len(items)} respuestas guardadas.")


def _config_movil():
    from cvmatch import acceso
    d = acceso.cargar()
    with st.container(border=True):
        st.subheader("📱 Acceso desde el celular")
        st.write(("✅ Activado" if d.get("activado") and d.get("hash") else "❌ Desactivado")
                 + " · La laptop debe estar encendida con CV Match abierto.")
        if st.session_state.get("_remoto"):
            st.caption("Estás conectado desde otro dispositivo; esta sección se administra mejor desde la laptop.")
        c1, c2 = st.columns(2)
        clave1 = c1.text_input("Contraseña para el celular (mín. 8 caracteres)", type="password", key="mov_c1")
        clave2 = c2.text_input("Repite la contraseña", type="password", key="mov_c2")
        b1, b2, b3 = st.columns(3)
        if b1.button("Activar / cambiar contraseña", type="primary"):
            if len(clave1) < 8:
                st.error("Usa al menos 8 caracteres.")
            elif clave1 != clave2:
                st.error("Las contraseñas no coinciden.")
            else:
                acceso.poner_clave(clave1)
                d = acceso.cargar()
                d["activado"] = True
                acceso.guardar(d)
                st.success("Acceso activado.")
        if b2.button("Desactivar acceso"):
            d["activado"] = False
            acceso.guardar(d)
            st.success("Desactivado: desde otros dispositivos ya no se puede entrar.")
        if b3.button("Permitir en el firewall (una vez)"):
            ok, out = acceso.abrir_firewall()
            (st.success if ok else st.error)(
                "Windows te pedirá permiso de administrador; acepta. La regla solo permite tu red local y Tailscale."
                if ok else out)
        dirs = acceso.direcciones()
        cols = st.columns(2)
        with cols[0]:
            st.markdown("**🏠 En tu casa (misma Wi-Fi)**")
            if dirs.get("wifi"):
                st.code(dirs["wifi"])
                st.image(acceso.qr_png(dirs["wifi"]), width=170)
            else:
                st.caption("No detecté la red Wi-Fi.")
        with cols[1]:
            st.markdown("**🌎 Desde cualquier lugar (Tailscale)**")
            if dirs.get("tailscale"):
                st.code(dirs["tailscale"])
                st.image(acceso.qr_png(dirs["tailscale"]), width=170)
            else:
                st.caption("Tailscale no está instalado o no está conectado en esta laptop.")
        with st.expander("Cómo usarlo desde cualquier lugar con Tailscale (gratis, ~5 min)"):
            st.markdown("""
1. Instala **Tailscale** en la laptop (tailscale.com/download) e inicia sesión (puedes usar tu cuenta Microsoft).
2. Instala la app **Tailscale** en tu celular e inicia sesión con **la misma cuenta**.
3. Vuelve aquí: aparecerá la dirección 🌎 con su QR. Funciona con datos móviles, cifrado y sin abrir puertos del router.""")
        with st.expander("Ponerla como app en tu celular"):
            st.markdown("""
- **Android (Chrome):** abre la dirección → menú ⋮ → **Agregar a pantalla principal**.
- **iPhone (Safari):** abre la dirección → botón Compartir → **Agregar a inicio**.

Queda con ícono propio y se abre a pantalla completa. Los botones "Abrir en Word" abren cosas en la laptop; en el celular usa **⬇️ Descargar**.""")


def pagina_config(cfg, facts, cv, llm):
    st.title("Configuración")
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else {}
    from cvmatch import usuarios as _us
    _admin = (not multiusuario()) or _us.es_admin(st.session_state.get("_usuario", ""))
    _config_usuarios()
    if _admin:
        _config_movil()
    key = get_api_key()
    with st.container(border=True):
        st.subheader("API key de Anthropic")
        st.write(("✅ Configurada: " + key[:12] + "…" + key[-4:]) if key else "❌ No configurada")
        nueva = st.text_input("Reemplazar API key", type="password")
        if st.button("Guardar API key") and nueva.strip():
            save_api_key(nueva)
            get_llm.clear()
            st.success("API key guardada.")
            st.rerun()
    with st.container(border=True):
        st.subheader("🔎 Búsqueda web (Tavily → Claude) y ayudante gratis (Gemini)")
        from cvmatch import buscador_web as bwm
        st.caption("Buscar ofertas: 1) Tavily (1000 búsquedas gratis al mes) · 2) si falla, Claude (el más caro). "
                   "Gemini NO busca (su búsqueda de Google exige facturación); se usa gratis, sin internet, para leer "
                   "los resultados de Tavily, evaluar el match y revisar tus respuestas guardadas cuando Ollama está "
                   "cerrado, antes de gastar en Claude.")
        tk, gk = bwm.get_key("tavily"), bwm.get_key("gemini")
        k1, k2 = st.columns(2)
        k1.write(("✅ Tavily: " + tk[:9] + "…" + tk[-4:]) if tk else "❌ Tavily sin clave")
        k1.caption("Cuenta gratis en tavily.com → API Keys (empieza con tvly-).")
        nt = k1.text_input("Pegar clave de Tavily", key="in_tavily", placeholder="tvly-...")
        k2.write(("✅ Gemini: " + gk[:6] + "…" + gk[-4:]) if gk else "❌ Gemini sin clave")
        k2.caption("Clave gratis en aistudio.google.com → Get API key. En el plan gratis Google puede usar lo que envías "
                   "para mejorar sus productos.")
        ng = k2.text_input("Pegar clave de Gemini", key="in_gemini", placeholder="AIza...")
        bw = raw.get("busqueda_web") or {}
        cresp = st.checkbox("Usar Claude como último recurso si Tavily falla (~USD 0.026 por área)",
                            value=bool((cfg.get("busqueda_web") or {}).get("claude_respaldo", True)))
        if st.button("Guardar búsqueda web"):
            if nt.strip():
                bwm.save_key("tavily", nt)
            if ng.strip():
                bwm.save_key("gemini", ng)
            bw.update({"claude_respaldo": cresp})
            bw.pop("gemini_modelo", None)
            if bw.get("orden"):
                bw["orden"] = [x for x in bw["orden"] if x != "gemini"]
            raw["busqueda_web"] = bw
            CONFIG_PATH.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
            for k in ("in_tavily", "in_gemini"):
                st.session_state.pop(k, None)
            st.success("Guardado.")
            st.rerun()
        if st.button("Probar los buscadores"):
            from cvmatch.jobs import areas_config
            area = areas_config(cfg)[0]
            from cvmatch import gemini as _gem
            _gem._BLOQUEO[0] = 0.0
            for nombre, fn in (("Tavily (búsqueda)", lambda: bwm.buscar_tavily_ollama(cfg, area, 1, lambda m: None)),
                               ("Gemini (ayudante sin búsqueda)",
                                lambda: [1] if _gem.ask_json("Respondes en JSON.", 'Devuelve {"ok": true}').get("ok") else [])):
                with st.spinner(f"Probando {nombre}…"):
                    try:
                        r = fn()
                        msg = (f"{nombre}: funciona" if nombre.startswith("Gemini")
                               else f"{nombre}: funciona ({len(r)} ofertas de «{area['nombre']}»)")
                        st.success(msg)
                    except Exception as e:
                        msg = f"{nombre}: ERROR {e}"
                        st.error(msg)
                try:  # queda registrado para poder revisarlo después
                    from datetime import datetime as _dt
                    with open(DATA_DIR / "prueba_buscadores.log", "a", encoding="utf-8") as _f:
                        _f.write(f"{_dt.now().isoformat(timespec='seconds')} {msg}\n")
                except Exception:
                    pass
    with st.container(border=True):
        st.subheader("CV base")
        st.write(f"Actual: `{cfg['_cv_base_path']}`")
        up = st.file_uploader("Reemplazar CV base (PDF o DOCX)", type=["pdf", "docx"])
        if up and st.button("Usar este CV como base"):
            dest = dir_usuario_app() / f"CV_base{Path(up.name).suffix.lower()}"
            dest.write_bytes(up.getvalue())
            raw["cv_base"] = dest.name
            CONFIG_PATH.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
            get_cv.clear()
            st.success("CV base actualizado.")
    with st.container(border=True):
        st.subheader("🤖 Búsqueda automática")
        from cvmatch import scheduler
        est = scheduler.estado()
        if est:
            st.write(f"✅ Activa a las **{est.get('horas', '')}** · próxima: {est.get('proxima', '')} · última: {est.get('ultima', '')}")
        else:
            st.write("❌ No está programada")
        horas_txt = st.text_input("Horas (HH:MM, separadas por coma)",
                                  value=", ".join(cfg.get("busqueda_automatica", {}).get("horas", ["07:00", "13:00"])))
        st.caption("Recomendado: una vez temprano (ej. 06:45). Con Tavily + Ollama/Gemini es gratis; trae solo lo publicado "
                   "en las últimas horas que definas en 🎯 Calidad de la búsqueda, y si activas el resumen diario te llega "
                   "por correo. Se ejecuta aunque la app esté cerrada, con la PC encendida (si estaba apagada, corre al encenderla).")
        k1, k2, k3 = st.columns(3)
        if k1.button("Activar / actualizar horario", type="primary"):
            horas = [h.strip() for h in horas_txt.split(",") if h.strip()]
            raw.setdefault("busqueda_automatica", {})["horas"] = horas
            CONFIG_PATH.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
            ok, out = scheduler.activar(horas)
            (st.success if ok else st.error)("Programada." if ok else out)
        if k2.button("Desactivar"):
            ok, out = scheduler.desactivar()
            (st.success if ok else st.error)("Desactivada." if ok else out)
        if k3.button("Buscar ahora (en segundo plano)"):
            import subprocess
            args = [scheduler._pythonw(), str(APP_DIR / "buscar_auto.py")]
            if multiusuario():
                args += ["--usuario", st.session_state.get("_usuario", "")]
            subprocess.Popen(args, cwd=str(APP_DIR))
            st.info("Búsqueda iniciada. Recibirás una notificación al terminar.")
        logf = DATA_DIR / "busquedas_auto.log"
        if logf.exists():
            with st.expander("Registro de búsquedas automáticas"):
                st.code("\n".join(logf.read_text(encoding="utf-8").splitlines()[-40:]))
    with st.container(border=True):
        st.subheader("✍️ Tu forma de escribir (opcional)")
        st.caption("Pega 1-3 párrafos escritos por ti (un correo, un post de LinkedIn, un resumen de proyecto). "
                   "La app imitará tu tono y vocabulario al redactar el CV; nunca toma datos de aquí.")
        mf = DATA_DIR / "muestra_estilo.txt"
        muestra = st.text_area("Muestra", value=mf.read_text(encoding="utf-8") if mf.exists() else "", height=150)
        if st.button("Guardar muestra"):
            mf.write_text(muestra, encoding="utf-8")
            st.success("Muestra guardada.")
    with st.container(border=True):
        st.subheader("📧 Outlook (solo lectura)")
        from cvmatch import correo
        oc = dict(cfg.get("outlook") or {})
        cid = oc.get("client_id", "")
        conectado = correo.cuenta(cid) if cid else None
        st.write(f"✅ Conectado: **{conectado}**" if conectado else "❌ No conectado")
        with st.expander("Cómo registrar la app en Entra ID (una sola vez, ~5 min)", expanded=not cid):
            st.markdown("""
1. Entra a **portal.azure.com** → **Microsoft Entra ID** → **App registrations** → **New registration**.
2. Nombre: `CV Match`. Tipo de cuenta: **Personal Microsoft accounts only**. Redirect URI: déjalo vacío → **Register**.
3. En **Authentication** → *Advanced settings* → **Allow public client flows: Yes** → **Save**.
4. En **API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated** → marca **Mail.Read** → **Add**.
5. En **Overview**, copia el **Application (client) ID** y pégalo aquí abajo.

La app solo pide permiso de **lectura**: no puede enviar, borrar ni mover correos. El token se guarda solo en tu PC.""")
        c1, c2 = st.columns([3, 1])
        nuevo_cid = c1.text_input("Application (client) ID", value=cid, placeholder="00000000-0000-0000-0000-000000000000")
        dias = c2.number_input("Días a revisar", 3, 60, int(oc.get("dias_revisar", 14)))
        auto = st.checkbox("Revisar el correo también en la búsqueda automática", value=oc.get("revisar_en_busqueda_automatica", True))
        b1, b2, b3 = st.columns(3)
        if b1.button("Guardar"):
            raw["outlook"] = {"client_id": nuevo_cid.strip(), "dias_revisar": int(dias), "revisar_en_busqueda_automatica": auto}
            CONFIG_PATH.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
            st.success("Guardado.")
        if b2.button("🔐 Conectar con Microsoft", disabled=not (nuevo_cid.strip() or cid)):
            usar = nuevo_cid.strip() or cid
            if usar != cid:
                raw["outlook"] = {"client_id": usar, "dias_revisar": int(dias), "revisar_en_busqueda_automatica": auto}
                CONFIG_PATH.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
            try:
                flow = correo.iniciar_conexion(usar)
                st.info(f"1) Abre **{flow['verification_uri']}**  \n2) Escribe el código **{flow['user_code']}**  \n"
                        "3) Inicia sesión con tu cuenta de Outlook y acepta el permiso de lectura.")
                st.link_button("Abrir página de Microsoft", flow["verification_uri"])
                with st.spinner("Esperando a que inicies sesión…"):
                    quien = correo.completar_conexion(usar, flow)
                st.success(f"Conectado como {quien}.")
            except Exception as e:
                st.error(f"No se pudo conectar: {e}")
        if b3.button("Desconectar"):
            correo.desconectar()
            st.success("Desconectado. El token local se borró.")
    with st.container(border=True):
        st.subheader("📬 Resumen diario por correo")
        st.caption("Después de cada búsqueda (una vez al día) te envía A TU PROPIO correo de Outlook las mejores ofertas "
                   "nuevas y las de tus empresas favoritas. Requiere dar a la app permiso de envío (Mail.Send) una vez; "
                   "solo se usa para escribirte a ti.")
        rd = dict(cfg.get("resumen_diario") or {})
        r1, r2 = st.columns(2)
        rd_on = r1.checkbox("Activar resumen diario", value=bool(rd.get("activado")))
        rd_min = r2.number_input("Match mínimo para incluir", 40, 100, int(rd.get("match_minimo", 70)))
        x1, x2, x3 = st.columns(3)
        if x1.button("Guardar resumen"):
            raw["resumen_diario"] = {"activado": rd_on, "match_minimo": int(rd_min)}
            CONFIG_PATH.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
            st.success("Guardado.")
        if x2.button("🔐 Dar permiso para enviarme el resumen", disabled=not cid):
            try:
                flow = correo.iniciar_conexion(cid, con_envio=True)
                st.info(f"1) Abre **{flow['verification_uri']}**  \n2) Escribe el código **{flow['user_code']}**  \n"
                        "3) Acepta los permisos de leer y enviar correo. (Si Microsoft lo rechaza, agrega **Mail.Send** en "
                        "API permissions de tu app en Entra ID, igual que hiciste con Mail.Read.)")
                st.link_button("Abrir página de Microsoft", flow["verification_uri"])
                with st.spinner("Esperando a que inicies sesión…"):
                    quien = correo.completar_conexion(cid, flow)
                st.success(f"Permiso de envío listo para {quien}.")
            except Exception as e:
                st.error(f"No se pudo: {e}")
        if x3.button("✉️ Enviarme uno de prueba ahora", disabled=not cid):
            try:
                from cvmatch import extras as _ex
                from cvmatch.pipeline import load_results
                n = _ex.enviar_resumen(cfg, load_results(), lambda m: None, forzar=True)
                st.success(f"Enviado ({n} ofertas). Revisa tu bandeja de entrada.")
            except Exception as e:
                st.error(str(e))
    with st.container(border=True):
        st.subheader("🏢 Portales de empleo de empresas (sin IA, sin créditos)")
        st.caption("Se lee directo la lista de vacantes de cada portal (Workday, Greenhouse, Lever, SmartRecruiters, Ashby) "
                   "y se queda con lo de Costa Rica/remoto de tus áreas: link directo, descripción completa y fecha real. "
                   "Pega la URL de la página de empleos de la empresa (ej. https://empresa.wd5.myworkdayjobs.com/Careers). "
                   "Cuando una buena oferta venga de uno de estos portales, se agrega solo.")
        from cvmatch import portales as _po
        ps = _po.lista()
        for i, p_ in enumerate(ps):
            a, b, c = st.columns([2, 5, 1])
            tipo, _ = _po.detectar(p_["url"])
            a.write(f"**{p_.get('empresa') or '—'}**  \n<small>{tipo} · {p_.get('origen', '')}</small>", unsafe_allow_html=True)
            b.caption(p_["url"])
            if c.button("Quitar", key=f"po_del_{i}"):
                _po.guardar([x for k, x in enumerate(ps) if k != i])
                st.rerun()
        n1, n2, n3 = st.columns([2, 5, 1])
        pe = n1.text_input("Empresa", key="po_emp")
        pu = n2.text_input("URL del portal de empleos", key="po_url", placeholder="https://jobs.lever.co/empresa")
        n3.write("")
        if n3.button("Agregar"):
            if _po.agregar(pe, pu):
                st.success("Agregado.")
                st.rerun()
            else:
                st.error("No reconozco ese portal (o ya está). Sirven URLs de myworkdayjobs.com, greenhouse.io, lever.co, "
                         "smartrecruiters.com o ashbyhq.com.")
        if st.button("Probar portales ahora"):
            msgs = []
            with st.spinner("Leyendo portales…"):
                r = _po.leer_todos(cfg, msgs.append)
            for m in msgs:
                (st.warning if "no disponible" in m else st.write)(m)
            try:
                with open(DATA_DIR / "prueba_buscadores.log", "a", encoding="utf-8") as _f:
                    from datetime import datetime as _dt
                    _f.write(f"{_dt.now().isoformat(timespec='seconds')} Portales: " + " | ".join(msgs) + "\n")
            except Exception:
                pass
    with st.container(border=True):
        st.subheader("🎯 Calidad de la búsqueda")
        bq = cfg["busqueda"]
        q1, q2 = st.columns(2)
        v_vig = q1.checkbox("Ocultar ofertas cerradas (revisa cada link, gratis)", value=bool(bq.get("verificar_vigencia", True)))
        v_apa = q2.checkbox("Omitir bolsas que no aportan ofertas útiles", value=bool(bq.get("apagar_fuentes_sin_rendimiento", True)))
        v_por = q1.checkbox("Revisar portales de empresas en cada búsqueda", value=bool(bq.get("usar_portales", True)))
        v_sop = q2.checkbox("Permitir puestos junior/associate en soporte TI", value=bool(bq.get("nivel_bajo_en_soporte", True)))
        niv = st.text_input("Palabras de nivel que se descartan (separadas por coma)", value=", ".join(bq.get("excluir_nivel", [])))
        perf = st.text_area("Perfil objetivo (qué puestos buscas y cuáles no; lo usa el filtro rápido para dar el match)",
                            value=cfg.get("perfil_objetivo", ""), height=170)
        rec = st.number_input("Búsqueda automática: solo lo publicado en las últimas N horas (0 = sin límite)", 0, 336,
                              int(bq.get("auto_solo_recientes_horas", 48) or 0))
        if st.button("Guardar calidad de búsqueda"):
            bb = raw.get("busqueda", {})
            bb.update({"verificar_vigencia": v_vig, "apagar_fuentes_sin_rendimiento": v_apa, "usar_portales": v_por,
                       "nivel_bajo_en_soporte": v_sop, "auto_solo_recientes_horas": int(rec),
                       "excluir_nivel": [x.strip() for x in niv.split(",") if x.strip()]})
            raw["busqueda"] = bb
            if perf.strip():
                raw["perfil_objetivo"] = perf.strip()
            CONFIG_PATH.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
            st.success("Guardado.")
    with st.container(border=True):
        st.subheader("⭐ Empresas favoritas")
        st.caption("Sus ofertas se marcan con ⭐, se muestran aunque el match sea menor y van primero en el resumen. "
                   "Además, una vez al día la búsqueda web revisa sus ofertas en Costa Rica (~5 créditos de Tavily).")
        favs = st.text_area("Una por línea", value="\n".join(cfg.get("empresas_favoritas", [])), height=160)
        f1, f2 = st.columns(2)
        bfav = f1.checkbox("Buscar ofertas de mis favoritas una vez al día", value=bool(cfg.get("buscar_en_favoritas", True)))
        dvieja = f2.number_input("Días para considerar una oferta vieja", 7, 90, int(cfg.get("dias_oferta_vieja", 30)))
        if st.button("Guardar favoritas"):
            raw["empresas_favoritas"] = [x.strip() for x in favs.splitlines() if x.strip()]
            raw["buscar_en_favoritas"] = bfav
            raw["dias_oferta_vieja"] = int(dvieja)
            CONFIG_PATH.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
            st.success("Guardado.")
    with st.container(border=True):
        st.subheader("🔗 Tu perfil de LinkedIn (opcional)")
        st.caption("Abre tu perfil, selecciona todo (Ctrl+A), copia y pega aquí. Se usa solo para avisarte de "
                   "diferencias entre el CV y LinkedIn (títulos, fechas); nunca se toman datos de aquí.")
        lf = DATA_DIR / "linkedin.txt"
        lt = st.text_area("Perfil", value=lf.read_text(encoding="utf-8") if lf.exists() else "", height=150, key="li_txt")
        if st.button("Guardar perfil de LinkedIn"):
            lf.write_text(lt, encoding="utf-8")
            st.success("Guardado.")
    with st.container(border=True):
        st.subheader("🗣️ Cómo declarar tus idiomas")
        st.caption("Muchas empresas en Costa Rica hacen prueba de inglés hablado: declara el nivel que puedas sostener. "
                   "Referencia: Native · Fluent (C1-C2) · Professional working proficiency (B2) · Intermediate (B1). "
                   "Vacío = se usa lo que dice tu CV base.")
        idi = st.text_input("Texto exacto para el CV", value=cfg.get("idiomas_declarados", ""),
                            placeholder="Spanish (Native) · English (Professional working proficiency)")
        if st.button("Guardar idiomas"):
            raw["idiomas_declarados"] = idi.strip()
            CONFIG_PATH.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
            st.success("Guardado.")
    with st.container(border=True):
        st.subheader("🦙 Ollama (IA local gratis, opcional)")
        st.caption("Si instalas Ollama (ollama.com) y descargas un modelo, la app lo usa para evaluar ofertas sin costo. "
                   "Si no responde, usa Claude automáticamente. Requiere 16 GB de RAM o más.")
        oc = dict(cfg.get("ollama") or {})
        o1, o2, o3 = st.columns([1, 2, 2])
        usar = o1.checkbox("Usar Ollama", value=bool(oc.get("usar_para_evaluar_ofertas")))
        om = o2.text_input("Modelo (o familia, ej. qwen2.5)", value=oc.get("modelo", "qwen2.5"))
        ou = o3.text_input("URL", value=oc.get("url", "http://localhost:11434"))
        q1, q2 = st.columns(2)
        if q1.button("Probar conexión"):
            from cvmatch import ollama
            ok, modelos = ollama.disponible(ou)
            if ok:
                elegido = ollama.elegir_modelo(om, modelos)
                if elegido:
                    st.success(f"Ollama responde. Instalados: {', '.join(modelos)}. La app usará: **{elegido}**.")
                else:
                    st.warning(f"Ollama responde pero no tiene modelos. En una terminal: ollama pull {om}")
            else:
                st.error("Ollama no responde en esa URL. ¿Está instalado y abierto?")
        if q2.button("Guardar Ollama"):
            raw["ollama"] = {"usar_para_evaluar_ofertas": usar, "modelo": om.strip(), "url": ou.strip()}
            CONFIG_PATH.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
            st.success("Guardado.")
    with st.container(border=True):
        st.subheader("🖥️ Acceso directo y seguridad")
        a1, a2 = st.columns(2)
        if a1.button("Crear acceso directo en el escritorio"):
            ok, out = crear_acceso_directo()
            (st.success if ok else st.error)("Acceso directo 'CV Match' creado en tu escritorio." if ok else out)
        a2.caption("Seguridad: si tu API key quedó escrita en algún chat, crea una nueva en console.anthropic.com → "
                   "API Keys, bórrala allá y pégala arriba en 'Reemplazar API key'.")
        rp = DATA_DIR / "respaldos"
        if rp.exists():
            ult = sorted(p.name for p in rp.iterdir() if p.is_dir())
            st.caption(f"Respaldos diarios: {len(ult)} (último: {ult[-1] if ult else '—'}) en datos\\respaldos")
    with st.container(border=True):
        st.subheader("🤖 Modelo por tarea")
        st.caption("Haiku es ~20 veces más barato que Sonnet. Generar y auditar el CV usa los modelos de Preferencias.")
        mpt = dict(cfg.get("modelos_por_tarea") or {})
        etiquetas = {"ranking": "Evaluar ofertas encontradas", "busqueda_web": "Búsqueda web en Costa Rica",
                     "top5": "Top 5 habilidades", "pulido_estilo": "Pulido de estilo humano",
                     "empresa": "Investigar la empresa", "seguimiento": "Correos de seguimiento"}
        cols = st.columns(2)
        nuevos = {}
        for k, (tarea, etiqueta) in enumerate(etiquetas.items()):
            actual = mpt.get(tarea, cfg["modelo_analisis"])
            nuevos[tarea] = cols[k % 2].selectbox(etiqueta, MODELOS, index=MODELOS.index(actual) if actual in MODELOS else 0,
                                                 key=f"mpt_{tarea}")
        if st.button("Guardar modelos por tarea"):
            raw["modelos_por_tarea"] = nuevos
            CONFIG_PATH.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
            st.success("Guardado.")
    with st.form("cfg"):
        st.subheader("Preferencias")
        salida = st.text_input("Carpeta de salida", value=str(cfg["_salida_path"]))
        c1, c2 = st.columns(2)
        m1 = c1.selectbox("Modelo de análisis", MODELOS, index=MODELOS.index(cfg["modelo_analisis"]) if cfg["modelo_analisis"] in MODELOS else 0)
        m2 = c2.selectbox("Modelo de redacción (Opus = mejor y más caro)", MODELOS,
                          index=MODELOS.index(cfg["modelo_redaccion"]) if cfg["modelo_redaccion"] in MODELOS else 1)
        c3, c4, c5 = st.columns(3)
        pag = c3.number_input("Máximo de páginas del CV", 1, 4, int(cfg["max_paginas_cv"]))
        minimo = c4.number_input("Match mínimo a mostrar", 0, 100, int(cfg["puntaje_minimo_mostrar"]))
        maxo = c5.number_input("Máx. ofertas a evaluar por búsqueda", 5, 100, int(cfg["max_ofertas_a_rankear"]))
        p1, p2 = st.columns(2)
        presu = p1.number_input("Presupuesto mensual en USD (0 = sin tope)", 0.0, 500.0,
                                float(cfg.get("presupuesto_mensual_usd", 5.0)), step=1.0)
        hweb = p2.number_input("Horas mínimas entre búsquedas web", 0, 48, int(cfg.get("horas_entre_busquedas_web", 6)))
        pdf = st.checkbox("Generar PDF (requiere Microsoft Word)", value=cfg["generar_pdf"])
        trweb = st.checkbox("Buscar cursos en la web para el Top 5", value=cfg["trainings_con_busqueda_web"])
        inv = st.checkbox("Investigar la empresa antes de redactar (~USD 0.01)", value=cfg.get("investigar_empresa", True))
        ent = st.checkbox("Preparar preguntas de entrevista con cada CV (~USD 0.05)", value=cfg.get("preparar_entrevista", True))
        dseg = st.number_input("Días sin respuesta para recordar seguimiento", 3, 30, int(cfg.get("dias_para_seguimiento", 7)))
        cr = st.checkbox("Búsqueda web de ofertas en Costa Rica", value=cfg["busqueda"]["buscar_costa_rica_con_ia"])
        _todas_f = ["remotive", "remoteok", "himalayas", "jobicy", "weworkremotely", "workingnomads"]
        fuentes = st.multiselect("Bolsas remotas", _todas_f,
                                 default=[f for f in cfg["busqueda"]["fuentes_remotas"] if f in _todas_f])
        from cvmatch.jobs import areas_config as _ac
        txt_areas = st.text_area("Áreas de búsqueda (una por línea: Nombre: término 1, término 2, …)",
                                 value="\n".join(f"{a['nombre']}: {', '.join(a['terminos'])}" for a in _ac(cfg)), height=230,
                                 help="Cada área se busca por separado. Los términos sirven para reconocer las ofertas de esa "
                                      "área (en el título; VMware, HCX, Hybrid Cloud, Azure y GCP también en la descripción).")
        exc1 = st.text_area("Títulos que NO buscas (se descartan siempre; uno por línea)",
                            value="\n".join(cfg["busqueda"].get("excluir_titulos", [])), height=120)
        exc2 = st.text_area("Títulos que se descartan salvo que también digan infraestructura/cloud/SRE/DevOps/soporte "
                            "(uno por línea)", value="\n".join(cfg["busqueda"].get("excluir_salvo_infra", [])), height=100)
        a1, a2 = st.columns(2)
        maxarea = a1.number_input("Ofertas nuevas a evaluar por área", 2, 30, int(cfg["busqueda"].get("max_por_area", 8)))
        nbus = a2.number_input("Búsquedas web por área (cada una ~USD 0.01)", 1, 5, int(cfg["busqueda"].get("busquedas_web_por_area", 2)))
        if st.form_submit_button("💾 Guardar configuración", type="primary"):
            try:
                rel = os.path.relpath(salida, APP_DIR)
            except ValueError:
                rel = salida
            raw.update({"carpeta_salida": rel, "modelo_analisis": m1, "modelo_redaccion": m2, "max_paginas_cv": int(pag),
                        "puntaje_minimo_mostrar": int(minimo), "max_ofertas_a_rankear": int(maxo), "generar_pdf": pdf,
                        "trainings_con_busqueda_web": trweb, "investigar_empresa": inv, "preparar_entrevista": ent,
                        "dias_para_seguimiento": int(dseg), "presupuesto_mensual_usd": float(presu),
                        "horas_entre_busquedas_web": int(hweb)})
            b = raw.get("busqueda", {})
            nuevas_areas = []
            for linea in txt_areas.splitlines():
                if ":" in linea:
                    nom, _, ter = linea.partition(":")
                    ters = [t.strip() for t in ter.split(",") if t.strip()]
                    if nom.strip() and ters:
                        nuevas_areas.append({"nombre": nom.strip(), "terminos": ters})
                elif linea.strip():
                    nuevas_areas.append({"nombre": linea.strip(), "terminos": [linea.strip().lower()]})
            b["excluir_titulos"] = [x.strip() for x in exc1.splitlines() if x.strip()]
            b["excluir_salvo_infra"] = [x.strip() for x in exc2.splitlines() if x.strip()]
            b.update({"buscar_costa_rica_con_ia": cr, "fuentes_remotas": fuentes, "max_por_area": int(maxarea),
                      "busquedas_web_por_area": int(nbus)})
            if nuevas_areas:
                b["areas"] = nuevas_areas
            raw["busqueda"] = b
            CONFIG_PATH.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
            get_llm.clear()
            st.success("Configuración guardada.")


def _puerta():
    """Desde la laptop se entra directo; desde otro dispositivo se pide contraseña (si el acceso está activado)."""
    from cvmatch import acceso
    try:
        ip = st.context.ip_address
        host = st.context.headers.get("Host", "")
    except Exception:
        ip, host = "desconocido", ""
    if acceso.es_local(ip, host):
        st.session_state._remoto = False
        return True
    st.session_state._remoto = True
    d = acceso.cargar()
    if multiusuario():  # con usuarios, el acceso remoto solo necesita estar activado: cada uno entra con su contraseña
        if not d.get("activado"):
            st.error("El acceso desde otros dispositivos está desactivado. Un administrador puede activarlo en la "
                     "laptop: ⚙️ Configuración → 📱 Acceso desde el celular.")
            return False
        return True
    if not d.get("activado") or not d.get("hash"):
        st.error("El acceso desde otros dispositivos está desactivado. Actívalo en la laptop: "
                 "⚙️ Configuración → 📱 Acceso desde el celular.")
        return False
    if st.session_state.get("_auth"):
        return True
    st.markdown("## 📄 CV Match")
    with st.form("login"):
        clave = st.text_input("Contraseña", type="password")
        entrar = st.form_submit_button("Entrar", type="primary")
    if entrar:
        if acceso.verificar(clave):
            st.session_state._auth = True
            st.rerun()
        else:
            import time
            time.sleep(2)  # frena intentos repetidos
            st.error("Contraseña incorrecta.")
    return False


# ---------------- formularios y simulador ----------------
def pagina_formularios(cfg, facts, cv, llm):
    from cvmatch import extras as ex
    st.title("📝 Respuestas para formularios")
    st.caption("Pega una pregunta de un formulario de postulación. La app busca si ya respondiste algo parecido y arma "
               "una respuesta solo con tus datos reales (CV + respuestas confirmadas). La revisas, la editas y la guardas: "
               "la próxima vez que salga una pregunta parecida, se reutiliza.")
    pipe = pipe_for(cfg, facts, cv, llm)
    with st.form("form_preg"):
        preg = st.text_area("Pregunta del formulario", height=80,
                            placeholder="Tell us about your experience with most relevant tech? (Go, TypeScript, Databases, IaC tools)")
        c1, c2, c3 = st.columns([2, 2, 1])
        emp = c1.text_input("Empresa (opcional)")
        pue = c2.text_input("Puesto (opcional)")
        largo = c3.selectbox("Largo", ["40-80 palabras", "80-150 palabras", "150-250 palabras"], index=1)
        ir = st.form_submit_button("✨ Armar respuesta", type="primary")
    if ir and preg.strip():
        with st.spinner("Buscando respuestas parecidas y redactando con tus datos…"):
            try:
                data, previas = ex.responder_formulario(pipe, preg, emp, pue, largo)
                st.session_state.form_resp = {"pregunta": preg, "empresa": emp,
                                              "texto": data.get("respuesta", ""), "datos": data.get("datos_usados", []),
                                              "sin": data.get("temas_sin_evidencia", []),
                                              "previas": [r["pregunta"] for r in previas]}
                st.session_state.form_txt = data.get("respuesta", "")
            except Exception as e:
                st.error(f"No pude armar la respuesta: {e}")
    fr = st.session_state.get("form_resp")
    if fr:
        with st.container(border=True):
            if fr["previas"]:
                st.caption("♻️ Reutilicé tus respuestas guardadas para: " + " · ".join(fr["previas"]))
            st.text_area("Respuesta (edítala a tu gusto)", key="form_txt", height=220)
            if fr["sin"]:
                st.warning("Sin evidencia en tus datos (se dijo con honestidad, no se inventó): " + ", ".join(fr["sin"]))
            if fr["datos"]:
                st.caption("Datos usados: " + " · ".join(fr["datos"]))
            g1, g2 = st.columns(2)
            if g1.button("💾 Guardar en mi banco", type="primary"):
                ex.guardar_respuesta(fr["pregunta"], st.session_state.get("form_txt", ""), fr.get("empresa", ""))
                st.success("Guardada. Se reutilizará en preguntas parecidas.")
            if g2.button("Descartar"):
                st.session_state.pop("form_resp", None)
                st.rerun()
    b = ex.banco()
    st.subheader(f"Mi banco de respuestas ({len(b)})")
    filtro = st.text_input("Buscar en el banco", placeholder="terraform, liderazgo, why us…")
    for i, r in enumerate(b):
        if filtro and filtro.lower() not in (r["pregunta"] + r["respuesta"]).lower():
            continue
        with st.expander(f"{r['pregunta'][:110]}  ·  {r.get('fecha', '')}"):
            st.code(r["respuesta"], language=None, wrap_lines=True)
            if st.button("🗑️ Borrar", key=f"borrar_banco_{i}"):
                ex.borrar_respuesta(i)
                st.rerun()


def pagina_simulador(cfg, facts, cv, llm):
    from cvmatch import extras as ex
    st.title("🎤 Simular entrevista")
    st.caption("Practica con las preguntas que la app preparó para cada CV que generaste. Escribe (o dicta con Win+H) tu "
               "respuesta y recibe una nota, qué estuvo bien, qué mejorar y la siguiente pregunta que te harían. "
               "Usa Ollama/Gemini (gratis); Haiku solo si no están.")
    pipe = pipe_for(cfg, facts, cv, llm)
    filas = []
    for r in history.all_rows():
        try:
            e = json.loads(r.get("extras") or "{}")
        except Exception:
            e = {}
        preguntas = [q.get("pregunta") for q in (e.get("entrevista") or {}).get("preguntas", []) if q.get("pregunta")]
        filas.append((r, preguntas))
    if not filas:
        st.info("Genera al menos un CV en ✍️ Adaptar CV para tener preguntas de práctica.")
        return
    i = st.selectbox("Oferta", range(len(filas)),
                     format_func=lambda k: f"#{filas[k][0]['id']} {filas[k][0]['empresa']} — {filas[k][0]['puesto']}")
    fila, preguntas = filas[i]
    generales = ["Tell me about yourself.", "Why do you want to work here?",
                 "Tell me about a migration that went wrong and what you did.",
                 "How do you handle a stakeholder who disagrees with your architecture?"]
    opciones = preguntas + [g for g in generales if g not in preguntas]
    rep_prev = st.session_state.get("sim_repregunta")
    if rep_prev and rep_prev not in opciones:
        opciones = [rep_prev] + opciones
    preg = st.selectbox("Pregunta", opciones)
    with st.form("sim"):
        resp = st.text_area("Tu respuesta", height=180)
        ev = st.form_submit_button("🎯 Evaluar mi respuesta", type="primary")
    if ev and resp.strip():
        with st.spinner("Evaluando como entrevistador…"):
            try:
                st.session_state.sim_eval = ex.evaluar_practica(pipe, fila["puesto"], fila["empresa"], preg, resp)
            except Exception as e:
                st.error(f"No pude evaluar: {e}")
    d = st.session_state.get("sim_eval")
    if d:
        with st.container(border=True):
            st.metric("Nota", f"{d.get('nota', '?')}/10")
            c1, c2 = st.columns(2)
            c1.markdown("**Bien:**\n" + "\n".join(f"- {x}" for x in d.get("bien", [])))
            c2.markdown("**Mejorar:**\n" + "\n".join(f"- {x}" for x in d.get("mejorar", [])))
            if d.get("respuesta_mejorada"):
                st.markdown("**Versión mejorada (solo con tus datos):**")
                st.write(d["respuesta_mejorada"])
            if d.get("repregunta"):
                st.info(f"🔁 Te repreguntarían: **{d['repregunta']}**")
                if st.button("Practicar esa repregunta"):
                    st.session_state.sim_repregunta = d["repregunta"]
                    st.session_state.pop("sim_eval", None)
                    st.rerun()
    hist = [h for h in ex.practicas() if h.get("empresa") == fila["empresa"]]
    if hist:
        with st.expander(f"Historial de práctica para {fila['empresa']} ({len(hist)})"):
            st.dataframe(pd.DataFrame(hist)[["fecha", "pregunta", "nota"]], hide_index=True)


# ---------------- usuarios (modo multiusuario) ----------------
def _login():
    """Pantalla de inicio de sesión. La primera vez crea el administrador."""
    from cvmatch import usuarios
    st.markdown("## 📄 CV Match")
    if not usuarios.hay_usuarios():
        st.info("Primera vez: crea la cuenta de **administrador**. Después podrás crear usuarios para otras personas; "
                "cada uno tendrá sus propios datos, CV, claves e historial.")
        modo = "crear_admin"
    else:
        modo = st.radio("Modo", ["Iniciar sesión", "Crear cuenta"] if usuarios.registro_abierto() else ["Iniciar sesión"],
                        horizontal=True, label_visibility="collapsed")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        p2 = st.text_input("Repite la contraseña", type="password") if modo in ("crear_admin", "Crear cuenta") else None
        ok = st.form_submit_button("Entrar" if modo == "Iniciar sesión" else "Crear cuenta", type="primary")
    if ok:
        if modo == "Iniciar sesión":
            if usuarios.verificar(u, p):
                st.session_state._usuario = usuarios.normalizar(u)
                st.rerun()
            st.error("Usuario o contraseña incorrectos.")
        else:
            if p != p2:
                st.error("Las contraseñas no coinciden.")
                return
            try:
                st.session_state._usuario = usuarios.crear(u, p, admin=(modo == "crear_admin"))
                st.rerun()
            except ValueError as e:
                st.error(str(e))


def _config_usuarios():
    from cvmatch import usuarios
    yo = st.session_state.get("_usuario", "")
    with st.container(border=True):
        st.subheader("👥 Usuarios")
        if not multiusuario():
            st.caption("Ahora la app es de una sola persona. Puedes convertirla en **multiusuario**: cada persona entra con "
                       "su usuario y contraseña y tiene sus propios datos. Tus datos actuales pasan a tu usuario "
                       "(administrador); no se pierde nada.")
            with st.form("migrar"):
                mu = st.text_input("Tu usuario (administrador)")
                mp = st.text_input("Contraseña (mín. 8)", type="password")
                mp2 = st.text_input("Repite la contraseña", type="password")
                go = st.form_submit_button("Activar modo multiusuario")
            if go:
                if mp != mp2:
                    st.error("Las contraseñas no coinciden.")
                else:
                    try:
                        nombre = usuarios.migrar_a_multiusuario(mu, mp)
                        st.session_state.clear()
                        st.session_state._usuario = nombre
                        st.success("Listo. Desde ahora se entra con usuario y contraseña.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
            return
        st.write(f"Sesión iniciada como **{yo}**" + (" (administrador)" if usuarios.es_admin(yo) else ""))
        with st.expander("Cambiar mi contraseña"):
            with st.form("cambiar_clave"):
                actual = st.text_input("Contraseña actual", type="password")
                n1 = st.text_input("Nueva contraseña", type="password")
                n2 = st.text_input("Repite la nueva", type="password")
                if st.form_submit_button("Cambiar"):
                    if n1 != n2:
                        st.error("No coinciden.")
                    elif not usuarios.verificar(yo, actual):
                        st.error("La contraseña actual no es correcta.")
                    else:
                        try:
                            usuarios.cambiar_clave(yo, n1)
                            st.success("Contraseña cambiada.")
                        except ValueError as e:
                            st.error(str(e))
        if not usuarios.es_admin(yo):
            return
        st.markdown("**Administración**")
        reg = st.checkbox("Permitir que cualquiera cree su cuenta desde la pantalla de inicio",
                          value=usuarios.registro_abierto())
        if reg != usuarios.registro_abierto():
            usuarios.poner_registro_abierto(reg)
        for i, u in enumerate(usuarios.lista()):
            a, b, c, d = st.columns([2, 1, 2, 1])
            a.write(f"**{u['usuario']}**  \n<small>desde {u.get('creado', '')}</small>", unsafe_allow_html=True)
            adm = b.checkbox("admin", value=bool(u.get("admin")), key=f"us_adm_{i}")
            if adm != bool(u.get("admin")):
                try:
                    usuarios.poner_admin(u["usuario"], adm)
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
            nueva = c.text_input("Nueva contraseña", type="password", key=f"us_pw_{i}", label_visibility="collapsed",
                                 placeholder="Nueva contraseña")
            if nueva and c.button("Restablecer", key=f"us_rst_{i}"):
                try:
                    usuarios.cambiar_clave(u["usuario"], nueva)
                    st.success(f"Contraseña de {u['usuario']} restablecida.")
                except ValueError as e:
                    st.error(str(e))
            if u["usuario"] != yo and d.button("Borrar", key=f"us_del_{i}"):
                try:
                    usuarios.borrar(u["usuario"], borrar_datos=False)
                    st.success(f"{u['usuario']} ya no puede entrar (sus datos se conservan en datos/usuarios).")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
        with st.form("nuevo_usuario"):
            st.markdown("Crear usuario")
            n1, n2, n3 = st.columns([2, 2, 1])
            nu = n1.text_input("Usuario", key="nu_u")
            npw = n2.text_input("Contraseña inicial", type="password", key="nu_p")
            nad = n3.checkbox("admin", key="nu_a")
            if st.form_submit_button("Crear"):
                try:
                    usuarios.crear(nu, npw, admin=nad)
                    st.success(f"Usuario {nu} creado. Que cambie su contraseña al entrar.")
                except ValueError as e:
                    st.error(str(e))


# ---------------- cerrar sesión ----------------
def _cerrar_procesos(cerrar_ollama):
    """Apaga la app (y Ollama si se pide) un momento después, para que alcance a mostrarse el mensaje."""
    import subprocess
    import threading
    import time

    def _apagar():
        time.sleep(2)
        if os.name == "nt":
            sin_ventana = 0x08000000  # CREATE_NO_WINDOW
            if cerrar_ollama:
                for exe in ("ollama app.exe", "ollama.exe"):
                    subprocess.run(["taskkill", "/IM", exe, "/F", "/T"], capture_output=True, creationflags=sin_ventana)
            # si la app se abrió con ejecutar_gui.bat, se cierra también esa ventana negra
            try:
                ppid = os.getppid()
                out = subprocess.run(["tasklist", "/FI", f"PID eq {ppid}", "/FO", "CSV", "/NH"],
                                     capture_output=True, text=True, creationflags=sin_ventana).stdout.lower()
                if "cmd.exe" in out:
                    subprocess.run(["taskkill", "/PID", str(ppid), "/T", "/F"], capture_output=True,
                                   creationflags=sin_ventana)
            except Exception:
                pass
        elif cerrar_ollama:
            subprocess.run(["pkill", "-x", "ollama"], capture_output=True)
        os._exit(0)
    threading.Thread(target=_apagar, daemon=True).start()


def _boton_cerrar():
    remoto = st.session_state.get("_remoto", False)
    if not st.session_state.get("_confirmar_cierre"):
        if st.button("⏻ Cerrar sesión", key="btn_cerrar", use_container_width=True):
            st.session_state._confirmar_cierre = True
            st.rerun()
        return
    with st.container(border=True):
        from cvmatch import usuarios as _us
        if multiusuario():
            st.markdown("**¿Cerrar tu sesión?**")
            puede_apagar = (not remoto) and _us.es_admin(st.session_state.get("_usuario", ""))
            apagar = puede_apagar and st.checkbox("Apagar también la app para todos (solo administrador)", value=False,
                                                  key="cierre_apagar")
            olla = apagar and st.checkbox("Cerrar también Ollama", value=True, key="cierre_ollama")
        elif remoto:
            st.markdown("**¿Cerrar sesión en este dispositivo?**")
            apagar = st.checkbox("Apagar también la app en la laptop (tendrás que abrirla allá de nuevo)", value=False,
                                 key="cierre_apagar")
            olla = apagar and st.checkbox("Cerrar también Ollama", value=True, key="cierre_ollama")
        else:
            st.markdown("**¿Cerrar todo?** Se cierra la app, su ventana negra y, si marcas, Ollama.")
            apagar = True
            olla = st.checkbox("Cerrar también Ollama", value=True, key="cierre_ollama")
        c1, c2 = st.columns(2)
        si = c1.button("Sí, cerrar", type="primary", key="btn_cerrar_si")
        if c2.button("Cancelar", key="btn_cerrar_no"):
            st.session_state._confirmar_cierre = False
            st.rerun()
    if si:
        ad = st.session_state.get("adapt")
        if ad and ad.get("stage") == "analizado":
            try:
                _guardar_borrador(ad)  # lo que estabas adaptando queda guardado para "Continuar donde quedé"
            except Exception:
                pass
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        if apagar:
            _cerrar_procesos(olla)
            st.session_state._cerrada = True
        st.rerun()


# ---------------- main ----------------
def main():
    if st.session_state.get("_cerrada"):
        st.markdown("## ⏻ CV Match se cerró")
        st.write("Tu trabajo quedó guardado. Ya puedes cerrar esta pestaña del navegador.")
        st.caption("Para volver a usarla, abre el acceso directo de CV Match o ejecutar_gui.bat.")
        st.stop()
    if not _puerta():
        return
    if multiusuario() and not st.session_state.get("_usuario"):
        _login()
        return
    cfg, facts, cv, cv_error, llm = contexto()
    if not st.session_state.get("_respaldo"):
        try:
            from cvmatch.backup import respaldo_diario
            respaldo_diario()
        except Exception:
            pass
        st.session_state._respaldo = True
    if "nav" not in st.session_state:
        st.session_state.nav = PAGINAS[0]
    if "cola" not in st.session_state:
        st.session_state.cola = _leer_json(COLA_PATH, [])
    with st.sidebar:
        st.markdown("## 📄 CV Match")
        st.caption("Costa Rica + remoto · sin inventar datos")
        if multiusuario():
            st.caption(f"👤 **{st.session_state.get('_usuario', '')}**")
        st.radio("Módulo", PAGINAS[:6] + PAGINAS[7:] + [PAGINAS[6]], key="nav", label_visibility="collapsed")
        st.divider()
        st.caption(f"CV base: **{cfg['_cv_base_path'].name}**")
        st.caption(f"Salida: `{cfg['_salida_path']}`")
        st.caption("API key: " + ("✅" if llm else "❌ falta"))
        try:
            from cvmatch import gasto
            tope = float(cfg.get("presupuesto_mensual_usd") or 0)
            st.caption(f"Gasto del mes: **USD {gasto.total_mes():.2f}**" + (f" de {tope:.2f}" if tope else ""))
        except Exception:
            pass
        if st.session_state.get("cola"):
            st.caption(f"Ofertas en cola: **{len(st.session_state.cola)}**")
        if st.button("📁 Abrir carpeta de salida", key="side_open"):
            abrir(cfg["_salida_path"])
        st.divider()
        _boton_cerrar()
    if cv_error and st.session_state.nav != "⚙️ Configuración":
        st.error(f"Problema con el CV base: {cv_error}. Corrígelo en ⚙️ Configuración.")
        return
    {
        PAGINAS[0]: pagina_panel, PAGINAS[1]: pagina_buscar, PAGINAS[2]: pagina_adaptar,
        PAGINAS[3]: pagina_historial, PAGINAS[4]: pagina_skills, PAGINAS[5]: pagina_respuestas,
        PAGINAS[6]: pagina_config, PAGINAS[7]: pagina_formularios, PAGINAS[8]: pagina_simulador,
    }[st.session_state.nav](cfg, facts, cv, llm)


main()

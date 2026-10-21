"""Reporte HTML por oferta y reporte de Top 5 habilidades."""
from datetime import date
from html import escape

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1d2430;--muted:#5b6575;--accent:#1f4e79;--ok:#1e7a46;--warn:#b25e00;--bad:#b3261e;--line:#e3e6eb}
@media (prefers-color-scheme:dark){:root{--bg:#14171c;--card:#1d2128;--ink:#e8ebf0;--muted:#9aa4b2;--accent:#7fb3e6;--ok:#5cc58a;--warn:#f0a34a;--bad:#f2867e;--line:#2c323b}}
body{font-family:Segoe UI,Calibri,Arial,sans-serif;background:var(--bg);color:var(--ink);margin:0;padding:24px 16px;line-height:1.5}
main{max-width:980px;margin:auto}
h1{color:var(--accent);margin:0 0 4px;font-size:1.6rem}h2{color:var(--accent);border-bottom:2px solid var(--line);padding-bottom:4px;margin-top:28px;font-size:1.2rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:12px 0}
.muted{color:var(--muted)}.scores{display:flex;gap:12px;flex-wrap:wrap}
.score{flex:1;min-width:150px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;text-align:center}
.score b{display:block;font-size:2rem;color:var(--accent)}
.tag{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:2px 10px;margin:3px;font-size:.9rem}
.flag{border-left:4px solid var(--bad)}.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}
table{border-collapse:collapse;width:100%;font-size:.92rem}td,th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
.old{color:var(--muted);text-decoration:line-through}a{color:var(--accent)}
"""

ESTADO_CLASE = {"cumple": "ok", "cumple_por_hecho": "ok", "parcial": "warn",
                "no_tiene_confirmado": "bad", "no_aparece": "bad"}


def _li(items):
    return "<ul>" + "".join(f"<li>{escape(str(i))}</li>" for i in items if i) + "</ul>"


def _trainings_html(trs):
    rows = []
    for t in trs:
        g = "Gratis" if t.get("gratis") else "Pago / suscripción"
        rows.append(f"<li><a href='{escape(t['url'])}' target='_blank'>{escape(t['nombre'])}</a> "
                    f"<span class='muted'>— {escape(t['plataforma'])} · {g}</span></li>")
    return "<ul>" + "".join(rows) + "</ul>"


def job_report(path, job, analysis, rewrite, scan, verify, trainings_by_kw, cv_paths, info_estilo=None, extras=None):
    a = analysis
    flags = "".join(
        f"<div class='card flag'><b>{escape(f.get('flag', ''))}</b><br>{escape(f.get('por_que', ''))}"
        f"<br><span class='muted'>Cómo se corrigió/corregir: {escape(f.get('como_corregir', ''))}</span></div>"
        for f in a.get("red_flags", []))
    req_rows = "".join(
        f"<tr><td>{escape(r.get('requisito', ''))}</td><td>{escape(r.get('tipo', ''))}</td>"
        f"<td class='{ESTADO_CLASE.get(r.get('estado'), '')}'>{escape(r.get('estado', ''))}</td>"
        f"<td>{escape(r.get('evidencia', ''))}</td></tr>" for r in a.get("requisitos", []))
    skipped = "".join(
        f"<div class='card'><b>{escape(s.get('parte', ''))}</b> — {escape(s.get('por_que', ''))}"
        f"<p class='old'>{escape(s.get('original', ''))}</p><p>{escape(s.get('reescritura', ''))}</p></div>"
        for s in scan.get("partes_que_saltaria", []))
    no_resp = verify.get("afirmaciones_no_respaldadas", [])
    no_resp_html = ("<p class='ok'>No se encontraron afirmaciones sin respaldo.</p>" if not no_resp else
                    "".join(f"<div class='card'><b>{escape(x.get('texto', ''))}</b><br>{escape(x.get('problema', ''))}"
                            f"<br><span class='muted'>Corrección: {escape(x.get('correccion', ''))}</span></div>"
                            for x in no_resp))
    no_incl = rewrite.get("palabras_clave_no_incluidas", [])
    trs = "".join(f"<h3>{escape(kw)}</h3>{_trainings_html(t)}" for kw, t in trainings_by_kw.items())
    ex = extras or {}

    def desg(d):
        if not d:
            return ""
        return " · ".join(f"{k} {d.get(k, '?')}/{m}" for k, m in
                          (("obligatorios", 50), ("deseables", 20), ("seniority", 15), ("industria", 15)))
    elim = ex.get("eliminatorios") or []
    elim_html = ("<p class='muted'>No se detectaron requisitos eliminatorios.</p>" if not elim else
                 "<table><tr><th>Requisito</th><th>¿Cumples?</th><th>Detalle</th></tr>" + "".join(
                     f"<tr><td>{escape(e.get('requisito', ''))}</td>"
                     f"<td class='{ {'si': 'ok', 'no': 'bad'}.get(e.get('cumple'), 'warn') }'>{escape(e.get('cumple', ''))}</td>"
                     f"<td>{escape(e.get('detalle', ''))}</td></tr>" for e in elim) + "</table>")
    emp = ex.get("empresa") or {}
    emp_html = ("" if not emp else
                f"<p><b>Industria:</b> {escape(str(emp.get('industria', '')))} · <b>Regulada:</b> {escape(str(emp.get('regulada', '')))}"
                f" · <b>Tamaño:</b> {escape(str(emp.get('tamano', '')))}<br><b>En Costa Rica:</b> {escape(str(emp.get('presencia_costa_rica', '')))}"
                f"<br><b>Cultura:</b> {escape(str(emp.get('cultura_valores', '')))}</p>"
                f"<p><b>Qué se priorizó en tu CV:</b></p>{_li(emp.get('que_priorizar_en_cv', []))}")
    ent = ex.get("entrevista") or {}
    ent_html = "".join(
        f"<div class='card'><b>{escape(q.get('pregunta', ''))}</b> <span class='muted'>({escape(q.get('sobre', ''))})</span>"
        f"{'' if q.get('defendible', True) else ' <span class=bad>⚠ difícil de defender</span>'}"
        f"<p><b>S:</b> {escape(q.get('situacion', ''))}<br><b>T:</b> {escape(q.get('tarea', ''))}<br>"
        f"<b>A:</b> {escape(q.get('accion', ''))}<br><b>R:</b> {escape(q.get('resultado', ''))}</p>"
        f"{('<p class=muted>Riesgo: ' + escape(q.get('riesgo', '')) + '</p>') if q.get('riesgo') else ''}</div>"
        for q in ent.get("preguntas", []))
    if ent.get("bullets_debiles"):
        ent_html += "<p><b>Bullets difíciles de defender:</b></p>" + _li(
            f"{b.get('bullet')}: {b.get('por_que')}" for b in ent["bullets_debiles"])
    li = ex.get("linkedin") or []
    li_html = ("" if not li else "<h2>Coherencia con LinkedIn</h2><table><tr><th>Campo</th><th>CV</th><th>LinkedIn</th>"
               "<th>Sugerencia</th></tr>" + "".join(
                   f"<tr><td>{escape(d.get('campo', ''))}</td><td>{escape(d.get('cv', ''))}</td>"
                   f"<td>{escape(d.get('linkedin', ''))}</td><td>{escape(d.get('sugerencia', ''))}</td></tr>" for d in li)
               + "</table>")
    ie = info_estilo or {}
    est_html = (f"<p>Marcas de texto IA detectadas: <b>{ie.get('detectadas', 0)}</b> · corregidas: <b>{ie.get('corregidas', 0)}</b>"
                f" · pendientes: <b>{len(ie.get('restantes', []))}</b></p>")
    est_html += "".join(f"<div class='card'><p class='old'>{escape(c.get('original', ''))}</p><p>{escape(c.get('nuevo', ''))}</p></div>"
                        for c in ie.get("cambios", []))
    est_html += "".join(f"<div class='card flag'>{escape(r['texto'])}<br><span class='muted'>{escape(', '.join(r['marcas']))}</span></div>"
                        for r in ie.get("restantes", []))
    url = job.get("url", "")
    html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Reporte — {escape(a.get('puesto', ''))}</title>
<style>{CSS}</style></head><body><main>
<h1>{escape(a.get('puesto') or job.get('puesto', ''))}</h1>
<p class="muted">{escape(a.get('empresa') or job.get('empresa', ''))} · {escape(a.get('ubicacion', ''))} · {escape(a.get('modalidad', ''))} · {date.today().isoformat()}<br>
<a href="{escape(url)}" target="_blank">{escape(url)}</a></p>
<div class="scores">
<div class="score">Match CV general<b>{a.get('puntuacion_match', '?')}</b>/100</div>
<div class="score">Match CV adaptado<b>{verify.get('puntuacion_match_final', '?')}</b>/100</div>
<div class="score">ATS (parseo)<b>{scan.get('ats', {}).get('puntuacion', '?')}</b>/100</div>
</div>
<div class="card"><b>CV a usar:</b> {escape(cv_paths.get('docx', ''))}<br>{escape(cv_paths.get('pdf') or '')}</div>
<p class="muted">Rúbrica inicial: {escape(desg(ex.get('desglose_inicial')))}<br>Rúbrica final: {escape(desg(ex.get('desglose_final')))}
{(' · Páginas: ' + str(ex.get('paginas'))) if ex.get('paginas') else ''}</p>
<div class="card"><b>Elegibilidad desde Costa Rica:</b> {escape(str(a.get('elegible_desde_costa_rica')))} — {escape(a.get('motivo_elegibilidad', ''))}</div>

<h2>Requisitos eliminatorios</h2>{elim_html}
{('<h2>La empresa</h2>' + emp_html) if emp_html else ''}

<h2>1. Vista del reclutador</h2>
<p>{escape(a.get('justificacion_puntuacion', ''))}</p>
<h3>5 palabras clave que faltaban</h3>{''.join(f"<span class='tag'>{escape(k)}</span>" for k in a.get('palabras_clave_faltantes', []))}
<h3>3 red flags (10 segundos)</h3>{flags}
<h3>Requisitos de la oferta</h3><table><tr><th>Requisito</th><th>Tipo</th><th>Estado</th><th>Evidencia</th></tr>{req_rows}</table>

<h2>2. Reescritura (fórmula XYZ)</h2>
<p><b>Palabras clave incluidas:</b> {escape(', '.join(rewrite.get('palabras_clave_incluidas', [])))}</p>
<p><b>No incluidas por falta de evidencia (no se inventaron):</b></p>{_li(f"{x.get('palabra')}: {x.get('motivo')}" for x in no_incl)}
<p><b>Red flags eliminadas:</b></p>{_li(f"{x.get('flag')}: {x.get('como')}" for x in rewrite.get('red_flags_eliminadas', []))}

<h2>3. Filtro ATS + lector de 100 CVs</h2>
<div class="card"><b>Lo que ve en 6 segundos:</b> {escape(scan.get('lo_que_veo_en_6_segundos', ''))}</div>
<p><b>Palabras ausentes para el ATS:</b> {escape(', '.join(scan.get('ats', {}).get('palabras_ausentes', [])))}</p>
<p><b>Problemas de formato:</b></p>{_li(scan.get('ats', {}).get('problemas_formato', []))}
<h3>Partes que se saltaría y su reescritura</h3>{skipped}

<h2>4. Auditoría de veracidad</h2>{no_resp_html}
<p class="muted">{escape(verify.get('comentario_puntuacion', ''))}</p>

<h2>4b. Naturalidad (que no parezca escrito por IA)</h2>{est_html}

{li_html}

<h2>Preparación de entrevista</h2>{ent_html or "<p class='muted'>No generada.</p>"}

<h2>5. Cómo subir más el match</h2>
{_li(a.get('sugerencias_para_subir_match', []) + verify.get('acciones_para_subir_mas', []))}

<h2>6. Trainings para cerrar las brechas</h2>{trs}
</main></body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def skills_report(path, top5, total_ofertas):
    cards = []
    for i, s in enumerate(top5, 1):
        cursos = "".join(
            f"<li><a href='{escape(c.get('url', ''))}' target='_blank'>{escape(c.get('nombre', ''))}</a> "
            f"<span class='muted'>— {escape(c.get('plataforma', ''))} · {'Gratis' if c.get('gratis') else 'Pago / suscripción'}</span></li>"
            for c in s.get("cursos", []))
        cert = f"<p><b>Certificación sugerida:</b> {escape(s['certificacion_sugerida'])}</p>" if s.get("certificacion_sugerida") else ""
        cards.append(f"<div class='card'><h3>{i}. {escape(s.get('habilidad', ''))}</h3>"
                     f"<p class='muted'>Aparece en {s.get('aparece_en_ofertas', '?')} de {total_ofertas} ofertas analizadas</p>"
                     f"<p>{escape(s.get('por_que', ''))}</p>{cert}<ul>{cursos}</ul></div>")
    html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Top 5 habilidades</title><style>{CSS}</style></head>
<body><main><h1>Top 5 habilidades que debes aprender</h1>
<p class="muted">Basado en {total_ofertas} ofertas analizadas · actualizado {date.today().isoformat()}</p>
{''.join(cards)}</main></body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path

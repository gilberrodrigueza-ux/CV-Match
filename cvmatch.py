"""CV Match
Busca ofertas en Costa Rica / remoto, adapta el CV por oferta sin inventar datos y lleva el historial."""
import json
import os
import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from cvmatch import history
from cvmatch.config import get_api_key, load_config, save_api_key
from cvmatch.cv_reader import read_cv
from cvmatch.facts import Facts

console = Console()


def open_file(path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # noqa
    except Exception:
        pass


class UI:
    def info(self, m): console.print(f"[cyan]{m}[/]")
    def warn(self, m): console.print(f"[yellow]⚠ {m}[/]")
    def ok(self, m): console.print(f"[green]✔ {m}[/]")
    def step(self, m): console.print(f"\n[bold magenta]▶ {m}[/]")
    def title(self, m): console.print(Panel(m, style="bold blue"))

    def ask(self, q, choices=None):
        while True:
            a = Prompt.ask(q, default="", show_default=False).strip()
            if choices is None or a.lower() in choices:
                return a.lower() if choices else a
            console.print(f"[red]Opciones válidas: {', '.join(c or 'Enter' for c in choices)}[/]")

    def confirm(self, q): return Confirm.ask(q, default=True)

    def paste(self, q):
        console.print(f"[bold]{q}[/] (al terminar escribe [bold]FIN[/] en una línea sola y Enter):")
        lines = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip().upper() == "FIN":
                break
            lines.append(line)
        return "\n".join(lines).strip()

    def show_analysis(self, a):
        console.print(Panel(
            f"[bold]{a.get('puesto', '')}[/] — {a.get('empresa', '')}  ({a.get('ubicacion', '')}, {a.get('modalidad', '')})\n"
            f"Match de tu CV general: [bold]{a.get('puntuacion_match', '?')}/100[/]\n{a.get('justificacion_puntuacion', '')}\n\n"
            f"[bold]5 palabras clave que faltan:[/] {', '.join(a.get('palabras_clave_faltantes', []))}\n\n"
            "[bold]3 red flags (10 segundos):[/]\n" +
            "\n".join(f" • {f.get('flag')}: {f.get('por_que')}" for f in a.get("red_flags", [])) +
            f"\n\nElegible desde CR: {a.get('elegible_desde_costa_rica')} — {a.get('motivo_elegibilidad', '')}",
            title="Vista del reclutador", border_style="blue"))

    def show_scan(self, sc):
        partes = sc.get("partes_que_saltaria", [])
        console.print(Panel(
            f"ATS: [bold]{sc.get('ats', {}).get('puntuacion', '?')}/100[/]\n"
            f"En 6 segundos ve: {sc.get('lo_que_veo_en_6_segundos', '')}\n\n[bold]Se saltaría:[/]\n" +
            "\n".join(f" • {p.get('parte')}: {p.get('por_que')}" for p in partes) +
            "\n(Esas partes ya fueron reescritas para parar el scroll.)",
            title="Filtro ATS + lector de 100 CVs", border_style="magenta"))

    def show_result(self, rid, a, vf, docx, pdf, rep, rw, tr):
        nores = vf.get("afirmaciones_no_respaldadas", [])
        txt = (f"Match: [bold]{a.get('puntuacion_match')}[/] → [bold green]{vf.get('puntuacion_match_final')}[/]/100\n"
               f"CV a usar: [bold]{docx}[/]\n" + (f"PDF: {pdf}\n" if pdf else "") +
               f"Reporte completo: {rep}\nRegistrado en el historial con ID {rid} (estado: Por aplicar)\n")
        if nores:
            txt += f"\nLa auditoría corrigió {len(nores)} afirmación(es) sin respaldo."
        noinc = rw.get("palabras_clave_no_incluidas", [])
        if noinc:
            txt += "\n\n[bold]Palabras clave NO incluidas por falta de evidencia:[/] " + ", ".join(
                x.get("palabra", "") for x in noinc)
        txt += "\n\n[bold]Cómo subir más el match:[/]\n" + "\n".join(
            f" • {s}" for s in (vf.get("acciones_para_subir_mas") or a.get("sugerencias_para_subir_match", []))[:6])
        console.print(Panel(txt, title="CV adaptado listo", border_style="green"))
        if Confirm.ask("¿Abrir el reporte (incluye los links de trainings)?", default=True):
            open_file(rep)


def build_llm(cfg):
    from cvmatch.llm import LLM
    key = get_api_key()
    if not key:
        console.print(Panel("Necesito tu API key de Anthropic (console.anthropic.com → API Keys).\n"
                            "Se guarda solo en tu PC, en datos\\api_key.txt.", title="Configuración inicial"))
        key = Prompt.ask("Pega tu API key (clic derecho para pegar) y Enter").strip()
        if not key:
            sys.exit("Sin API key no puedo analizar.")
        save_api_key(key)
    llm = LLM(key, cfg["modelo_analisis"], cfg["modelo_redaccion"])
    llm.cfg = cfg
    return llm


def menu_search(pipe):
    extra = Prompt.ask("Palabras clave extra para esta búsqueda (separadas por coma, Enter = usar tu perfil)",
                       default="", show_default=False)
    kws = [k.strip() for k in extra.split(",") if k.strip()]
    res = pipe.search(kws)
    if not res:
        console.print("[yellow]No encontré ofertas nuevas que superen el puntaje mínimo.[/]")
        return
    t = Table(title=f"Ofertas que mejor encajan con tu CV ({len(res)})", show_lines=False)
    for c in ("#", "Match", "Puesto", "Empresa", "Ubicación", "Fuente", "Motivo"):
        t.add_column(c, overflow="fold")
    for i, j in enumerate(res, 1):
        t.add_row(str(i), str(j.get("match_estimado", "?")), j["puesto"], j["empresa"], j["ubicacion"],
                  j["fuente"], j.get("motivo", ""))
    console.print(t)
    sel = Prompt.ask("Números de las ofertas para adaptar tu CV (ej. 1,3,5; Enter = ninguna)", default="",
                     show_default=False)
    for s in [x.strip() for x in sel.split(",") if x.strip().isdigit()]:
        k = int(s) - 1
        if 0 <= k < len(res):
            console.rule(f"[bold]{res[k]['puesto']} — {res[k]['empresa']}")
            console.print(f"[dim]{res[k]['url']}[/]")
            try:
                pipe.process(res[k])
            except Exception as e:
                console.print(f"[red]Error procesando la oferta: {e}[/]")


def menu_manual(pipe):
    url = Prompt.ask("Link de la oferta (Enter si no tienes link)", default="", show_default=False).strip()
    job = {"url": url, "fuente": "Manual", "descripcion": "", "empresa": "", "puesto": ""}
    if not url:
        job["descripcion"] = UI().paste("Pega la descripción del puesto (JD)")
    pipe.process(job)


def menu_history(pipe):
    rows = history.all_rows()
    if not rows:
        console.print("[yellow]Historial vacío.[/]")
        return
    t = Table(title="Historial de solicitudes")
    for c in ("ID", "Fecha", "Empresa", "Puesto", "Match", "Estado", "CV a usar"):
        t.add_column(c, overflow="fold")
    for r in rows:
        t.add_row(str(r["id"]), r["fecha"], r["empresa"], r["puesto"],
                  f"{r['match_inicial']}→{r['match_final']}", r["estado"], os.path.basename(r["cv_docx"] or ""))
    console.print(t)
    rid = Prompt.ask("ID para ver/editar (Enter = volver)", default="", show_default=False)
    if not rid.isdigit():
        return
    r = next((x for x in rows if x["id"] == int(rid)), None)
    if not r:
        return
    console.print(Panel(f"Link: {r['url']}\nCV: {r['cv_docx']}\nPDF: {r['cv_pdf']}\nReporte: {r['reporte']}\n"
                        f"Estado: {r['estado']}\nNotas: {r['notas']}", title=f"{r['empresa']} — {r['puesto']}"))
    acc = Prompt.ask("[e]stado · [n]otas · [a]brir CV · [r]eporte · Enter = volver", default="", show_default=False).lower()
    if acc == "e":
        for i, e in enumerate(history.ESTADOS, 1):
            console.print(f" {i}. {e}")
        k = Prompt.ask("Nuevo estado", choices=[str(i) for i in range(1, len(history.ESTADOS) + 1)])
        history.update(r["id"], estado=history.ESTADOS[int(k) - 1])
    elif acc == "n":
        history.update(r["id"], notas=Prompt.ask("Notas"))
    elif acc == "a":
        open_file(r["cv_docx"])
    elif acc == "r":
        open_file(r["reporte"])
    pipe.export_history()


def menu_skills(pipe):
    out = pipe.top_skills()
    if not out:
        return
    top5, path = out
    t = Table(title="Top 5 habilidades que debes aprender (según tus JDs)")
    for c in ("#", "Habilidad", "Ofertas", "Por qué", "Primer training"):
        t.add_column(c, overflow="fold")
    for i, s in enumerate(top5, 1):
        first = s.get("cursos", [{}])[0] if s.get("cursos") else {}
        t.add_row(str(i), s.get("habilidad", ""), str(s.get("aparece_en_ofertas", "")), s.get("por_que", ""),
                  first.get("url", ""))
    console.print(t)
    console.print(f"Reporte con todos los links: [bold]{path}[/]")
    if Confirm.ask("¿Abrirlo?", default=True):
        open_file(path)


def menu_facts(facts):
    while True:
        t = Table(title="Tus respuestas confirmadas (lo único que se suma al CV)")
        for c in ("#", "Habilidad", "Tiene", "Detalle"):
            t.add_column(c, overflow="fold")
        for i, f in enumerate(facts.items, 1):
            t.add_row(str(i), f["habilidad"], f["tiene"], f.get("detalle", ""))
        console.print(t)
        acc = Prompt.ask("[a]gregar · [b]orrar · Enter = volver", default="", show_default=False).lower()
        if acc == "a":
            h = Prompt.ask("Habilidad / requisito")
            tiene = Prompt.ask("¿La tienes?", choices=["si", "parcial", "no"])
            det = Prompt.ask("Detalle (dónde, cuándo, qué, cifras reales)", default="") if tiene != "no" else ""
            facts.add(h, tiene, det, "Agregado manualmente")
        elif acc == "b":
            k = Prompt.ask("Número a borrar")
            if k.isdigit():
                facts.remove(int(k) - 1)
        else:
            return


def main():
    from cvmatch.config import multiusuario, set_usuario
    if multiusuario():
        from getpass import getpass
        from cvmatch import usuarios
        u = input("Usuario: ").strip().lower()
        if not usuarios.verificar(u, getpass("Contraseña: ")):
            console.print("[red]Usuario o contraseña incorrectos.[/]")
            return
        set_usuario(u)
    cfg = load_config()
    console.print(Panel.fit("[bold]CV Match[/] — Costa Rica + remoto · adaptación sin inventar datos",
                            border_style="blue"))
    try:
        cv = read_cv(cfg["_cv_base_path"])
    except Exception as e:
        console.print(f"[red]{e}[/]\nRevisa \"cv_base\" en config.json.")
        input("Enter para salir")
        return
    console.print(f"CV base: {cfg['_cv_base_path'].name} · Salida: {cfg['_salida_path']}")
    facts = Facts()
    llm = build_llm(cfg)
    from cvmatch.pipeline import Pipeline
    pipe = Pipeline(cfg, llm, facts, cv, UI())
    while True:
        console.print("\n[bold]Menú[/]\n 1. Buscar ofertas (Costa Rica + remoto) y adaptar CV\n"
                      " 2. Adaptar CV a una oferta específica (link o texto)\n"
                      " 3. Historial de solicitudes (estado, notas, abrir CV)\n"
                      " 4. Top 5 habilidades a aprender + trainings\n"
                      " 5. Mis respuestas confirmadas (habilidades)\n"
                      " 6. Exportar historial a Excel\n 0. Salir")
        op = Prompt.ask("Opción", choices=["1", "2", "3", "4", "5", "6", "0"], default="1")
        try:
            if op == "1":
                menu_search(pipe)
            elif op == "2":
                menu_manual(pipe)
            elif op == "3":
                menu_history(pipe)
            elif op == "4":
                menu_skills(pipe)
            elif op == "5":
                menu_facts(facts)
            elif op == "6":
                p = pipe.export_history()
                console.print(f"[green]Excel: {p}[/]")
                open_file(p)
            else:
                break
        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelado, volviendo al menú.[/]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/]")


if __name__ == "__main__":
    main()

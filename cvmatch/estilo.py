"""Estilo humano: reglas de redacción y detector local de marcas típicas de texto generado por IA."""
import re

# Palabras y frases que delatan texto de IA en CVs (inglés y español)
MARCAS_IA = [
    # inglés
    "spearheaded", "spearheading", "leveraged", "leveraging", "leverage", "seamless", "seamlessly", "robust",
    "orchestrated", "orchestrating", "dynamic", "passionate", "proven track record", "results-driven",
    "results-oriented", "cutting-edge", "state-of-the-art", "synergy", "synergies", "holistic", "delve",
    "pivotal", "paramount", "meticulous", "meticulously", "transformative", "game-changer", "game-changing",
    "innovative solutions", "fostered", "fostering", "empowered", "empowering", "streamlined",
    "best-in-class", "world-class", "thought leader", "go-getter", "detail-oriented", "self-starter",
    "as measured by", "showcasing", "underscoring", "navigating the", "in today's", "ever-evolving",
    "landscape", "tapestry", "realm", "elevate", "elevated", "unlock", "unlocked", "harness", "harnessed",
    "drive innovation", "driving innovation", "strategic visionary", "adept at", "instrumental in",
    "a testament to", "deep dive", "end-to-end excellence",
    # español
    "medido por", "apasionado", "orientado a resultados", "sinergia", "sinergias", "de vanguardia",
    "holístico", "holística", "impulsé la innovación", "aprovechando", "transformador", "sin fisuras",
    "trayectoria comprobada", "panorama", "potenciar", "potencié", "fomenté", "en el dinámico",
]

ESTILO_HUMANO = """
ESTILO HUMANO (obligatorio): el CV debe leerse como escrito por un ingeniero senior, no por una IA.
- Usa la estructura XYZ (resultado + métrica + cómo) pero SIN la fórmula literal: nunca escribas "as measured by" /
  "medido por". Varía el orden: a veces la cifra primero, a veces la acción, a veces el contexto (cliente, países).
- Verbos simples y concretos: led, built, moved, migrated, cut, ran, designed, fixed, set up, rebuilt, owned,
  automated, consolidated, trained (o en español: lideré, migré, diseñé, reduje, armé, automaticé, consolidé).
- PROHIBIDO usar: spearheaded, leveraged, seamless, robust, orchestrated, dynamic, passionate, proven track record,
  results-driven, cutting-edge, synergy, holistic, pivotal, meticulous, transformative, fostered, empowered,
  streamlined, world-class, landscape, realm, elevate, unlock, harness, instrumental in, adept at, showcasing
  (ni sus equivalentes en español: apasionado, orientado a resultados, sinergia, de vanguardia, holístico, potenciar).
- Nada de guiones largos (—) dentro de bullets ni del perfil; usa comas, punto y coma o dos frases.
- Varía la longitud de los bullets (unos de una línea, otros de dos). No empieces dos bullets seguidos con el mismo
  verbo ni con la misma estructura. Evita listas de tres adjetivos.
- Lo más humano es lo específico: nombres reales de herramientas, clientes permitidos, países, versiones, volúmenes.
  Prefiere un detalle técnico concreto a una frase de impacto genérica.
- Perfil: 2-3 frases directas con hechos (años, tipo de clientes, 2-3 logros con cifra). Sin adjetivos de
  autopromoción ("highly skilled", "passionate", "dedicated").
- Números con dígitos (400,000+; 6 countries; 2 months). Sin pronombres "I/my".
"""


def _textos(cv):
    """Devuelve [(ruta, texto)] de las partes redactadas del CV."""
    out = []
    if cv.get("titular"):
        out.append(("titular", cv["titular"]))
    if cv.get("perfil"):
        out.append(("perfil", cv["perfil"]))
    for i, c in enumerate(cv.get("competencias", []) or []):
        out.append((f"competencias[{i}]", c))
    for i, e in enumerate(cv.get("experiencia", []) or []):
        for j, b in enumerate(e.get("bullets", []) or []):
            out.append((f"experiencia[{i}].bullets[{j}]", b))
    return out


def detectar(cv):
    """Lista de problemas de estilo: [{'ruta','texto','marcas'}]."""
    problemas = []
    for ruta, t in _textos(cv):
        low = t.lower()
        marcas = [m for m in MARCAS_IA if re.search(r"(?<![a-záéíóúñ])" + re.escape(m) + r"(?![a-záéíóúñ])", low)]
        if "—" in t and ruta != "titular":
            marcas.append("guion largo (—)")
        if marcas:
            problemas.append({"ruta": ruta, "texto": t, "marcas": marcas})
    # mismo verbo inicial repetido en un mismo rol
    for i, e in enumerate(cv.get("experiencia", []) or []):
        primeros = [((b.split() or [""])[0]).lower().strip(",.") for b in e.get("bullets", []) or []]
        for j in range(1, len(primeros)):
            if primeros[j] and primeros[j] == primeros[j - 1]:
                t = e["bullets"][j]
                problemas.append({"ruta": f"experiencia[{i}].bullets[{j}]", "texto": t,
                                  "marcas": [f"empieza igual que el bullet anterior ('{primeros[j]}')"]})
    return problemas


def aplicar(cv, cambios):
    """Aplica reemplazos [{'original','nuevo'}] por coincidencia exacta de texto."""
    mapa = {c.get("original", ""): c.get("nuevo", "") for c in cambios if c.get("original") and c.get("nuevo")}
    if not mapa:
        return cv
    if cv.get("titular") in mapa:
        cv["titular"] = mapa[cv["titular"]]
    if cv.get("perfil") in mapa:
        cv["perfil"] = mapa[cv["perfil"]]
    cv["competencias"] = [mapa.get(c, c) for c in cv.get("competencias", []) or []]
    for e in cv.get("experiencia", []) or []:
        e["bullets"] = [mapa.get(b, b) for b in e.get("bullets", []) or []]
    return cv

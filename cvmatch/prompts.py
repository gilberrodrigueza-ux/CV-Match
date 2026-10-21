"""Prompts del sistema. Regla central: NUNCA inventar datos."""
from .estilo import ESTILO_HUMANO

REGLA_NO_INVENTAR = """
REGLA ABSOLUTA — NO INVENTAR:
- Solo puedes usar información que aparezca en (a) el CV BASE o (b) los HECHOS CONFIRMADOS por el candidato.
- Prohibido inventar empresas, puestos, fechas, clientes, certificaciones, herramientas, cifras, porcentajes,
  tamaños de equipo, presupuestos o logros. Si una cifra no existe en las fuentes, NO la crees.
- Si un hecho confirmado dice "no" o "solo labs/training", respétalo exactamente (no lo conviertas en experiencia).
- Un "training" nunca se presenta como certificación. Una certificación no obtenida no aparece como obtenida.
- Empresas, puestos oficiales y fechas se copian tal cual del CV base.
- Puedes reformular, reordenar, priorizar, usar sinónimos del mismo concepto y adoptar la terminología de la
  oferta SOLO cuando describe lo mismo que ya está respaldado.
"""

SYSTEM_RECLUTADOR = """Eres un técnico de selección / reclutador senior de la empresa que publica la oferta.
Evalúas CVs con criterio exigente y realista, como lo haría un responsable de selección de esa empresa.
Respondes SIEMPRE en JSON válido, con textos explicativos en español.""" + REGLA_NO_INVENTAR

PROMPT_ANALISIS = """Analiza mi CV contra esta descripción de puesto.

=== OFERTA (JD) ===
{jd}

=== CV BASE ===
{cv}

=== HECHOS CONFIRMADOS POR EL CANDIDATO (cuentan como evidencia, pero NO están escritos en el CV) ===
{hechos}

=== DATOS DEL CANDIDATO ===
Vive en Costa Rica. Solo le sirven puestos en Costa Rica o 100% remotos contratables desde Costa Rica.

Tareas:
1. Puntuación de match sobre 100 del CV TAL COMO ESTÁ ESCRITO (lo que vería el reclutador hoy), con esta rúbrica.
   Para esta puntuación inicial, lo que solo está en HECHOS CONFIRMADOS cuenta como 0 (no está escrito en el CV).
RÚBRICA FIJA (súmala; no estimes a ojo):
- obligatorios (0-50): proporción de requisitos obligatorios cumplidos × 50 (cumple = 1, parcial = 0.5, resto = 0)
- deseables (0-20): proporción de requisitos deseables cumplidos × 20 (misma regla)
- seniority (0-15): ajuste de años, nivel y alcance del rol. Estar sobrecalificado NO resta.
- industria (0-15): experiencia en la misma industria / tipo de cliente / entorno (regulado, consultoría, producto).
puntuacion = suma redondeada.
2. Las 5 palabras clave más importantes de la oferta que FALTAN en el CV (términos exactos que un ATS buscaría).
3. Las 3 red flags que un responsable de selección detectaría en menos de 10 segundos.
4. Lista de requisitos de la oferta y su estado considerando CV + hechos confirmados:
   - "cumple": está en el CV
   - "cumple_por_hecho": no está en el CV, pero el candidato lo confirmó (hecho con tiene=si)
   - "parcial": evidencia parcial (en CV o hechos)
   - "no_tiene_confirmado": el candidato ya confirmó que NO lo tiene
   - "no_aparece": no hay evidencia en CV ni en hechos (hay que PREGUNTARLE)
   Para "no_aparece" y "parcial" sin hecho confirmado, redacta una pregunta corta en español para el candidato.
5. Sugerencias concretas para subir el match (qué destacar, qué reordenar, qué certificación/curso/proyecto haría
   la mayor diferencia).
6. REQUISITOS ELIMINATORIOS: los que un ATS o reclutador usaría para descartar automáticamente (años mínimos,
   título universitario, certificación obligatoria, nivel de idioma, residencia/permiso de trabajo, clearance,
   disponibilidad on-call/turnos/fines de semana, % de viajes, presencialidad). Para cada uno: si el candidato cumple
   ("si"), no cumple ("no") o no se sabe ("desconocido"), usando CV + hechos.
7. ¿Es elegible desde Costa Rica? (true/false/null si no se sabe) y por qué.
REGLA DE ELEGIBILIDAD (estricta): el candidato SOLO acepta (a) puestos ubicados en Costa Rica (presencial, híbrido o
remoto) o (b) puestos 100 % remotos que contraten explícitamente desde Costa Rica / LATAM / cualquier país.
Es NO elegible (false) si: la oficina está en otro país (aunque la región diga LATAM), ofrece o exige relocation,
es presencial/híbrido fuera de Costa Rica, o el remoto está restringido a otro país (ej. "US only", "Mexico only").
Usa null solo si de verdad no se puede saber.

SÉ CONCISO (es obligatorio): máximo 15 requisitos (los más importantes), "evidencia" y "pregunta_para_candidato"
de máximo 20 palabras, máximo 6 sugerencias, máximo 15 habilidades_jd, máximo 8 eliminatorios.

Devuelve SOLO este JSON:
{{
  "empresa": "", "puesto": "", "ubicacion": "", "modalidad": "remoto|hibrido|presencial|desconocido",
  "idioma_jd": "en|es",
  "elegible_desde_costa_rica": true, "motivo_elegibilidad": "",
  "puntuacion_match": 0,
  "desglose_puntuacion": {{"obligatorios": 0, "deseables": 0, "seniority": 0, "industria": 0}},
  "justificacion_puntuacion": "",
  "requisitos_eliminatorios": [{{"requisito": "", "cumple": "si|no|desconocido", "detalle": ""}}],
  "industria_empresa": "",
  "palabras_clave_faltantes": ["", "", "", "", ""],
  "red_flags": [{{"flag": "", "por_que": "", "como_corregir": ""}}],
  "requisitos": [{{"requisito": "", "tipo": "obligatorio|deseable", "estado": "", "evidencia": "",
                   "habilidad_corta": "", "pregunta_para_candidato": ""}}],
  "habilidades_jd": [""],
  "sugerencias_para_subir_match": [""]
}}
"habilidad_corta" = nombre normalizado y breve de la habilidad (ej. "Kubernetes", "AWS networking", "AZ-305")."""

SYSTEM_REDACTOR = """Eres un redactor experto de CVs técnicos para el mercado de tecnología (Costa Rica, LATAM, EE.UU.)
y conoces cómo filtran los ATS. Escribes bullets con la lógica XYZ de Google (qué lograste, cómo se midió, cómo lo
hiciste), pero con redacción natural de ingeniero, nunca con la plantilla literal.
Respondes SIEMPRE en JSON válido.""" + REGLA_NO_INVENTAR + ESTILO_HUMANO

ESQUEMA_CV = """{
  "nombre": "", "titular": "", "contacto": "",
  "perfil": "",
  "competencias": [""],
  "experiencia": [{"empresa": "", "puesto": "", "ubicacion": "", "fechas": "", "bullets": [""]}],
  "habilidades_tecnicas": [{"categoria": "", "items": ""}],
  "certificaciones": [""],
  "formacion": [""],
  "educacion": [""]
}"""

PROMPT_REESCRITURA = """Adapta mi CV a esta oferta.

=== OFERTA (JD) ===
{jd}

=== ANÁLISIS DEL RECLUTADOR ===
Palabras clave faltantes: {keywords}
Red flags: {redflags}
Sugerencias: {sugerencias}

=== CONTEXTO DE LA EMPRESA (solo para decidir qué priorizar; NO es fuente de hechos del candidato) ===
{contexto_empresa}

=== CV BASE (fuente de verdad) ===
{cv}

=== HECHOS CONFIRMADOS POR EL CANDIDATO (fuente de verdad adicional) ===
{hechos}

Instrucciones:
- Idioma del CV final: {idioma}.
- Reescribe la sección de experiencia incluyendo las palabras clave faltantes SOLO si están respaldadas por el CV o
  los hechos confirmados; si una palabra clave no está respaldada, NO la incluyas y repórtala en
  "palabras_clave_no_incluidas".
- Elimina o neutraliza las red flags (sin mentir: reordenar, reenfocar, aclarar, quitar ruido).
- Cada bullet con lógica XYZ (resultado, métrica, cómo) en redacción natural y variada, sin "as measured by".
  Las métricas solo pueden ser las que existen en las fuentes; si no hay cifra, usa un resultado verificable
  cualitativo (ej. "without major service disruption", "ahead of schedule").
- Sigue las reglas de ESTILO HUMANO.{muestra}
- Prioriza lo relevante para la oferta: bullets más relevantes primero; recorta bullets irrelevantes.
- Ajusta titular, perfil, competencias y habilidades técnicas a la terminología de la oferta (sin inventar).
- Mantén nombre y datos de contacto EXACTOS del CV base.{idiomas}
- Prioriza la experiencia que más pesa en la industria de la empresa (ej. banca/entornos regulados, consultoría,
  migraciones a gran escala), siempre con hechos de las fuentes.
- Mantén la seniority completa del candidato (títulos oficiales tal cual), aunque el puesto sea de menor nivel.
- RECENCIA: los roles terminados hace más de 15 años que no aporten a esta oferta se condensan en una sola entrada:
  {{"empresa": "Earlier Experience" (o "Experiencia previa" en español), "puesto": "Empresa — Puesto; Empresa — Puesto",
  "ubicacion": "", "fechas": "año inicio – año fin", "bullets": [1 línea con lo más relevante]}}. Si un rol antiguo SÍ
  aporta (ej. el cliente o la tecnología de la oferta), mantenlo con 1-2 bullets.
- Longitud objetivo: máximo {paginas} páginas (aprox. 5-6 bullets en el rol más reciente, 2-4 en roles antiguos).
- Copia certificaciones, formación y educación tal cual (puedes reordenarlas por relevancia).

Devuelve SOLO este JSON:
{{
  "cv": {esquema},
  "palabras_clave_incluidas": [""],
  "palabras_clave_no_incluidas": [{{"palabra": "", "motivo": ""}}],
  "red_flags_eliminadas": [{{"flag": "", "como": ""}}]
}}"""

SYSTEM_ESCANER = """Actúas a la vez como (1) un filtro ATS (Workday, Greenhouse, Lever, Taleo, iCIMS) y (2) un
responsable de selección que lee 100 CVs de golpe y dedica 6-10 segundos a cada uno.
Respondes SIEMPRE en JSON válido, con explicaciones en español.""" + REGLA_NO_INVENTAR + ESTILO_HUMANO

PROMPT_ESCANEO = """Escanea este CV nuevo para la oferta indicada.

=== OFERTA (JD) ===
{jd}

=== CV NUEVO (JSON) ===
{cv_json}

=== FUENTES DE VERDAD (para no inventar al reescribir) ===
CV BASE:
{cv}
HECHOS CONFIRMADOS:
{hechos}

Tareas:
1. Como ATS: puntuación de parseo/coincidencia (0-100), palabras clave presentes y ausentes, problemas de formato.
2. Como responsable de selección con 100 CVs: qué ves en los primeros 6 segundos y QUÉ PARTES TE SALTARÍAS
   (y por qué).
3. Reescribe esas partes para que "paren el scroll" (resultado concreto, cifra real, términos de la oferta),
   respetando la regla de no inventar y el ESTILO HUMANO (sin frases de marketing ni clichés de IA).
4. Devuelve el CV completo con esas reescrituras aplicadas, en el mismo idioma.

Devuelve SOLO este JSON:
{{
  "ats": {{"puntuacion": 0, "palabras_presentes": [""], "palabras_ausentes": [""], "problemas_formato": [""]}},
  "lo_que_veo_en_6_segundos": "",
  "partes_que_saltaria": [{{"parte": "", "por_que": "", "original": "", "reescritura": ""}}],
  "cv": {esquema}
}}"""

SYSTEM_VERIFICADOR = """Eres un auditor de veracidad de CVs. Comparas cada afirmación del CV final contra las
fuentes de verdad y eliminas o corriges todo lo que no esté respaldado. Luego puntúas el match final como reclutador.
Respondes SIEMPRE en JSON válido, con explicaciones en español.""" + REGLA_NO_INVENTAR + ESTILO_HUMANO + """
Al corregir, no reintroduzcas frases de IA ni la plantilla "as measured by"."""

PROMPT_VERIFICACION = """Audita el CV final.

=== FUENTES DE VERDAD ===
CV BASE:
{cv}
HECHOS CONFIRMADOS POR EL CANDIDATO:
{hechos}

=== CV FINAL (JSON) ===
{cv_json}

=== OFERTA (JD) ===
{jd}

=== PERFIL DE LINKEDIN DEL CANDIDATO (solo para detectar inconsistencias; NO agregues hechos desde aquí) ===
{linkedin}

Tareas:
1. Revisa cada bullet, el perfil, competencias, habilidades y certificaciones. Lista toda afirmación, cifra,
   herramienta, cliente o certificación que NO esté respaldada por las fuentes, y corrígela (reformula con lo
   respaldado o elimínala). Verifica que empresas, puestos y fechas coincidan exactamente con el CV base (se permite la entrada condensada
   "Earlier Experience"/"Experiencia previa" si respeta nombres y años).
2. Devuelve el CV corregido.
3. Puntúa el match final del CV corregido contra la oferta con esta rúbrica:
RÚBRICA FIJA (súmala; no estimes a ojo):
- obligatorios (0-50): proporción de requisitos obligatorios cumplidos × 50 (cumple = 1, parcial = 0.5, resto = 0)
- deseables (0-20): proporción de requisitos deseables cumplidos × 20 (misma regla)
- seniority (0-15): ajuste de años, nivel y alcance del rol. Estar sobrecalificado NO resta.
- industria (0-15): experiencia en la misma industria / tipo de cliente / entorno (regulado, consultoría, producto).
puntuacion = suma redondeada.
5. Si hay perfil de LinkedIn, lista discrepancias que un reclutador notaría (títulos, fechas, empresas, certificaciones
   distintas entre el CV y LinkedIn) y qué conviene alinear.
4. Da las acciones restantes más efectivas para subir aún más el match (cursos, certificaciones, proyectos,
   evidencia que el candidato podría aportar).

Devuelve SOLO este JSON:
{{
  "afirmaciones_no_respaldadas": [{{"texto": "", "problema": "", "correccion": ""}}],
  "cv": {esquema},
  "puntuacion_match_final": 0,
  "desglose_final": {{"obligatorios": 0, "deseables": 0, "seniority": 0, "industria": 0}},
  "discrepancias_linkedin": [{{"campo": "", "cv": "", "linkedin": "", "sugerencia": ""}}],
  "comentario_puntuacion": "",
  "acciones_para_subir_mas": [""]
}}"""

SYSTEM_RANKER = """Eres un reclutador técnico que hace un primer filtro rápido de ofertas para un candidato.
Respondes SIEMPRE en JSON válido."""

PROMPT_RANKING = """Perfil del candidato (resumen de su CV):
{cv}

Hechos confirmados (lo que tiene y NO tiene):
{hechos}

REGLA DE ELEGIBILIDAD (estricta): el candidato SOLO acepta (a) puestos ubicados en Costa Rica (presencial, híbrido o
remoto) o (b) puestos 100 % remotos que contraten explícitamente desde Costa Rica / LATAM / cualquier país.
Es NO elegible (false) si: la oficina está en otro país (aunque la región diga LATAM), ofrece o exige relocation,
es presencial/híbrido fuera de Costa Rica, o el remoto está restringido a otro país (ej. "US only", "Mexico only").
Usa null solo si de verdad no se puede saber.

Ofertas:
{ofertas}

{perfil_objetivo}

TUS ELECCIONES ANTERIORES (aprende de ellas: puestos parecidos a los que le interesaron suben en tipo_rol; parecidos a
los que descartó bajan):
{preferencias}

RÚBRICA (súmala, no estimes a ojo):
- tipo_rol (0-40): qué tanto el puesto es del PERFIL OBJETIVO. Si el centro del puesto es programar software,
  máximo 10 aunque mencione Azure/GCP/AWS.
- tecnologias (0-40): cuántas de las tecnologías y requisitos principales tiene en el CV o en los hechos confirmados.
- seniority (0-20): años y nivel. Estar sobrecalificado NO resta (un puesto de soporte TI no baja por eso).
puntuacion = tipo_rol + tecnologias + seniority (entero de 1 a 100).
Si la descripción es corta (solo un resumen), estima con el puesto y la empresa sin castigar por falta de
información, y dilo en el motivo. Incluye TODAS las ofertas del listado, una por id.
Para cada una da también si es elegible desde Costa Rica (true/false/null) y un motivo de una línea en español.
Devuelve SOLO este JSON: {{"ranking": [{{"id": 0, "tipo_rol": 30, "tecnologias": 25, "seniority": 15, "puntuacion": 70, "elegible_cr": true, "motivo": "..."}}]}}"""

SYSTEM_BUSCADOR = """Eres un investigador de mercado laboral tecnológico en Costa Rica. Usas la búsqueda web para
encontrar ofertas REALES y VIGENTES. Nunca inventas ofertas ni enlaces: solo incluyes ofertas cuyo enlace viste en
los resultados de búsqueda. Respondes al final con JSON válido."""

PROMPT_BUSQUEDA_CR = """Busca ofertas de empleo publicadas recientemente (últimas 4 semanas, hoy es {hoy}) que encajen
con este perfil:

{perfil}

Ámbito: (a) puestos en Costa Rica (presencial/híbrido en GAM o remoto), y (b) puestos 100% remotos que acepten
candidatos en Costa Rica / LATAM.
EXCLUYE: puestos con oficina en otro país (aunque digan LATAM), que ofrezcan relocation, presenciales/híbridos fuera
de Costa Rica, o remotos restringidos a otro país. En "ubicacion" escribe la ciudad/país real o "Remoto (LATAM)" etc.
ESTA BÚSQUEDA ES SOLO PARA UN ÁREA: «{area}» (términos: {keywords}).
Busca únicamente ofertas de esta área; no mezcles otras áreas ni combines todos los criterios en una sola búsqueda.
Tienes {busquedas} búsquedas: úsalas en sitios distintos, por ejemplo una en LinkedIn Jobs / Glassdoor
(glassdoor.com) con «{area} Costa Rica», y otra en Computrabajo, Indeed Costa Rica, Get on Board, Torre o páginas de
empleo de empresas con operación en Costa Rica (Microsoft, Oracle, AWS, IBM, Kyndryl, Accenture, Deloitte, EY, PwC,
KPMG, Intel, HPE, Dell, Cisco, Broadcom/VMware, ServiceNow, Workday, SAP, Akamai, Equifax, Experian, Pythian,
Concentrix, Gartner, Boston Scientific, P&G, Fiserv, Western Union, Citi, BAC Credomatic, etc.) o «{area} remote LATAM».
Prioriza puestos senior (Senior, Lead, Principal, Staff, Architect, Manager técnico).

LINKS (muy importante): "url" debe ser el enlace DIRECTO de UNA oferta concreta, por ejemplo
linkedin.com/jobs/view/<número>, glassdoor.com/job-listing/..., indeed.com/viewjob?jk=..., computrabajo.com/ofertas-de-trabajo/...,
o la página de la vacante en el portal de la empresa (Workday, Greenhouse, Lever, SuccessFactors...).
NUNCA uses páginas de resultados o listas (linkedin.com/jobs/search, ".../cloud-architect-jobs-costa-rica", búsquedas
de Indeed o Glassdoor). Si solo viste una lista, busca el enlace directo de esa oferta; si no lo encuentras, NO la incluyas.
No construyas ofertas a partir de fragmentos de una lista.

Devuelve al final SOLO este JSON con hasta {n} ofertas:
{{"ofertas": [{{"empresa": "", "puesto": "", "url": "", "ubicacion": "", "modalidad": "", "resumen": "", "sitio": ""}}]}}
"sitio" = dónde la encontraste (Glassdoor, LinkedIn, Computrabajo, página de la empresa, etc.).
"resumen" = 2-3 frases con los requisitos principales que viste (plataformas, años, certificaciones, idioma)."""

SYSTEM_SKILLS = """Eres un mentor de carrera en cloud e infraestructura. Agrupas habilidades sinónimas y priorizas
qué aprender según la demanda real observada en las ofertas. Respondes SIEMPRE en JSON válido en español."""

PROMPT_TOP_SKILLS = """Estas son las brechas (habilidades/palabras clave faltantes) detectadas en las ofertas que el
candidato ha analizado, con su frecuencia ponderada:
{brechas}

Hechos confirmados del candidato (para no recomendar lo que ya domina):
{hechos}

Agrupa sinónimos (ej. "K8s", "Kubernetes", "AKS/GKE" → "Kubernetes") y devuelve el TOP 5 de habilidades que debe
aprender, ordenadas por impacto en su empleabilidad.
{web_instr}
Devuelve SOLO este JSON:
{{"top5": [{{"habilidad": "", "puntaje": 0, "aparece_en_ofertas": 0, "por_que": "",
            "certificacion_sugerida": "",
            "cursos": [{{"nombre": "", "plataforma": "", "url": "", "gratis": true}}]}}]}}"""

WEB_INSTR_SKILLS = """Para cada habilidad usa la búsqueda web para encontrar 2-3 cursos CONCRETOS y vigentes:
prioriza el training gratuito del fabricante (Microsoft Learn, Google Cloud Skills Boost, AWS Skill Builder,
HashiCorp, Linux Foundation, Red Hat, Cisco NetAcad, etc.), luego Udemy y Coursera (el candidato está suscrito a
ambos). Solo incluye URLs que viste en los resultados de búsqueda."""


SYSTEM_PULIDO = """Eres un editor que hace que textos de CV suenen escritos por una persona, sin cambiar los hechos.
Respondes SIEMPRE en JSON válido.""" + REGLA_NO_INVENTAR + ESTILO_HUMANO

PROMPT_PULIDO = """Estas líneas del CV tienen marcas típicas de texto generado por IA. Reescribe SOLO esas líneas para que
suenen naturales, manteniendo exactamente los mismos hechos, cifras, herramientas y palabras clave técnicas, en el
mismo idioma ({idioma}).

{lineas}

FUENTES DE VERDAD (no agregues nada que no esté aquí):
{cv}
{hechos}

Devuelve SOLO este JSON: {{"cambios": [{{"original": "texto exacto original", "nuevo": "texto reescrito"}}]}}"""


# ---------------- reutilizar respuestas previas ----------------
SYSTEM_COINCIDENCIAS = """Comparas requisitos de una oferta con respuestas que un candidato ya confirmó sobre sus
habilidades. Decides por SIGNIFICADO técnico, no solo por nombre (ej. "AKS" o "container orchestration" se relacionan con
una respuesta sobre Kubernetes; "landing zone" con una sobre Azure Landing Zones). No inventas relaciones dudosas.
Respondes SIEMPRE en JSON válido."""

PROMPT_COINCIDENCIAS = """REQUISITOS SIN RESPUESTA TODAVÍA:
{requisitos}

RESPUESTAS YA CONFIRMADAS POR EL CANDIDATO (nombre exacto | tiene | detalle):
{hechos}

Para cada requisito indica si alguna respuesta confirmada lo responde:
- "cubre": "si" si la respuesta demuestra ese requisito; "parcial" si lo cubre en parte (ej. labs, experiencia no central);
  "no_tiene" si una respuesta dice claramente que NO lo tiene; "ninguna" si ninguna respuesta aplica.
- "hecho": el NOMBRE EXACTO de la respuesta usada (copiado tal cual), o "" si es "ninguna".
- "motivo": una línea en español.
Devuelve SOLO este JSON: {{"coincidencias": [{{"requisito": "", "cubre": "", "hecho": "", "motivo": ""}}]}}"""

# ---------------- contexto de empresa ----------------
SYSTEM_EMPRESA = """Eres un analista que investiga empresas para preparar candidaturas. Usas la búsqueda web y no
inventas datos. Respondes al final con JSON válido en español."""

PROMPT_EMPRESA = """Investiga brevemente a la empresa "{empresa}" (oferta: {puesto}). Máximo 3 búsquedas.
Fragmento de la oferta:
{jd}

Devuelve SOLO este JSON:
{{"industria": "", "regulada": true, "tamano": "", "presencia_costa_rica": "", "stack_mencionado": [""],
  "cultura_valores": "", "que_priorizar_en_cv": [""]}}
"que_priorizar_en_cv" = tipos de experiencia que más valoraría esta empresa (ej. "banca regulada", "migraciones a
escala", "consultoría client-facing"). No describas al candidato."""

# ---------------- banco de métricas ----------------
SYSTEM_METRICAS = """Eres un coach de CVs que ayuda a recuperar cifras reales para bullets con fórmula XYZ.
Respondes SIEMPRE en JSON válido en español."""

PROMPT_METRICAS = """Este es el CV base del candidato y lo que ya confirmó:

CV BASE:
{cv}

HECHOS CONFIRMADOS:
{hechos}

Identifica los logros o responsabilidades que NO tienen cifra (o la tienen vaga) y redacta hasta 15 preguntas cortas
para que el candidato aporte números REALES: tamaño de equipos, cantidad de servidores/VMs/bases/usuarios/buzones,
países o sitios, presupuestos, SLAs/uptime, tiempos antes/después, ahorros, tickets, etc.
No preguntes lo que ya está en el CV o en los hechos. Prioriza los roles más recientes del CV.

Devuelve SOLO este JSON:
{{"preguntas": [{{"id": "m1", "rol": "", "logro": "", "pregunta": "", "ejemplo_respuesta": ""}}]}}"""

# ---------------- preparación de entrevista ----------------
SYSTEM_ENTREVISTA = """Eres un entrevistador técnico senior y coach de entrevistas. Preparas al candidato con preguntas
probables y respuestas STAR construidas SOLO con sus datos reales. Respondes SIEMPRE en JSON válido en español.""" + REGLA_NO_INVENTAR

PROMPT_ENTREVISTA = """Prepara al candidato para la entrevista de esta oferta.

=== OFERTA ===
{jd}

=== CV QUE VA A ENVIAR ===
{cv_json}

=== FUENTES DE VERDAD ===
{cv}
{hechos}

Tareas:
1. Las 6-8 preguntas más probables (técnicas y conductuales) que le harían SOBRE SU CV y la oferta, en el idioma de
   la oferta.
2. Para cada una, un esquema STAR (situación, tarea, acción, resultado) usando solo hechos de las fuentes. Si falta
   un dato, escribe "[completa: qué dato falta]" en vez de inventarlo.
3. Marca si la pregunta es defendible con lo que hay (true/false) y el riesgo si no lo es.
4. Lista los bullets del CV que serían difíciles de defender y por qué.

Devuelve SOLO este JSON:
{{"preguntas": [{{"pregunta": "", "sobre": "", "situacion": "", "tarea": "", "accion": "", "resultado": "",
                  "defendible": true, "riesgo": ""}}],
  "bullets_debiles": [{{"bullet": "", "por_que": ""}}]}}"""

# ---------------- cover letter y mensaje ----------------
SYSTEM_COVER = """Escribes cover letters y mensajes a reclutadores breves, concretos y humanos para perfiles técnicos
senior. Respondes SIEMPRE en JSON válido.""" + REGLA_NO_INVENTAR + ESTILO_HUMANO

PROMPT_COVER = """Escribe para esta oferta, en {idioma}:
(a) un cover letter de 220-300 palabras: por qué esta empresa/puesto, 2-3 logros con cifras reales del CV que
    conecten con la oferta, y cierre con disponibilidad. Sin frases de plantilla ("I am writing to express...").
(b) un mensaje para el reclutador en LinkedIn de máximo 300 caracteres.
(c) un asunto de correo.

=== OFERTA ===
Empresa: {empresa} · Puesto: {puesto}
{jd}

=== CV ENVIADO ===
{cv_json}

=== FUENTES DE VERDAD ===
{hechos}

Devuelve SOLO este JSON: {{"asunto": "", "cover_letter": "", "mensaje_linkedin": ""}}"""

# ---------------- seguimiento ----------------
SYSTEM_SEGUIMIENTO = """Escribes correos de seguimiento de candidaturas: cortos, cordiales y humanos.
Respondes SIEMPRE en JSON válido.""" + ESTILO_HUMANO

PROMPT_SEGUIMIENTO = """El candidato {nombre} aplicó al puesto "{puesto}" en {empresa} hace {dias} días y no ha tenido
respuesta. Escribe un correo de seguimiento de 70-110 palabras en {idioma}: reafirma interés, recuerda 1 logro
relevante con cifra (de este CV: {resumen}), y pregunta por los siguientes pasos. Sin presionar.
Devuelve SOLO este JSON: {{"asunto": "", "cuerpo": ""}}"""


SYSTEM_REFRASEO = """Eres un reclutador técnico que ayuda a un candidato a explicar mejor su experiencia.
Reescribes su respuesta para que sea clara, concreta y fácil de usar en un CV (qué hizo, con qué, a qué escala,
qué logró). REGLA ABSOLUTA: no agregas NINGÚN dato que no esté en su texto (ni herramientas, cifras, fechas,
empresas, cargos ni resultados). Si algo útil falta, lo propones como pregunta en "falta". Respondes SIEMPRE en
JSON válido."""

PROMPT_REFRASEO = """Requisito de la oferta: {requisito}
Pregunta que se le hizo: {pregunta}
Respuesta del candidato ({nivel}):
\"\"\"{texto}\"\"\"

Reescríbela en el mismo idioma en que la escribió, en 1-3 frases directas, primera persona implícita (sin "yo"),
corrigiendo ortografía y orden. Conserva todos los datos que dio y no inventes ninguno.
En "falta" pon hasta 3 preguntas cortas sobre datos que harían la respuesta más fuerte (cifras, escala, fechas,
resultado), solo si de verdad faltan.
Devuelve SOLO este JSON: {{"texto": "", "falta": [""]}}"""

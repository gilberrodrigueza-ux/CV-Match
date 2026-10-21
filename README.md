# CV Match

**Asistente de búsqueda de empleo con IA:** encuentra ofertas en Costa Rica o remotas contratables desde Costa Rica, calcula el match con tu CV y adapta el CV a cada oferta como lo haría un reclutador, **sin inventar datos**.

*AI job-search assistant: finds Costa Rica / remote-from-Costa-Rica jobs, scores them against your CV and tailors the CV per posting like a recruiter would, without fabricating experience. Python + Streamlit, multi-LLM (Claude, Gemini, local Ollama).*

---

## Qué hace

**Búsqueda por área, del más barato al más caro**
- Bolsas remotas con API pública (Remotive, RemoteOK, Himalayas, Jobicy, We Work Remotely, Working Nomads).
- Portales de empleo de empresas leídos directo, sin IA: Workday, Greenhouse, Lever, SmartRecruiters y Ashby. Se agregan pegando la URL o se descubren solos.
- Búsqueda web de ofertas locales con **Tavily** (capa gratuita). **Claude** queda como último recurso.
- Filtro estricto de ubicación: descarta "US only", relocation u oficinas en otro país, aunque la oferta diga "Anywhere".
- Filtro de perfil y nivel: desarrollo, QA o ventas fuera; junior o intern fuera, configurable.
- Verifica que la oferta siga abierta antes de mostrarla.
- Botón **"No me interesa"**: la IA aprende de lo que eliges y descartas.
- Mide qué fuente y qué área aportan ofertas útiles, y apaga solas las bolsas que no rinden.

**Match y adaptación del CV**
- Filtro rápido gratis (Ollama local o Gemini) con rúbrica: tipo de rol 40, tecnologías 40, seniority 20.
- Análisis de reclutador (Claude) con rúbrica fija: obligatorios 50, deseables 20, seniority 15, industria 15. Entrega las 5 palabras clave que faltan, 3 red flags y los requisitos eliminatorios.
- Antes de adaptar, **pregunta lo que no está en el CV** y reutiliza las respuestas ya guardadas. Tiene botón ✨ para refrasear la respuesta sin agregar datos.
- Reescritura con la **fórmula XYZ de Google**, escaneo ATS y una revisión de "reclutador que lee 100 CVs".
- Auditoría que verifica que cada dato salga del CV o de tus respuestas, y pulido para que el texto suene humano.
- Salida en DOCX/PDF compatible con ATS, más cover letter, preparación de entrevista e investigación de la empresa.

**Multiusuario**
- Cada persona entra con **usuario y contraseña**. Las contraseñas se guardan con PBKDF2-SHA256 y sal, nunca en texto plano.
- Cada usuario tiene sus propios datos: CV, claves de API, historial, respuestas, cola, configuración y carpeta de CVs generados.
- La primera vez que se abre, se crea el administrador. El administrador crea usuarios, restablece contraseñas y define si cualquiera puede registrarse.
- La búsqueda automática se programa por usuario.
- Una instalación de una sola persona puede convertirse a multiusuario desde ⚙️ Configuración → 👥 Usuarios, sin perder datos.

**Seguimiento y productividad**
- Historial (SQLite) y embudo con estadísticas por área y por fuente.
- Integración opcional con Outlook (Microsoft Graph): detecta respuestas de empresas y puede enviarte un resumen diario a tu propio correo.
- **Banco de respuestas para formularios** de postulación.
- **Simulador de entrevista** con nota y repregunta.
- Top 5 de habilidades a aprender, con cursos y un plan de estudio con progreso.
- Empresas favoritas, ofertas frescas primero, cola persistente.
- Búsqueda automática programada (Programador de tareas de Windows).
- Acceso desde el celular en la red local o por Tailscale, con contraseña.
- Control de gasto: medidor real por llamada, tope mensual y modelo por tarea.

## Stack

Python 3.11+, Streamlit, Anthropic SDK (Claude), Gemini API, Ollama (IA local), Tavily, python-docx, pdfplumber/pypdf, SQLite, MSAL / Microsoft Graph.

## Instalación (Windows)

1. Instala Python 3.11 o superior.
2. Ejecuta `instalar.bat`. Crea el entorno virtual e instala las dependencias.
3. Ejecuta `ejecutar_gui.bat`. Se abre en `http://localhost:8501`.
4. La primera vez, crea tu cuenta de **administrador** (usuario y contraseña).
5. En **⚙️ Configuración**:
   - Pega tu API key de Anthropic.
   - Sube tu CV base (PDF o DOCX).
   - Opcional: claves de Tavily y Gemini para búsquedas gratis, y Ollama para evaluar ofertas gratis en tu PC.

La carpeta `datos/` (usuarios, claves, historial, respuestas, configuración de cada usuario) se crea localmente y **está excluida del repositorio**.

## Privacidad

Todo corre en tu PC o servidor. Cada usuario solo ve sus propios datos (`datos/usuarios/<usuario>/`). Las claves, los CVs, las respuestas y el historial nunca se suben a este repositorio (ver `.gitignore`). Las llamadas a los modelos de IA envían solo el texto necesario para cada tarea.

## Licencia

MIT

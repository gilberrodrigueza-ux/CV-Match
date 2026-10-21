@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Primero ejecuta instalar.bat
  pause
  exit /b 1
)
.venv\Scripts\python.exe -c "import streamlit, pandas, pypdf, msal, segno; v=tuple(int(x) for x in streamlit.__version__.split('.')[:2]); assert v>=(1,45)" >nul 2>nul
if errorlevel 1 (
  echo Instalando componentes de la interfaz grafica, solo esta vez...
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)
set PYTHONUTF8=1
echo Abriendo CV Match en tu navegador... (no cierres esta ventana mientras la usas)
start "" cmd /c "timeout /t 5 >nul & start http://localhost:8501"
.venv\Scripts\python.exe -m streamlit run gui.py
pause

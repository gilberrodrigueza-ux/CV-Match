@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Primero ejecuta instalar.bat
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m cvmatch.scheduler activar
echo.
echo Las horas se cambian en la interfaz: Configuracion - Busqueda automatica.
pause

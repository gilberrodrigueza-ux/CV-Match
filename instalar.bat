@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Instalando CV Match ===
set PY=
where py >nul 2>nul && set PY=py -3
if "%PY%"=="" where python >nul 2>nul && set PY=python
if "%PY%"=="" (
  echo No encontre Python. Instalalo desde https://www.python.org/downloads/ marcando "Add python.exe to PATH" y vuelve a ejecutar este archivo.
  pause
  exit /b 1
)
if not exist .venv %PY% -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Hubo un error instalando dependencias.
  pause
  exit /b 1
)
echo.
echo Listo. Ahora ejecuta "ejecutar.bat".
pause

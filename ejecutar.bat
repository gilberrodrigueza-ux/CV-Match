@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Primero ejecuta instalar.bat
  pause
  exit /b 1
)
set PYTHONUTF8=1
.venv\Scripts\python.exe cvmatch.py
pause

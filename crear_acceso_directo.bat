@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=[Environment]::GetFolderPath('Desktop'); $w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut((Join-Path $d 'CV Match.lnk')); $s.TargetPath='%~dp0ejecutar_gui.bat'; $s.WorkingDirectory='%~dp0'; $s.WindowStyle=7; $s.IconLocation='imageres.dll,109'; $s.Save()"
echo Acceso directo "CV Match" creado en tu escritorio.
pause

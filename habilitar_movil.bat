@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Creando regla de firewall para CV Match (solo red local y Tailscale, no internet)...
powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-Command','Remove-NetFirewallRule -DisplayName ''CV Match (red local y Tailscale)'' -ErrorAction SilentlyContinue; New-NetFirewallRule -DisplayName ''CV Match (red local y Tailscale)'' -Direction Inbound -Protocol TCP -LocalPort 8501 -Action Allow -Profile Any -RemoteAddress LocalSubnet,100.64.0.0/10'"
echo Listo. Ahora activa el acceso y pon tu contrasena en CV Match: Configuracion - Acceso desde el celular.
pause

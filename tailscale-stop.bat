@echo off
REM Stop exposing Aadyon Assist over Tailscale (removes the serve config).
REM Your laptop stays on the tailnet; only the localhost:8000 proxy is removed.
cd /d "%~dp0"
where tailscale >nul 2>&1 || ( echo [ERROR] Tailscale not on PATH. & pause & exit /b 1 )
tailscale serve reset
echo Tailscale serve config cleared.
tailscale serve status
pause

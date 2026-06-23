@echo off
REM ============================================================
REM  Expose Aadyon Assist (localhost:8000) over YOUR Tailscale
REM  network only - private to your signed-in devices, HTTPS.
REM  Prereq: install Tailscale + sign in (see TAILSCALE.md).
REM ============================================================
cd /d "%~dp0"

where tailscale >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Tailscale is not installed / not on PATH.
  echo Install from https://tailscale.com/download , sign in, then run this again.
  pause & exit /b 1
)

echo Checking that the app is up locally...
curl -fsS http://localhost:8000/api/health >nul 2>&1
if errorlevel 1 ( echo [WARN] localhost:8000 not responding - start the stack first (run.bat). )

echo.
echo Publishing http://localhost:8000 to your tailnet over HTTPS...
tailscale serve --bg 8000
if errorlevel 1 (
  echo Trying alternate syntax...
  tailscale serve --bg http://127.0.0.1:8000
)

echo.
echo === Current Tailscale serve config (your private URL is shown below) ===
tailscale serve status
REM Also record status to a file (gitignored) so it can be reviewed after the window closes.
( echo ==== tailscale serve status ==== & tailscale serve status & echo. & echo ==== tailscale status ==== & tailscale status ) > "%~dp0tailscale-status.txt" 2>&1
echo.
echo Open that https://...ts.net URL on any device signed into YOUR Tailscale account
echo (install the Tailscale app on your phone and sign in with the same account).
echo This is NOT public - do not run "tailscale funnel" unless you intend public access.
echo.
pause

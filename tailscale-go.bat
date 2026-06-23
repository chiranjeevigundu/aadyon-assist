@echo off
cd /d "%~dp0"
set "TSDIR=C:\Program Files\Tailscale"

REM Record what's actually in the Tailscale folder so we can see the CLI name.
( echo ==== contents of %TSDIR% ==== & dir /b "%TSDIR%" ) > "%~dp0tailscale-status.txt" 2>&1

if exist "%TSDIR%\tailscale.exe" (
  "%TSDIR%\tailscale.exe" serve --bg 8000
  if errorlevel 1 "%TSDIR%\tailscale.exe" serve --bg http://127.0.0.1:8000
  (
    echo.
    echo ==== tailscale serve status ====
    "%TSDIR%\tailscale.exe" serve status
    echo.
    echo ==== tailscale status ====
    "%TSDIR%\tailscale.exe" status
  ) >> "%~dp0tailscale-status.txt" 2>&1
) else (
  echo. >> "%~dp0tailscale-status.txt"
  echo tailscale.exe NOT found in %TSDIR% ^(only the GUI is installed^) >> "%~dp0tailscale-status.txt"
)
echo done

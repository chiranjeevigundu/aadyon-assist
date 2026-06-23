@echo off
cd /d "%~dp0"
set "TS=C:\Program Files\Tailscale\tailscale.exe"
(
  echo ==== tailscale IPv4 ====
  "%TS%" ip -4
  echo.
  echo ==== tailscale dns name ====
  "%TS%" status --json 2>nul | findstr /i "DNSName"
  echo.
  echo ==== tailscale status ====
  "%TS%" status
) > "%~dp0tailscale-status.txt" 2>&1
echo done

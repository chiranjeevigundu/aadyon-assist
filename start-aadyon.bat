@echo off
REM Aadyon Assist auto-start (runs at Windows login). Waits for Docker, then starts the stack.
:waitdocker
docker info >nul 2>&1
if errorlevel 1 (
  timeout /t 5 /nobreak >nul
  goto waitdocker
)
cd /d "D:\AI\aadyon-assist"
docker compose up -d

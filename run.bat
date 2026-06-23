@echo off
REM Aadyon Assist launcher - starts the DB + API stack via Docker.
cd /d "%~dp0"

where docker >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Docker is not installed or not on PATH. Install/start Docker Desktop first.
  pause
  exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Docker Desktop is not running. Start it, then run this again.
  pause
  exit /b 1
)

echo Building and starting containers...
docker compose up -d --build
if errorlevel 1 (
  echo [ERROR] docker compose failed. See output above.
  pause
  exit /b 1
)

echo.
echo Waiting for the API to come up...
timeout /t 5 /nobreak >nul
start "" http://localhost:8000
echo.
echo Aadyon Assist is running:
echo   Dashboard:  http://localhost:8000
echo   API docs:   http://localhost:8000/docs
echo   Stop with:  docker compose down
echo.
pause

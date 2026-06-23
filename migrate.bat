@echo off
REM Applies all idempotent DB migrations (03_*.sql and up) to the RUNNING database,
REM then rebuilds the API so new endpoints + dashboards ship.
REM 01_schema/02_seed are skipped (they only run on a fresh volume). Safe to re-run.
cd /d "%~dp0"

docker info >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Docker Desktop is not running. Start it, then run this again.
  pause
  exit /b 1
)

echo Applying migrations (03+_*.sql) to the live database...
docker compose exec -T db sh -c "set -e; export PGPASSWORD=$(cat /run/secrets/db_password); for f in /docker-entrypoint-initdb.d/0[3-9]_*.sql; do echo \"-- applying $f\"; psql -v ON_ERROR_STOP=1 -U $POSTGRES_USER -d $POSTGRES_DB -f \"$f\"; done"
if errorlevel 1 (
  echo.
  echo [ERROR] Migration failed. Is the stack running? Try run.bat first.
  pause
  exit /b 1
)

echo.
echo Rebuilding all services with the new code, dashboards, and workers...
docker compose up -d --build
if errorlevel 1 (
  echo [ERROR] Rebuild failed. See output above.
  pause
  exit /b 1
)

echo.
echo Done. Opening the dashboard:
echo   http://localhost:8000
start "" http://localhost:8000
echo.
pause

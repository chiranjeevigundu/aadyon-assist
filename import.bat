@echo off
REM Imports entities from artifacts\inbox.json into the running tracker.
cd /d "%~dp0"

echo Ensuring the API container has the latest importer...
docker compose up -d --build api briefing >nul 2>&1

echo Importing entities from artifacts\inbox.json ...
docker compose exec -T api python -m app.jobs.import_entities
if errorlevel 1 (
  echo.
  echo [ERROR] Import failed. Is the stack running? Try run.bat first.
)
echo.
pause

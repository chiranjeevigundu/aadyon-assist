@echo off
REM ============================================================
REM  Start a new feature branch off an up-to-date main.
REM  Use this before parallel / agent work so each feature lands
REM  via its own branch + Pull Request (no clobbering main).
REM ============================================================
cd /d "%~dp0"

where git >nul 2>&1
if errorlevel 1 ( echo [ERROR] git is not on PATH. & pause & exit /b 1 )

set /p NAME="New feature branch name (e.g. email-rules): "
if "%NAME%"=="" ( echo [ERROR] A name is required. & pause & exit /b 1 )

git checkout main || ( echo [ERROR] could not switch to main. & pause & exit /b 1 )
git pull --ff-only
git checkout -b feat/%NAME%
if errorlevel 1 ( echo [ERROR] could not create branch (does it already exist?). & pause & exit /b 1 )

echo.
echo Created and switched to feat/%NAME%.
echo Make your changes, then run commit-and-push.bat and open a Pull Request.
pause

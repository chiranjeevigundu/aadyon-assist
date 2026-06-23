@echo off
REM ============================================================
REM  Aadyon Assist - safe incremental commit + push
REM  Normal, linear git history (NO force-push, NO history rewrite),
REM  so feature branches and PR-based agents (Codex, Antigravity) and
REM  Claude in Cowork can all collaborate without clobbering each other.
REM  Keeps the personal-data guard before every commit.
REM
REM  Solo quick change on main? Just run this.
REM  Parallel / agent work? Start a branch first with feature.bat, then
REM  run this on the branch and open a Pull Request on GitHub.
REM ============================================================
cd /d "%~dp0"

where git >nul 2>&1
if errorlevel 1 ( echo [ERROR] git is not on PATH. Install Git, then retry. & pause & exit /b 1 )

if exist ".git\index.lock" ( echo Removing stale .git\index.lock ... & del /f /q ".git\index.lock" >nul 2>&1 )

for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do set BR=%%b
echo Current branch: %BR%

git add -A

REM --- Safety net: never commit a personal/seed/secret file ---
git ls-files | findstr /i /c:"init/02_seed.sql" /c:"99_seed_local.sql" /c:"notes/" /c:"secrets/" >nul
if not errorlevel 1 (
  echo.
  echo [ERROR] A personal/secret file is staged. Aborting BEFORE commit. Offending:
  git ls-files | findstr /i /c:"init/02_seed.sql" /c:"99_seed_local.sql" /c:"notes/" /c:"secrets/"
  pause & exit /b 1
)

set /p MSG="Commit message: "
if "%MSG%"=="" set MSG=update

git commit -q -m "%MSG%"
if errorlevel 1 ( echo [info] Nothing to commit. & pause & exit /b 0 )

echo Pushing %BR% to origin (normal push, no force)...
git push -u origin %BR%
if errorlevel 1 (
  echo.
  echo Push failed. Common fixes:
  echo   - When asked for a password, paste a GitHub Personal Access Token ^(not your password^).
  echo   - Or run:  gh auth login
  echo   - If the remote moved ahead, run:  git pull --ff-only   then push again.
)
echo.
if /i not "%BR%"=="main" (
  echo Branch pushed. Open a Pull Request:
  echo   https://github.com/chiranjeevigundu/aadyon-assist/pull/new/%BR%
  echo.
)
pause

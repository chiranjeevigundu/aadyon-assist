@echo off
REM ============================================================
REM  Aadyon Assist - clean commit + push to GitHub (PRIVATE repo)
REM  Builds ONE fresh commit from an EMPTY index, so .gitignore is
REM  fully respected and no personal data (or old history) is pushed.
REM  Re-runnable and safe: never force-checkouts, never discards your edits.
REM ============================================================
cd /d "%~dp0"

where git >nul 2>&1
if errorlevel 1 ( echo [ERROR] git is not on PATH. Install Git, then retry. & pause & exit /b 1 )

if exist ".git\index.lock" ( echo Removing stale .git\index.lock ... & del /f /q ".git\index.lock" >nul 2>&1 )

echo Preparing a clean, empty index (working files are left untouched)...
REM Point HEAD at a fresh unborn branch and empty the index. Working tree is NOT touched.
git symbolic-ref HEAD refs/heads/__pub
git reset -q

REM Stage everything that is NOT gitignored (personal files are skipped from the start).
git add -A

REM Belt-and-suspenders: drop personal paths from the index if anything slipped in.
git rm -r --cached --ignore-unmatch "code/db/init/02_seed.sql" "code/db/init/99_seed_local.sql" "notes" "data" >nul 2>&1

REM --- Safety net: never commit a personal file ---
git ls-files | findstr /i /c:"init/02_seed.sql" /c:"99_seed_local.sql" /c:"notes/" /c:"secrets/" >nul
if not errorlevel 1 (
  echo.
  echo [ERROR] A personal file is still staged. Aborting BEFORE commit/push. Offending:
  git ls-files | findstr /i /c:"init/02_seed.sql" /c:"99_seed_local.sql" /c:"notes/" /c:"secrets/"
  pause & exit /b 1
)

git commit -q -m "Aadyon Assist: Digital Me + jobs/EMI + data admin + agentic org (clean history, no personal data)"
if errorlevel 1 ( echo [ERROR] commit failed. & pause & exit /b 1 )

REM Make main point at this clean commit, switch to it, drop the temp branch.
git branch -f main __pub
git symbolic-ref HEAD refs/heads/main
git branch -D __pub >nul 2>&1

echo.
echo === Files that will be pushed (scan for anything personal) ===
git ls-files | findstr /i "seed notes data secret openrouter env"
echo === Expect ONLY code/db/seed.example.sql (+ doc mentions). NOT 02_seed.sql / 99_seed_local.sql / notes/ ===
echo.
set /p OK="Force-push this clean history to origin/main? (y/n): "
if /i not "%OK%"=="y" (
  echo Aborted. Clean commit is ready locally; run "git push --force -u origin main" when ready.
  pause & exit /b 0
)

git push --force -u origin main
if errorlevel 1 (
  echo.
  echo Push failed. Common fixes:
  echo   - When asked for a password, paste a GitHub Personal Access Token ^(not your password^).
  echo   - Or first run:  gh auth login
  echo   - Confirm the private repo exists: https://github.com/chiranjeevigundu/aadyon-assist
)
echo.
pause

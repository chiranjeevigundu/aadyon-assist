@echo off
cd /d "%~dp0"
echo Pushing aadyon-assist to GitHub...
git push -u origin main
if %errorlevel% neq 0 (
  echo.
  echo Push failed. Common fixes:
  echo  - Make sure the repo exists at https://github.com/chiranjeevigundu/aadyon-assist
  echo  - If asked for a password, use a Personal Access Token, not your account password
  echo  - Or run: gh auth login   (GitHub CLI^)
)
echo.
pause

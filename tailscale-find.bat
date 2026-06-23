@echo off
cd /d "%~dp0"
(
  echo ==== where tailscale ====
  where tailscale
  echo.
  echo ==== Get-Command source ====
  powershell -NoProfile -Command "(Get-Command tailscale -ErrorAction SilentlyContinue).Source"
  echo.
  echo ==== probe common locations ====
  powershell -NoProfile -Command "$p=@(\"$env:ProgramFiles\Tailscale\tailscale.exe\",\"${env:ProgramFiles(x86)}\Tailscale\tailscale.exe\",\"$env:LOCALAPPDATA\Microsoft\WindowsApps\tailscale.exe\"); foreach($x in $p){ if(Test-Path $x){ \"FOUND: $x\" } else { \"miss : $x\" } }"
  echo.
  echo ==== search WindowsApps (Store installs) ====
  powershell -NoProfile -Command "Get-ChildItem 'C:\Program Files\WindowsApps' -Filter tailscale.exe -Recurse -ErrorAction SilentlyContinue | Select -First 3 -Expand FullName"
) > "%~dp0tailscale-status.txt" 2>&1
echo Wrote tailscale-status.txt

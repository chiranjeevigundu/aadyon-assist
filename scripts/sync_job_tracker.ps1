# Windows wrapper for scripts/sync_job_tracker.py — meant to be launched by Task
# Scheduler ~30 min after the daily job-search digest updates the tracker xlsx.
#
# NO SECRETS LIVE IN THIS FILE. Credentials are read from environment variables
# (set them once as *user* env vars so the scheduled task inherits them):
#
#   setx AADYON_TOKEN  "<a long-lived JWT from POST /api/auth/login>"
#   # ...or, to log in fresh each run instead of storing a token:
#   setx AADYON_EMAIL    "you@example.com"
#   setx AADYON_PASSWORD "your-password"
#
#   setx AADYON_BASE   "http://mini-a:8000"     # your API over the tailnet
#   setx JOB_TRACKER_XLSX "D:\resume\CV\interview-prep\JOB_TRACKER.xlsx"
#
# The script itself resolves auth from $AADYON_TOKEN, else $AADYON_EMAIL/
# $AADYON_PASSWORD (see sync_job_tracker.py). Pass -DryRun to preview.

param(
    [switch]$DryRun,
    [string]$Xlsx = $env:JOB_TRACKER_XLSX,
    [string]$Base = $env:AADYON_BASE
)

$ErrorActionPreference = "Stop"

# Resolve repo root from this script's location (scripts\ -> repo root).
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Py = Join-Path $RepoRoot "scripts\sync_job_tracker.py"

if (-not $Xlsx) { throw "Set JOB_TRACKER_XLSX (or pass -Xlsx) to the tracker path." }
if (-not $Base) { $Base = "http://localhost:8000" }

$cliArgs = @("--xlsx", $Xlsx, "--base", $Base)
if ($DryRun) { $cliArgs += "--dry-run" }

# Prefer the venv python if one exists, else the system python.
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

Write-Host "[$(Get-Date -Format s)] sync-jobs -> $Base ($Xlsx)"
& $Python $Py @cliArgs
exit $LASTEXITCODE

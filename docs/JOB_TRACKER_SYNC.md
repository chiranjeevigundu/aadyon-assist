# Job-tracker sync

Pull the rows of a job-tracker spreadsheet into the API's `applications` table
so the Digital Me **Career** dimension reflects your live job search. The sync
is an idempotent upsert: it creates rows that don't exist yet, PATCHes only the
fields that actually changed, and leaves everything else untouched — so it's
safe to run on a schedule.

- Script: [`scripts/sync_job_tracker.py`](../scripts/sync_job_tracker.py)
- Recipe: `just sync-jobs <xlsx> [--dry-run] [--verbose]`
- Windows wrapper: [`scripts/sync_job_tracker.ps1`](../scripts/sync_job_tracker.ps1)
- New dependency: `openpyxl` (pinned in `code/api/requirements.txt`)

## What it maps

Spreadsheet headers are matched to `applications` columns by fuzzy, case-
insensitive header matching (e.g. **Job Title → role**, **Min Salary →
salary_min**, **Date Applied → applied_date**, **Remote/Hybrid → work_type**).
Only a `company` column is required; unmapped columns are ignored. Mapped
fields: `company, role, status, salary_min, salary_max, location, work_type,
source, url, applied_date, notes`.

Matching an xlsx row to an existing application uses the natural key
**(company, role)**, compared case-insensitively. An **empty cell is dropped**
from the payload, so a sparse tracker never clears data the API already holds.

Values are canonicalised before comparison so a re-run is a true no-op:
- dates (a datetime cell, `2026-07-15`, `07/15/2026`, an ISO echo) → `YYYY-MM-DD`;
- money (`$120,000`, `120000`, `150k`) → a 2-decimal float, matching the
  `numeric(12,2)` the API returns.

## Auth (never commit secrets)

Resolved in order — first that's present wins:
1. `--token` / `$AADYON_TOKEN` — a JWT from `POST /api/auth/login`.
2. `--email`/`--password` or `$AADYON_EMAIL` / `$AADYON_PASSWORD` — logs in each run.

Put these in your environment or a **gitignored** `.env`, never on the command
line or in a committed file. gitleaks gates CI and pre-commit.

## Run it manually

```bash
# preview (auth + read live rows, print the plan, write nothing)
AADYON_TOKEN=… just sync-jobs /path/to/JOB_TRACKER.xlsx --dry-run

# for real, against the tailnet API
AADYON_BASE=http://mini-a:8000 AADYON_TOKEN=… just sync-jobs /path/to/JOB_TRACKER.xlsx
```

## Windows Task Scheduler (runs ~30 min after the morning digest)

The daily job-search digest rewrites the xlsx each morning; schedule the sync a
little after it. Set the credentials **once** as user environment variables so
the task inherits them without any secret touching the repo:

```powershell
# one-time: store creds + config as USER env vars (persist across sessions)
setx AADYON_TOKEN       "<JWT from POST /api/auth/login>"
setx AADYON_BASE        "http://mini-a:8000"
setx JOB_TRACKER_XLSX   "D:\resume\CV\interview-prep\JOB_TRACKER.xlsx"
```

Register the task. Adjust `/st` to ~30 min after your digest time (digest at
07:00 → sync at 07:30) and `-File` to your checkout path:

```powershell
schtasks /Create /TN "AadyonJobTrackerSync" /SC DAILY /ST 07:30 ^
  /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\path\to\aadyon-assist\scripts\sync_job_tracker.ps1" ^
  /RL LIMITED /F
```

Or the PowerShell equivalent (`Register-ScheduledTask` with a
`New-ScheduledTaskTrigger -Daily -At 7:30am`).

Verify:

```powershell
# dry run through the same wrapper the task uses
powershell -File C:\path\to\aadyon-assist\scripts\sync_job_tracker.ps1 -DryRun
schtasks /Run /TN "AadyonJobTrackerSync"     # fire it once now
schtasks /Query /TN "AadyonJobTrackerSync" /V /FO LIST | findstr "Last"
```

> A JWT eventually expires; if the task starts failing auth, mint a fresh token
> (`POST /api/auth/login`) and `setx AADYON_TOKEN …` again, or switch to the
> `$AADYON_EMAIL`/`$AADYON_PASSWORD` path so each run logs in fresh.

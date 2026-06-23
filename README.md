# Aadyon Assist

Personal life-ops tracker. Phase 1 (now): a lean, self-hosted tracker for **deadlines,
debts, bills, subscriptions, and shifts** — one source of truth, built on the same stack
the eventual agentic "life ops" platform will run on (Postgres + pgvector, Docker, Python).

> Track-first, migrate-later. The schema here is the schema that ports to Mini-A.
> Building software is not the priority — the visa filing and income are. This tool just
> gets the mental load out of your head; it doesn't change the numbers.

## Digital Me
The front door (`http://localhost:8000`) is now a **Digital Me** view: a single living
model of you built from the same data. It has two layers:

- **Identity** — name, headline, location, age, visa, and a *life-since-birth* track
  (days alive, life lived %, and a countdown to 30 — the self-imposed Aadyon deadline).
- **Four life dimensions**, each a transparent 0–100 score (every score returns the
  sub-components it was built from, so the number is auditable):
  - **Financial** — card utilization, income coverage, and interest load.
  - **Visa / status** — proximity and blockers on immigration deadlines.
  - **Career** — job-search activity, funnel traction, and income-vs-target gap.
  - **Goal · by 30** — average progress on open goals vs. the share of life-to-30 used.

Backed by three new tables — `profile` (singleton), `applications` (job-search funnel),
`milestones` (life timeline + in-progress goals) — and one endpoint, `GET /api/digital-me`.
The scores are deliberately honest: a near-limit debt load and a job search that hasn't
started read low, by design. The old tracker still lives at `/tracker`.

## Data admin (`/data`)
A no-Swagger web console to **view, add, edit, and delete** rows for every entity
(deadlines, debts, bills, subscriptions, shifts, profile, applications, milestones).
It builds typed forms automatically from the live schema (`GET /api/entities`, which
reads column types from `information_schema`), so it stays in sync with the database
with zero hardcoding. Reachable from the **Data** link in both dashboards.

## Agentic layer — the org (`/agency`)
A Phase-2 agentic layer runs the tracker like a small company. A **CEO** agent takes a
goal, reads the Digital Me snapshot, and **delegates** to four **teams** (Finance,
Immigration, Career, Growth — the dimensions), whose **team leads / employees** analyze
and, for anything with a real-world side effect, file a **proposal that you approve**
(human-in-the-loop). Read-only analysis runs automatically; money/email/destructive
actions never auto-execute.

- **Model routing core** — every agent has a *tier* (`reasoning` / `cheap` / `local`).
  The `model_routes` table maps tiers to a provider+model and is editable in the admin.
  Defaults: `reasoning → openrouter/auto` (OpenRouter picks the best provider/model),
  `cheap → openai/gpt-4o-mini`, `local → ollama/llama3.1`. So one core (OpenRouter)
  fans out to many providers, with local models for private/bulk tasks.
- **Tables** (all editable in the admin): `teams`, `agents` (CEO/lead/employee org chart),
  `tasks` (the queue + proposals), `agent_runs` (audit trail of every step), `model_routes`.
- **Worker** — the `agency` container drains the task queue, so a single "ask the CEO"
  fans out across the org automatically (bounded by `AGENT_MAX_STEPS`).
- **Endpoints** — `GET /api/agency/org`, `GET /api/agency/health`, `POST /api/agency/ask`,
  `GET /api/agency/tasks`, `POST /api/agency/tasks/{id}/run|approve|reject`, `GET /api/agency/runs`.

**To turn it on:** add your OpenRouter key to `.env` as `OPENROUTER_API_KEY=...` (or put it
in `secrets/openrouter_api_key.txt`) and restart. Optional: run **Ollama** on the host for
the `local` tier. Until a key is present, agents route correctly but tasks show **blocked**
with a clear message — nothing crashes.

## Email accounts (`/accounts`)
Connect your mailboxes and let the app turn inbox noise into reviewable to-dos. It reads mail
**read-only** (never deletes or sends), runs each new message through the cheap model to extract
one actionable item — a deadline, bill, or subscription — and queues it in a **review queue**.
Nothing is auto-applied: you Approve (it becomes a real `deadline`/`bill`/`subscription`) or
Dismiss. iCloud and Gmail connect via **IMAP app-password**; Outlook/Microsoft 365 via **Microsoft
Graph device-code**. Stored credentials are **Fernet-encrypted** at rest, and each account keeps a
sync cursor so a daily sync only reads new mail. Syncs run automatically with the morning briefing.

## Morning briefing → phone
The `briefing` service writes `artifacts/briefing-*.md` daily and pushes it to a **self-hosted
ntfy** server, which delivers to your phone over Tailscale. Content stays on the tailnet; only the
iOS background wake is proxied via `ntfy.sh`. Set `NTFY_TOPIC` in `.env` to enable.

## Documentation
- **[SYSTEM.md](SYSTEM.md)** — full system architecture: diagrams, components, data flows, data
  model, security model, deployment, and operations runbook.
- **[TAILSCALE.md](TAILSCALE.md)** — remote-access setup.

## Stack
- **Postgres 16 + pgvector** — relational data now, vector memory ready for later RAG.
- **FastAPI (Python)** — REST API + serves the dashboards.
- **Docker Compose** — six services: `db`, `api`, `briefing`, `agency`, `backup`, `ntfy`.
  DB password and API keys via **Docker secrets**.
- **Vanilla HTML/JS dashboards** — no build step, served by the API; shared CSS/JS in `/static`.
- **Runs on the Mini-A** (Ubuntu, always-on) and reachable over **Tailscale**; identical stack on
  the laptop for dev.

## Layout
```
aadyon-assist/
  code/
    api/            FastAPI app (Dockerfile, requirements.txt)
      app/
        main.py       create_app() factory — wires routers + static mount
        core/         config.py — settings + DB password (Docker secret aware)
        db/           session.py — connection pool + query() helper
        models/       tables.py — Entity registry (tables + writable columns)
        routers/      crud.py (factory), system.py, agency.py, email.py, dashboard.py
        services/     digital_me + dimensions, summary, routing/llm/tools/agency,
                      crypto, email_* (extract/store/imap/graph/ingest), ms_graph, notify
        jobs/         briefing_loop, agency_loop, import_entities (each a worker)
    db/init/        SQL migrations 01..09 (auto-run on first DB boot)
    dashboard/      pages: digital-me, index (tracker), data, agency, accounts + assets/
  documents/        SENSITIVE — immigration PDFs, offers, I-983 (gitignored)
  artifacts/        dashboard exports, drafts (gitignored)
  notes/            handoff brief, decisions log, project log
  data/             local Postgres volume + exports (gitignored)
  docker-compose.yml
  .env.example      copy to .env
```

## Run it
1. Copy env + create the DB secret:
   ```bash
   cp .env.example .env
   mkdir -p secrets
   # pick a strong password:
   printf 'change-me-strong-password' > secrets/db_password.txt
   ```
2. Start:
   ```bash
   docker compose up -d --build
   ```
3. Open the dashboard: http://localhost:8000
   API docs (Swagger): http://localhost:8000/docs

First boot runs `code/db/init/01_schema.sql`, `02_seed.sql`, then `03_digital_me.sql`
automatically. To re-seed from scratch: `docker compose down -v` (wipes the DB volume) then `up` again.

**Already have a running DB?** The init scripts only run on an empty volume, so apply the
Digital Me migration to your live database (idempotent — safe to re-run) and rebuild:
double-click **`migrate.bat`**. It runs `03_digital_me.sql` against the running DB, then
rebuilds the API + briefing with the new endpoint and page.

## Automation
The stack now runs and maintains itself:

- **Auto-start on login** — `start-aadyon.bat` (copied into the Windows Startup folder) waits for the Docker engine, then runs `docker compose up -d`. A copy lives in the repo root.
- **Daily briefing** — the `briefing` service writes `artifacts/briefing-YYYY-MM-DD.md` (and `briefing-latest.md`) once on start and again each day at `BRIEFING_HOUR` (default 07:00, `TZ` from `.env`). On-demand: `GET /api/briefing`. A Cowork scheduled task (`aadyon-morning-briefing`, 7:05 AM daily) surfaces it in chat.
- **Nightly DB backup** — the `backup` service runs `pg_dump` into `data/exports/aadyon_YYYY-MM-DD.sql` daily, keeping the last 14 days.
- **Stays up unattended** — every service uses `restart: unless-stopped`, and `db` + `api` have healthchecks.

Tunables in `.env`: `BRIEFING_HOUR`, `TZ`, `API_PORT`.

### Importing entities from your data
The app can ingest entities you (or Claude) extract from emails, statements, or the `documents/` folder:

1. Write the items to `artifacts/inbox.json` — a list of `{"table": "...", "data": {...}}` (tables: deadlines, debts, bills, subscriptions, shifts; only whitelisted columns are used).
2. Double-click `import.bat`. It rebuilds the API (cached/fast), runs the importer in the container, de-duplicates by natural key (so re-running is safe), and archives the processed file + a result log to `artifacts/imported/`.

`bills`/`subscriptions`/`debts` require an `amount`/`balance`; items without a known amount are better added as `deadlines` (only `title` + `due_date` are required).

## Migrate to Mini-A later
The schema in `code/db/init/01_schema.sql` is the contract. On Mini-A:
`pg_dump`/`pg_restore` the data, point the same compose file at the NVMe volume, and add
the reasoning/RAG services. Nothing in Phase 1 needs to be rewritten.

## Security notes
- `documents/` and `.env` and `secrets/` are gitignored — keep them that way.
- Encrypt `documents/` at rest (immigration PDFs, I-983) — Docker does not do this for you.
- Action layer is human-in-the-loop by design: no autonomous money or email actions.

# Aadyon Assist

[![CI](https://github.com/chiranjeevigundu/aadyon-assist/actions/workflows/ci.yml/badge.svg)](https://github.com/chiranjeevigundu/aadyon-assist/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A **self-hosted, multi-user personal life-ops platform** with a conversational AI assistant:
one Postgres source of truth for your deadlines, debts, bills, subscriptions, work and goals —
an agentic "org" that analyzes it, an email/document-ingest pipeline that turns inbox noise and PDFs into
reviewable to-dos, and an iPhone app with an Aadyon Assist chat that can act on your data.

Personal life-ops tracker. Phase 1 (now): a lean, self-hosted tracker for **deadlines,
debts, bills, subscriptions, and shifts** — one source of truth, built on the same stack
the eventual agentic "life ops" platform will run on (Postgres + pgvector, Docker, Python).

> Track-first, migrate-later. The schema here is the schema that ports to your always-on
> server. The tool gets the mental load out of your head; it doesn't change the numbers.

## Aadyon Assist (multi-user)
The app is now **multi-user** with a conversational assistant. Sign up / log in from the
iPhone app (`mobile/`); every account is isolated at the database by Postgres Row-Level
Security. The **Assistant** tab is a chat that reads your Digital Me and can **directly update
your own records** ("add a deadline to renew my passport next month", "mark the Netflix
subscription inactive"). Anything with a real-world side effect (money, email, filings) comes
back as a **proposal you approve** — it never auto-executes. API auth is a JWT bearer token
(`POST /api/auth/login`); `/api/health` and `/api/auth/*` are the only public routes.

> Web dashboards (`/`, `/tracker`, …) also require login. They share the same JWT auth layer 
> and store your session transparently.

## Digital Me
The front door (`http://localhost:8000`) is now a **Digital Me** view: a single living
model of you built from the same data. It has two layers:

- **Identity** — name, headline, location, age, visa, and a *life-since-birth* track
  (days alive, life lived %, and a countdown to a personal goal age you set).
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

## Email, Documents, and Connectors (`/accounts`)
Connect your mailboxes, cloud drives, calendar, and banking accounts to let the app turn inbox noise, statements, and PDFs into reviewable to-dos. 
- **Email**: Reads mail **read-only**, runs each new message through the model to extract actionable items (deadlines, bills) and queues it. iCloud/Gmail via **IMAP app-password**; Outlook via **Microsoft Graph device-code**.
- **Documents (P3)**: Upload PDFs and receipts. Extracted text and OpenAI Vision parses the content to queue extracted items. Stored in S3 (P4).
- **Calendar & Drive (P2)**: Connects to Google Calendar and Google Drive to sync upcoming events and documents into the ecosystem.
- **Banking (P2)**: Syncs transactions for financial score analysis and bill verification.

Nothing is auto-applied: you Approve (it becomes a real `deadline`/`bill`/`subscription`) or Dismiss. Stored credentials are **Fernet-encrypted** at rest, and each account keeps a sync cursor. Syncs run automatically with the morning briefing or background worker.

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
- **FastAPI (Python)** — REST API + serves the dashboards; **LiteLLM** for model access; **boto3** for S3 cloud storage; **yoyo-migrations** for plain-SQL schema migrations.
- **Docker Compose** — services: `db`, `migrate`, `api`, `briefing`, `agency`, `backup`, `ntfy`.
  DB password and API keys via **Docker secrets**. Tasks via **just** (`just --list`).
- **Vanilla HTML/JS dashboards** — no build step, served by the API; shared CSS/JS in `/static`.
- **Self-hosted** on any always-on Linux box, reachable over **Tailscale**; identical stack on
  a dev machine.

## Layout
```
aadyon-assist/
  code/
    api/            FastAPI app (Dockerfile, requirements.txt)
      app/
        main.py       create_app() factory — wires routers + static mount
        core/         config.py — settings + DB password (Docker secret aware)
        db/           session.py — connection pool + query() helper (RLS-scoped)
        models/       tables.py — Entity registry (tables + writable columns)
        routers/      crud.py (factory), system.py, auth.py, agency.py, email.py,
                      assistant.py, dashboard.py
        services/     digital_me + dimensions, summary, routing/llm/tools/agency, assistant,
                      auth, crypto, email_* (extract/store/imap/graph/ingest), ms_graph, notify
        jobs/         briefing_loop, agency_loop, import_entities (each a worker)
    db/migrations/  plain-SQL migrations (applied by yoyo; `just new-migration <name>`)
    db/seed/        your personal seed SQL (gitignored; `just seed`)
    dashboard/      pages: digital-me, index (tracker), data, agency, accounts + assets/
  mobile/           Expo / React Native iPhone app (login + assistant chat)
  artifacts/        dashboard exports, drafts (gitignored)
  data/             local Postgres volume + exports (gitignored)
  justfile          task runner (up/down/test/lint/migrate/seed/backup/…)
  docker-compose.yml
  .env.example      copy to .env
```

## Run it

Prereqs: Docker (with Compose) and [`just`](https://github.com/casey/just)
(`brew install just` · `winget install Casey.Just` · apt/dnf).

1. Copy env + create the secrets:
   ```bash
   cp .env.example .env
   mkdir -p secrets
   # pick a strong DB password:
   printf 'change-me-strong-password' > secrets/db_password.txt
   # signing key for login tokens (multi-user auth):
   python -c "import secrets; print(secrets.token_urlsafe(48))" > secrets/jwt_secret.txt
   ```
2. Start (migrations apply automatically via the one-shot `migrate` service):
   ```bash
   just up          # = docker compose up -d --build
   ```
3. Open the dashboard: http://localhost:8000
   API docs (Swagger): http://localhost:8000/docs

`just --list` shows every recipe (logs, test, lint, migrate, seed, backup, restore, mobile…).
To re-init from scratch: `docker compose down -v` (wipes the DB volume) then `just up`.

**Upgrading a database created before yoyo-migrations?** Baseline it once:
`just backup-now && just migrate-baseline` (records the already-applied schema in the ledger
without re-running it); from then on `just migrate` applies only new files.

## Automation
The stack runs and maintains itself:

- **Daily briefing** — the `briefing` service (APScheduler cron) writes `artifacts/briefing-YYYY-MM-DD.md` (and `briefing-latest.md`) once on start and again each day at `BRIEFING_HOUR` (default 07:00, `TZ` from `.env`). On-demand: `GET /api/briefing`.
- **Nightly DB backup** — the `backup` service (postgres-backup-local) writes gzipped dumps under `data/exports/daily/`, keeping 14 days. On-demand: `just backup-now`; restore: `just restore <file>`.
- **Stays up unattended** — long-running services use `restart: unless-stopped`, and `db` + `api` have healthchecks.

Tunables in `.env`: `BRIEFING_HOUR`, `TZ`, `API_PORT`.

### Importing entities from your data
The app can ingest entities you (or an AI assistant) extract from emails, statements, or documents:

1. Write the items to `artifacts/inbox.json` — a list of `{"table": "...", "data": {...}}` (tables: deadlines, debts, bills, subscriptions, shifts; only whitelisted columns are used).
2. Run `just import`. It runs the importer in the container, de-duplicates by natural key (so re-running is safe), and archives the processed file + a result log to `artifacts/imported/`.

`bills`/`subscriptions`/`debts` require an `amount`/`balance`; items without a known amount are better added as `deadlines` (only `title` + `due_date` are required).

## Moving between machines
The schema in `code/db/migrations/` is the contract. `pg_dump`/`pg_restore` the data, point the
same compose file at the new volume, run `just migrate-baseline` once, and everything ports as-is.

## Contributing & security
- [CONTRIBUTING.md](CONTRIBUTING.md) — dev setup, tests, PR flow. [SECURITY.md](SECURITY.md) — reporting + the security model.
- `documents/`, `.env`, `secrets/`, and `code/db/seed/` are gitignored — keep them that way; gitleaks guards CI and pre-commit.
- Action layer is human-in-the-loop by design: no autonomous money or email actions.

## License
MIT — see [LICENSE](LICENSE).

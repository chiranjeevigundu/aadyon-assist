# Aadyon Assist

[![CI](https://github.com/chiranjeevigundu/aadyon-assist/actions/workflows/ci.yml/badge.svg)](https://github.com/chiranjeevigundu/aadyon-assist/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A **self-hosted, multi-user personal finance tracker** with a conversational AI assistant.
One Postgres source of truth for your **net worth** — assets, debts, bills, subscriptions,
income, and transactions — plus an email/document-ingest pipeline that turns statements and
inbox noise into reviewable entries, and an assistant that can read your finances and act on
them (with your approval for anything that touches the real world).

> Track-first. The tool gets the numbers out of your head and into one place; it never moves
> money on its own. Anyone can self-host it — nothing here is tied to a specific person.

## Net worth (the front door)

`http://localhost:8000` opens the **Net Worth** view: **assets − liabilities**, at a glance.

- **Assets** (holdings) — cash, investments, retirement, property, vehicles, crypto — in the
  `assets` table; **liabilities** are your `debts`.
- **Net worth = total assets − total liabilities**, with a breakdown by asset type and a
  **trend** you build by snapshotting over time (`net_worth_snapshots`, one row per day).
- Endpoints: `GET /api/networth` (totals + breakdown + history), `POST /api/networth/snapshot`.

## Tracker (`/tracker`)

The cash-flow view: **debts** with payoff order and interest math, **bills**, **subscriptions**,
upcoming **deadlines**, and **income** (jobs + shifts).

## Assistant (`/assistant`)

A chat that reads your finances and can **directly update your own records** ("add my brokerage
account worth $25k", "mark the Netflix subscription inactive", "log a $3,000 card balance at
19.9% APR"). It always pulls real numbers via a net-worth snapshot rather than guessing.

Anything with a real-world **external** side effect — moving money, sending an email, paying a
bill — comes back as a **proposal you approve** (the `proposals` table); it never auto-executes.
The assistant can also read a **document you upload** to pull figures from a statement.

## Data admin (`/data`)

A no-Swagger web console to **view, add, edit, and delete** rows for every entity (assets, debts,
bills, subscriptions, income, bank accounts/transactions, documents, deadlines, profile). It
builds typed forms automatically from the live schema (`GET /api/entities`, which reads column
types from `information_schema`), so it stays in sync with the database with zero hardcoding.

## Email & document ingestion (`/accounts`)

Feed financial data in from your existing sources — nothing is auto-applied; you **Approve**
(it becomes a real `bank_transaction` / `bill` / entry) or **Dismiss**.

- **Email** — reads mail **read-only**, runs each new message through the model to extract
  financial items (transactions, bills, statements) into a review queue. iCloud/Gmail via
  **IMAP app-password**; Outlook via **Microsoft Graph device-code**; Gmail also via OAuth.
- **Documents** — upload bank/brokerage statements and receipts; text + vision extraction
  queues the figures. Stored in S3-compatible object storage (see
  [docs/cloud-storage.md](docs/cloud-storage.md)).

Stored credentials are **Fernet-encrypted** at rest, and each account keeps a sync cursor.
Syncs run with the morning briefing or on demand.

## Assistant model routing

The assistant routes to a model by *tier* (`reasoning` / `cheap` / `local`), configured in
`.env` — no DB table to manage. Defaults: `reasoning → openrouter/auto` (OpenRouter picks the
best provider/model), `cheap → openai/gpt-4o-mini`, `local → ollama/llama3.1`.

**To enable it:** add your OpenRouter key to `.env` as `OPENROUTER_API_KEY=...` (or
`secrets/openrouter_api_key.txt`) and restart. Optional: run **Ollama** on the host for the
`local` tier. Until a key is present, the chat replies with a clear message — nothing crashes.

## Morning briefing → phone

The `briefing` service writes `artifacts/briefing-*.md` daily (upcoming bills, debt/interest
summary, pending proposals) and pushes it to a **self-hosted ntfy** server, delivered to your
phone over Tailscale. Content stays on the tailnet; only the iOS background wake is proxied via
`ntfy.sh`. Set `NTFY_TOPIC` in `.env` to enable.

## Documentation

- **[docs/architecture.md](docs/architecture.md)** — system + service diagrams.
- **[SYSTEM.md](docs/SYSTEM.md)** — full architecture: components, data flows, data model, security,
  deployment, and operations runbook.
- **[docs/cloud-storage.md](docs/cloud-storage.md)** — object storage: real AWS ⇄ local emulator.
- **[docs/CLOUD.md](docs/CLOUD.md)** — moving to a managed cloud platform.
- **[TAILSCALE.md](docs/TAILSCALE.md)** — remote-access setup.

## Stack

- **Postgres 16 + pgvector** — relational data now, vector memory ready for later RAG.
- **FastAPI (Python)** — REST API + serves the dashboards; **LiteLLM** for model access;
  **boto3** for S3-compatible storage; **yoyo-migrations** for plain-SQL schema migrations.
- **Docker Compose** — services: `db`, `migrate`, `api`, `briefing`, `backup`, `ntfy`.
  DB password and API keys via **Docker secrets**. Tasks via **just** (`just --list`).
- **Vanilla HTML/JS dashboards** — no build step, served by the API; shared CSS/JS in `/static`,
  installable as a PWA.
- **Multi-user** — JWT bearer auth (`POST /api/auth/login`); every account is isolated at the
  database by Postgres **Row-Level Security**. `/api/health` and `/api/auth/*` are the only
  public routes.
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
        routers/      crud.py (factory), system.py, auth.py, networth.py, bank.py,
                      email.py, documents.py, assistant.py, dashboard.py
        services/     networth, summary, routing/llm/tools, assistant, auth, crypto,
                      storage, bank_*, email_* (extract/store/imap/graph/ingest),
                      document_*, ms_graph, google_oauth, mailer, notify
        jobs/         briefing_loop, backup_sync, import_entities (each a worker)
    db/migrations/  plain-SQL migrations (applied by yoyo; `just new-migration <name>`)
    db/init/        your personal seed SQL (gitignored)
    dashboard/      pages: networth (home), index (tracker), data, accounts + assets/
  artifacts/        briefings, uploads (gitignored)
  data/             local Postgres volume + exports (gitignored)
  justfile          task runner (up/down/test/lint/migrate/backup/…)
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
3. Open the dashboard: http://localhost:8000 · API docs (Swagger): http://localhost:8000/docs

`just --list` shows every recipe (logs, test, lint, migrate, backup, restore…).
To re-init from scratch: `docker compose down -v` (wipes the DB volume) then `just up`.

**Upgrading a database created before yoyo-migrations?** Baseline it once:
`just backup-now && just migrate-baseline` (records the already-applied schema in the ledger
without re-running it); from then on `just migrate` applies only new files.

## Running on Kubernetes (optional)

Compose is the simplest way to run this. If you'd rather exercise the Kubernetes path —
a realistic dry-run of deploying to EKS, using a local k3s cluster — see
[deploy/k8s/README.md](deploy/k8s/README.md):

```bash
./deploy/k8s/deploy.sh
```

## Automation

The stack runs and maintains itself:

- **Daily briefing** — the `briefing` service (APScheduler cron) writes
  `artifacts/briefing-YYYY-MM-DD.md` (and `briefing-latest.md`) once on start and again each day
  at `BRIEFING_HOUR` (default 07:00, `TZ` from `.env`). On-demand: `GET /api/briefing`.
- **Nightly DB backup** — the `backup` service (postgres-backup-local) writes gzipped dumps under
  `data/exports/daily/`, keeping 14 days. On-demand: `just backup-now`; restore: `just restore <file>`.
- **Stays up unattended** — long-running services use `restart: unless-stopped`, and `db` + `api`
  have healthchecks.

Tunables in `.env`: `BRIEFING_HOUR`, `TZ`, `API_PORT`.

### Importing entries from your data

The app can ingest entities you (or an AI assistant) extract from statements or documents:

1. Write the items to `artifacts/inbox.json` — a list of `{"table": "...", "data": {...}}`
   (tables: assets, debts, bills, subscriptions, deadlines; only whitelisted columns are used).
2. Run `just import`. It de-duplicates by natural key (so re-running is safe) and archives the
   processed file + a result log to `artifacts/imported/`.

## Development vs. production environments

`docker-compose.yml` is the production definition — it's what runs on the always-on server.
`docker-compose.dev.yml` is an additive overlay for local iteration (hot-reload API via bind
mount + `--reload`, Postgres port published to the host for psql/GUI access, skips `backup`/`ntfy`
since dev data is throwaway). Both read from `.env` + `secrets/*.txt` on whichever machine you're
on — those are gitignored per-machine state.

```bash
just bootstrap-dev  && just up-dev    # local dev: hot reload, exposed DB port, no backup/ntfy
just bootstrap-prod && just up-prod   # production: matches the deployed server exactly
```

## Moving between machines

The schema in `code/db/migrations/` is the contract. `pg_dump`/`pg_restore` the data, point the
same compose file at the new volume, run `just migrate-baseline` once, and everything ports as-is.

## Contributing & security

- [CONTRIBUTING.md](CONTRIBUTING.md) — dev setup, tests, PR flow. [SECURITY.md](SECURITY.md) —
  reporting + the security model.
- `.env`, `secrets/`, and `code/db/init/` are gitignored — keep them that way; gitleaks guards
  CI and pre-commit. Never commit personal or financial data.
- The action layer is human-in-the-loop by design: no autonomous money or email actions.

## License

MIT — see [LICENSE](LICENSE).

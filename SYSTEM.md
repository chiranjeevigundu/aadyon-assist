# Aadyon Assist — System Architecture

A self-hosted, single-user **life-ops platform**. It keeps one auditable source of truth for
your deadlines, debts, bills, subscriptions, work and income, immigration status, and goals —
and layers three capabilities on top of it: a **Digital Me** scoring model, an **agentic org**
that reasons over that data, and an **email ingest** pipeline that turns inbox noise into
reviewable to-dos. It runs on a stack (Postgres + Docker + Python) designed to move, unchanged,
between a laptop and the always-on "Mini-A" server.

> Design intent: the tool reflects your numbers; it does not move money or send mail on its own.
> Anything with a real-world side effect is gated behind explicit human approval.

---

## 1. Design principles

- **One source of truth.** Every view (tracker, Digital Me, briefing, agents) reads the same
  Postgres database. No metric is computed in two places.
- **Transparent over clever.** Scores return the sub-components they were built from; nothing is
  a black box you can't audit.
- **Read-by-default, write-on-approval.** Email sync and agents only *read* and *propose*.
  Payments, emails, filings, and destructive actions never auto-execute.
- **Private by construction.** No app-level auth, so the system is kept on a private Tailscale
  network rather than the public internet. Secrets live in Docker secrets; email credentials are
  encrypted at rest; personal data never enters git.
- **Port-later, not rewrite-later.** The schema and containers are identical on laptop and server.

---

## 2. Context diagram

```mermaid
flowchart TD
  you([You]) -->|browser, over Tailscale| dash["Dashboards<br/>Digital Me · Tracker · Data · Agency · Accounts"]
  you -->|morning push| phone([iPhone / ntfy app])

  subgraph minia["Mini-A — Ubuntu, always-on (Docker Compose)"]
    dash --> api["api (FastAPI)"]
    api --> db[("Postgres 16 + pgvector")]
    briefing["briefing worker"] --> db
    agency["agency worker"] --> db
    backup["backup (pg_dump)"] --> db
    ntfy["ntfy push server"]
    briefing --> ntfy
  end

  ntfy -->|Tailscale| phone
  api -->|read mail| mail[/"IMAP · Microsoft Graph"/]
  agency -->|routed inference| models[/"OpenRouter (cloud)<br/>Ollama (local)"/]
  api -->|routed inference| models

  laptop["Laptop (dev)"] -->|git push| gh[("GitHub repo + Actions")]
  gh -->|git pull + compose up --build| minia
```

The user reaches everything through a browser over Tailscale and receives a daily push on their
phone. The whole application is a Docker Compose stack on the Mini-A. The only outbound network
calls are to mail providers (read-only) and model providers (inference).

---

## 3. Service topology

The stack is **six containers** in `docker-compose.yml`, all `restart: unless-stopped`:

| Service | Image / build | Role | Ports |
|---|---|---|---|
| **db** | `pgvector/pgvector:pg16` | Postgres + pgvector. Auto-loads `code/db/init/*.sql` on first boot. `pg_isready` healthcheck. | internal |
| **api** | `code/api/Dockerfile` | FastAPI: REST API + serves dashboards. HTTP healthcheck on `/api/health`. | `${API_PORT:-8000}:8000` (Mini-A: **8800**) |
| **briefing** | same image | Runs `app.jobs.briefing_loop`: writes `artifacts/briefing-*.md` and pushes to ntfy, daily at `BRIEFING_HOUR`. | — |
| **agency** | same image | Runs `app.jobs.agency_loop`: drains the agent task queue (CEO → teams). | — |
| **backup** | `pgvector/pgvector:pg16` | Shell loop: nightly `pg_dump` into `data/exports/`, 14-day retention. | — |
| **ntfy** | `binwiederhier/ntfy` | Self-hosted push server. Private to the tailnet; `ntfy.sh` upstream only proxies the iOS background wake. | `${NTFY_PORT:-8090}:80` |

The DB password is supplied to `db`, `api`, `briefing`, `agency`, and `backup` via a **Docker
secret** (`secrets/db_password.txt`), never an environment variable. `api` and `agency` get
`host.docker.internal` mapped so they can reach a local **Ollama** on the host.

---

## 4. Application structure

The FastAPI app (`code/api/app/`) is layered, with absolute `app.*` imports:

```
app/
  main.py              create_app() — wires routers + mounts /static
  core/config.py       Settings: DB, secrets, artifacts, briefing hour, TZ,
                       model routing, ntfy, email (Fernet key, lookback), MS/Google OAuth
  db/session.py        psycopg2 connection pool + query() helper (RealDictCursor)
  models/tables.py     Entity registry — every CRUD table + its writable-column whitelist
  routers/
    system.py          /api/health, /api/summary, /api/digital-me, /api/entities, /api/briefing
    crud.py            generic CRUD router factory (one router per Entity)
    agency.py          /api/agency/* — org, health, ask, tasks, runs, approvals
    email.py           /api/email/* — connect, sync, MS device-code, extractions review
    dashboard.py       serves /, /tracker, /data, /agency, /accounts
  services/
    common.py          numeric helpers (f, clamp, rnd, band) + constants
    dimensions.py      life + income + financial/visa/career/goal read-models
    digital_me.py      orchestrator — assembles the dimensions into one payload
    summary.py         tracker read-model aggregation
    schema.py          column metadata (types, required, FKs) for the data admin
    briefing.py        builds the daily briefing markdown
    notify.py          push_briefing() → self-hosted ntfy
    routing.py         resolve(tier) → {provider, model, temperature} from model_routes
    llm.py             chat() over OpenRouter (tool-calling) and Ollama (local); health()
    tools.py           agent tools: get_snapshot (read), delegate, propose_action (approval-gated)
    agency.py          org_tree(), ask_ceo(), run_task() — the bounded tool-calling engine
    crypto.py          Fernet encrypt/decrypt for stored email secrets
    email_extract.py   LLM extraction prompt + output normalization (coerce_due, normalize)
    email_store.py     dedup, queue pending extractions, apply approved ones
    email_imap.py      IMAP reading + iCloud/Gmail sync path
    email_graph.py     Microsoft Graph (Outlook/365) sync path
    email_ingest.py    entrypoint: dispatch per-account sync, sync_all, re-export helpers
    ms_graph.py        Graph device-code OAuth + mail fetch
  jobs/
    briefing_loop.py   briefing worker (own container)
    agency_loop.py     agent queue worker (own container)
    import_entities.py inbox importer (run via import.bat)
```

**Generic CRUD.** `models/tables.py` declares each table as an `Entity(table, columns, order_by)`.
`routers/crud.py` turns each `Entity` into a full REST resource, with writes restricted to the
column whitelist (`id`, `created_at`, `updated_at` are DB-managed and never writable). The data
admin UI builds typed forms from `/api/entities`, which reads column types, nullability, and
foreign keys live from `information_schema` — so the admin stays in sync with the DB with zero
hardcoding.

The dashboards are vanilla HTML/JS, no build step. They share `dashboard/assets/base.css` (theme
tokens, reset, and common components) and `dashboard/assets/base.js` (helpers `esc`/`money`/
`money2`/`num`/`$`, plus `renderNav()` which renders the top nav consistently on every page).

---

## 5. Core data flows

### 5.1 Digital Me

`GET /api/digital-me` returns, in one response: the `profile` singleton, a *life-since-birth*
track (days alive, life-lived %, countdown to 30), projected income, and four **transparent
0–100 dimension scores** — Financial, Visa/Status, Career, Goal-by-30 — each returning the
sub-components it was computed from. The orchestrator (`digital_me.py`) composes read-models from
`dimensions.py`; shared math lives in `common.py`. Scores are deliberately honest: a near-limit
debt load or a job search that hasn't started reads low.

### 5.2 Tracker

`GET /api/summary` aggregates everything the Phase-1 tracker (`/tracker`) needs in one call:
deadlines, the `debt_summary` view, debt totals, active bills, active subscriptions, and recent
shifts.

### 5.3 Email ingest pipeline

```mermaid
sequenceDiagram
  participant U as You (Accounts page)
  participant API as api
  participant P as Provider (IMAP / Graph)
  participant LLM as cheap model
  participant DB as Postgres

  U->>API: connect (app-password / device-code)
  API->>P: verify credentials
  API->>DB: store secret (Fernet-encrypted), status=connected
  Note over API,DB: daily — briefing worker calls sync_all()
  API->>P: fetch new mail (UID high-water / last_sync cursor)
  loop each new message
    API->>LLM: extract one actionable item (strict JSON)
    LLM-->>API: {kind, title, due_date, amount, summary} or none
    API->>DB: queue email_extractions (status=pending), deduped
  end
  U->>API: review queue → Approve / Dismiss
  API->>DB: approved → INSERT into deadlines / bills / subscriptions
```

Read-only over IMAP and Graph — nothing is ever deleted or sent. Each account tracks a cursor
(IMAP UID high-water + UIDVALIDITY; Graph `last_sync`) so a sync only spends model calls on new
mail. Stored secrets (IMAP app-passwords, Graph refresh tokens) are **Fernet-encrypted**.
Extractions are **never auto-applied** — they wait in a review queue. The extraction prompt is
tuned to ignore marketing, receipts, shipping, OTP/login alerts, and automated CI/notification
mail. Providers: iCloud and Gmail via IMAP app-password; Outlook/Microsoft 365 via Graph
device-code OAuth.

### 5.4 Agentic org

```mermaid
flowchart LR
  ask["POST /api/agency/ask<br/>(give the CEO a goal)"] --> q[("tasks: queued")]
  worker["agency worker<br/>agency_loop"] --> q
  worker --> run["run_task() — bounded tool loop<br/>(AGENT_MAX_STEPS)"]
  run --> route["routing.resolve(tier)"]
  route --> llm["llm.chat() → OpenRouter / Ollama"]
  run -->|get_snapshot| snap["Digital Me data"]
  run -->|delegate| q
  run -->|propose_action| prop[("tasks: awaiting_approval")]
  run --> audit[("agent_runs: every step")]
  prop --> human{"You: approve / reject"}
```

A **CEO** agent takes a goal, calls `get_snapshot` for real data, and **delegates** sub-tasks to
four **teams** (Finance, Immigration, Career, Growth — the four dimensions). Team leads and
employees analyze and, for anything with a side effect, call `propose_action`, which queues a
proposal in `awaiting_approval` — it does **not** execute. Every model turn and tool call is
logged to `agent_runs`. The loop is bounded by `AGENT_MAX_STEPS`. Tool access is by org level:
CEO gets `get_snapshot` + `delegate`; leads/employees get `get_snapshot` + `propose_action`.

**Model routing.** Each agent has a *tier* (`reasoning` / `cheap` / `local`). `routing.resolve()`
maps a tier to a concrete provider+model from the `model_routes` table (editable in the admin),
falling back to `config.default_routes`. Defaults: `reasoning → openrouter/auto`,
`cheap → openai/gpt-4o-mini`, `local → ollama/llama3.1`. One core (OpenRouter) fans out to many
cloud providers; Ollama serves the local tier. With no key present, agents route correctly but
tasks land in `blocked` with a clear message — nothing crashes.

### 5.5 Daily briefing & push

The `briefing` worker calls `build_briefing()` against the live DB, writes
`artifacts/briefing-YYYY-MM-DD.md` (+ `briefing-latest.md`), and `push_briefing()` POSTs it to the
self-hosted **ntfy** topic, which delivers to the phone over Tailscale. Content stays on the
tailnet; only the iOS background wake is proxied via `ntfy.sh` upstream. The same `build_briefing()`
backs `GET /api/briefing`.

---

## 6. Data model

Postgres 16 with the `pgvector` extension (vector columns reserved for future RAG memory).
Migrations live in `code/db/init/` and run **in filename order on first boot only**:

`01_schema` · `02_seed` (personal, gitignored) · `03_digital_me` · `04_jobs_schedule` ·
`05_debts_emi` · `06_agency` · `07_email_accounts` · `08_email_ingest` · `09_email_uid` ·
`99_seed_local` (gitignored).

Every table has DB-managed `id` (UUID), `created_at`, and `updated_at`.

**Life-ops core**

| Table | Purpose | Notable columns |
|---|---|---|
| `deadlines` | Dated to-dos (visa, payments, renewals) | title, category, due_date, status, priority, blocked_on |
| `debts` | Cards + installment/EMI debts | name, kind, balance, apr, min_payment, credit_limit, due_date, installment_amount, term_months, installments_paid, priority_rank |
| `bills` | Recurring bills | name, amount, frequency, due_day, autopay, category, active |
| `subscriptions` | Recurring subscriptions | name, amount, billing_cycle, renews_on, category, active |
| `shifts` | Individual work shifts | employer, role, shift_date, start/end_time, hours, hourly_rate, est_pay, status |
| `debt_summary` | **View**: per-debt utilization + interest | (derived from `debts`) |

**Digital Me**

| Table | Purpose | Notable columns |
|---|---|---|
| `profile` | Singleton identity + targets | full_name, birthdate, visa_type, visa_status, work_auth_until, target_role, target_salary, current_income, goal_title, goal_target_date, life_expectancy_years |
| `applications` | Job-search funnel | company, role, status, salary_min/max, work_type, source, applied_date |
| `milestones` | Life timeline + in-progress goals | title, category, milestone_date, achieved, progress_pct |

**Work & income**

| Table | Purpose | Notable columns |
|---|---|---|
| `jobs` | Part-time / full-time jobs | employer, role, kind, status, hourly_rate, annual_salary, remittance_pct, start/end_date |
| `work_schedule` | Weekly hours per job | **job_id → jobs**, day_of_week, start/end_time, hours, active |

**Email**

| Table | Purpose | Notable columns |
|---|---|---|
| `email_accounts` | Mailbox registry + connection state | email, provider, auth_type, imap_host/port, status, **secret_enc** (Fernet), last_sync, last_uid, uid_validity, last_error |
| `email_extractions` | Review queue of extracted items | **account_id → email_accounts**, message_uid, message_date, sender, subject, kind, payload (JSON), summary, status (pending/approved/dismissed) |

**Agentic org**

| Table | Purpose | Notable columns |
|---|---|---|
| `teams` | The four teams | name, dimension, mission, active |
| `agents` | CEO/lead/employee org chart | name, title, agent_type, **team_id → teams**, **reports_to → agents**, model_tier, model_id, system_prompt, autonomy |
| `tasks` | Queue + proposals | title, description, kind (goal/task/proposal), **team_id**, **agent_id**, **parent_id**, status, requires_approval, result, error, model_used |
| `model_routes` | Tier → provider+model map | tier, provider, model_id, temperature, active |
| `agent_runs` | Per-step audit trail | **task_id**, **agent_id**, step, provider, model, role, tool_name, content, tokens |

---

## 7. API reference

**Pages** — `GET /` (Digital Me), `/tracker`, `/data`, `/agency`, `/accounts`, `/static/*`.

**System**
- `GET /api/health` — DB liveness (`ok` / `degraded`).
- `GET /api/summary` — full tracker payload in one response.
- `GET /api/digital-me` — identity + life track + four dimension scores.
- `GET /api/entities` — per-entity column metadata (types, required, FKs) from `information_schema`.
- `GET /api/briefing` — the current briefing markdown.

**CRUD** (generated per entity) — `GET/POST /api/{entity}`, `GET/PATCH/DELETE /api/{entity}/{id}`.

**Agency**
- `GET /api/agency/org` · `GET /api/agency/health` (key set? Ollama reachable? routes)
- `POST /api/agency/ask` (give the CEO a goal) · `GET /api/agency/tasks` · `GET /api/agency/runs`
- `POST /api/agency/tasks/{id}/run|approve|reject`

**Email**
- `POST /api/email/{account_id}/connect` (IMAP app-password) · `POST .../disconnect`
- `POST /api/email/{account_id}/ms/start` · `POST .../ms/complete` (Graph device-code)
- `POST /api/email/{account_id}/sync`
- `GET /api/email/extractions?status=` · `POST /api/email/extractions/{id}/approve|dismiss`

---

## 8. Security model

- **No application auth → network isolation.** The API is unauthenticated by design, so it is only
  ever reachable on the private **Tailscale** tailnet (Mini-A at `100.124.146.89:8800`). Do **not**
  expose it publicly and do **not** run `tailscale funnel`.
- **Secrets via Docker secrets.** `db_password`, `openrouter_api_key`, and the email Fernet key
  (`email_key`) are mounted from `secrets/` (preferred) with env-var fallback for local dev. Config
  reads secret files first, env second.
- **Email credentials encrypted at rest.** IMAP app-passwords and Graph refresh tokens are stored
  in `email_accounts.secret_enc`, encrypted with Fernet (`crypto.py`). Plaintext is held only
  transiently in memory during a sync.
- **Read-only external access.** Mail is read over IMAP/Graph with read-only scopes; agents and
  sync never delete or send. All side-effecting actions are human-approved.
- **Personal data never in git.** Seed data (`02_seed.sql`, `99_seed_local.sql`), DB dumps
  (`data/exports/`), `artifacts/`, and source documents are `.gitignore`d. The repo is private.

---

## 9. Deployment & operations

### 9.1 Topology

- **Mini-A (production)** — Ubuntu server, always on. Runs the full Compose stack; API published on
  port **8800**; reachable from laptop and phone over Tailscale. This is where the real data lives.
- **Laptop (development)** — same stack via `run.bat`/`start-aadyon.bat`; API on `localhost:8000`.

### 9.2 Deploy a change

```powershell
# laptop — clean-history single-commit force-push (respects .gitignore)
.\commit-and-push.bat
```
```bash
# Mini-A — history is rewritten upstream, so reset rather than pull-merge
cd ~/aadyon-assist && git fetch origin && git reset --hard origin/main \
  && docker compose up -d --build api briefing agency
```

`.github/workflows/ci.yml` runs lint + a personal-data guard + a smoke test on push;
`publish.yml` publishes the image to GHCR.

### 9.3 Schema migrations

The `code/db/init/*.sql` scripts run **only on first boot of an empty volume**. For an existing
database (like the Mini-A), apply a new migration manually:

```bash
docker compose exec -T db psql -U aadyon -d aadyon_assist < code/db/init/NN_name.sql
```

### 9.4 Backups & restore

The `backup` container writes `data/exports/aadyon_YYYY-MM-DD.sql` nightly (14-day retention).
Restore into a fresh stack:

```bash
docker compose exec -T db psql -U aadyon -d aadyon_assist < data/exports/aadyon_YYYY-MM-DD.sql
```

### 9.5 Routine actions

- **Connect a mailbox** — Accounts page → add account → Connect (IMAP app-password) or Connect
  (Microsoft device-code).
- **Sync email** — automatic each morning via the briefing worker, or per-account on the Accounts
  page; review the queue and Approve/Dismiss.
- **Run the org** — Agency page → "Ask the CEO" a goal; the worker fans it out; approve any
  proposals.
- **Turn agents on** — put `OPENROUTER_API_KEY` in `.env` (or `secrets/openrouter_api_key.txt`)
  and restart; optionally run Ollama on the host for the `local` tier.

---

## 10. Configuration reference

Set in `.env` (see `.env.example`); secrets preferred via files in `secrets/`.

| Variable | Purpose | Default |
|---|---|---|
| `API_PORT` | Host port for the API | 8000 (Mini-A 8800) |
| `TZ` / `BRIEFING_HOUR` | Timezone / daily briefing hour | `America/Phoenix` / 7 |
| `OPENROUTER_API_KEY` | Cloud model access (or `secrets/openrouter_api_key.txt`) | — |
| `OPENROUTER_BASE_URL` | OpenRouter endpoint | `https://openrouter.ai/api/v1` |
| `OLLAMA_BASE_URL` | Local model endpoint | `http://host.docker.internal:11434` |
| `AGENCY_WORKER_ENABLED` / `AGENT_MAX_STEPS` | Worker on/off / loop bound | `true` / 6 |
| `EMAIL_ENC_KEY` | Fernet key for email secrets (or `secrets/email_key`) | — |
| `EMAIL_LOOKBACK_DAYS` / `EMAIL_MAX_MESSAGES` | Sync window / cap | 14 / 40 |
| `MS_CLIENT_ID` / `MS_TENANT` | Microsoft Graph app | — / `common` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Gmail OAuth (IMAP used in practice) | — |
| `NTFY_TOPIC` / `NTFY_PORT` / `NTFY_BASE_URL` | Push topic / port / phone-facing URL | — / 8090 / — |

---

*This document describes the architecture as built. For the day-one quickstart see
[README.md](README.md); for the Tailscale setup see [TAILSCALE.md](TAILSCALE.md).*

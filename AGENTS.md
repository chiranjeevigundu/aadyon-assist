# AGENTS.md — operating manual for AI coding agents

This file is the first thing an AI coding agent (Claude Code, Cursor, Copilot, Windsurf, etc.)
should read before changing anything in this repo. It encodes the rules, layout, and recipes so
every agent works the same way and doesn't repeat past mistakes. Humans: see
[README.md](README.md) (quickstart) and [SYSTEM.md](SYSTEM.md) (full architecture).

**What this is:** Aadyon Assist — a self-hosted, single-user life-ops platform (Postgres +
FastAPI + Docker). One Postgres database is the single source of truth; on top of it sit a
Digital Me scoring model, an agentic org, and a read-only email-ingest pipeline. It runs on the
always-on "Mini-A" server and is reached over Tailscale.

---

## 🚦 Golden rules (non-negotiable)

1. **Never commit personal, financial, or immigration data.** Seed data, DB dumps, `artifacts/`,
   and `documents/` are gitignored — keep them that way. CI's `guard` job fails the build if it
   finds known personal strings. When adding examples, use placeholders.
2. **Never weaken the human-in-the-loop boundary.** Email sync and agents may *read* and
   *propose* only. Nothing may auto-execute a payment, email, filing, or destructive action.
   Side-effecting agent actions go through `propose_action` → `awaiting_approval`.
3. **Keep the app private.** The API has no auth by design; it must stay on the Tailscale tailnet.
   Do not add public exposure, and do not run `tailscale funnel`.
4. **Secrets come from Docker secrets**, not committed env values. Read order is always *secret
   file → env var* (see `core/config.py`).
5. **If you add a third-party import, add it to `code/api/requirements.txt`** (pinned). A clean
   `docker compose build --no-cache` must succeed.
6. **Verify before declaring done.** Run the verify loop (below). For refactors that shouldn't
   change behavior, the API parity check must pass.

---

## Repo map (where things live)

```
code/api/app/      FastAPI app — see SYSTEM.md §4 for the full module breakdown
  core/config.py     all settings (DB, secrets, model routing, email, ntfy)
  db/session.py      pooled query() helper
  models/tables.py   Entity registry — the list of CRUD tables + writable columns
  routers/           system, crud (factory), agency, email, dashboard
  services/          digital_me/dimensions/common, summary, routing/llm/tools/agency,
                     crypto, email_* (extract/store/imap/graph/ingest), ms_graph, notify
  jobs/              briefing_loop, agency_loop, import_entities (each its own container)
code/db/init/      SQL migrations 01..09 (run only on first boot of an empty volume)
code/dashboard/    vanilla HTML/JS pages + assets/ (base.css, base.js)
tests/             pytest suite (see §Verify)
scripts/verify.py  API parity check
docker-compose.yml six services: db, api, briefing, agency, backup, ntfy
```

Full architecture, data model, and data flows: **[SYSTEM.md](SYSTEM.md)**.
Past design decisions and rationale: **notes/decisions.md**.

---

## Run, build, verify

```bash
# Run the stack locally (laptop dev; API at http://localhost:8000)
cp .env.example .env && mkdir -p secrets && printf 'dev-password' > secrets/db_password.txt
docker compose up -d --build

# Run the test suite (no DB needed — imports + pure logic)
pip install -r code/api/requirements.txt pytest
pytest

# Parity check a running stack (refactors must not change untouched endpoints)
python scripts/verify.py --base http://localhost:8000 --save   # once, to set a baseline
python scripts/verify.py --base http://localhost:8000           # after changes, must match
```

CI (`.github/workflows/ci.yml`) runs: syntax-compile, narrow lint, dashboard JS parse, the
personal-data `guard`, `pytest`, and a Docker build + endpoint smoke test.

---

## Recipes

**Add a new entity (table the data admin can edit):**
1. Write a migration `code/db/init/NN_name.sql` (next number). Include `id uuid`, `created_at`,
   `updated_at` like the existing tables.
2. Register it in `code/api/app/models/tables.py` as an `Entity(table, [writable columns], order_by)`.
   That alone generates full CRUD endpoints and a typed admin form — no router code needed.
3. Apply it: on a fresh volume it auto-runs; on an existing DB run it manually (see §Gotchas).

**Add an API endpoint / read-model:** put logic in a `services/*.py` module, expose it from the
relevant router in `routers/` (or add a small new router and include it in `main.py`). Keep
metric math in `services/` so it isn't duplicated across views.

**Add an email provider:** follow the `email_*` split — reading/sync lives in a provider module
(`email_imap.py` / `email_graph.py`), extraction stays in `email_extract.py`, persistence in
`email_store.py`, and `email_ingest.sync_account()` dispatches by `auth_type`. Keep it read-only.

**Add/adjust an agent or model route:** agents and routes are *data* (`agents`, `model_routes`
tables), editable in the data admin — usually no code change. Tool definitions live in
`services/tools.py`; the run loop in `services/agency.py`.

---

## Deploy ritual

```powershell
# laptop — single clean commit, force-pushed (history is intentionally rewritten)
.\commit-and-push.bat
```
```bash
# Mini-A — upstream history was rewritten, so reset (don't merge), then rebuild
cd ~/aadyon-assist && git fetch origin && git reset --hard origin/main \
  && docker compose up -d --build api briefing agency
```

---

## ⚠️ Gotchas (learned the hard way)

- **Migrations only auto-run on an empty DB volume.** For the live Mini-A database, apply a new
  migration manually: `docker compose exec -T db psql -U aadyon -d aadyon_assist < code/db/init/NN_name.sql`.
- **`commit-and-push.bat` rewrites history (force-push).** On any other clone, use
  `git fetch && git reset --hard origin/main`, never a plain `git pull`.
- **Routers are generated from `tables.py`.** Don't hand-write CRUD endpoints; add the `Entity`.
- **Don't trust a stale editor/shell mount for verification.** If a tool reports null bytes or
  wrong line numbers on a file you just edited, re-read it with the editor's own file reader; the
  real source of truth is the file on disk that Docker builds from. Verify behavior against the
  live API, not a possibly-stale local view.
- **`information_schema` drives the admin UI.** Column type/required/FK changes flow through
  automatically; you don't hardcode form fields.

---

## Conventions

- Python 3.12, FastAPI, psycopg2 (pooled `query()` helper — don't open raw connections).
- Absolute imports (`from app.services import ...`).
- Keep functions small and dependency-light; pure metric helpers go in `services/common.py`.
- Match the existing terse, commented style. No new heavy dependencies without a clear reason.
- Dashboards: no build step. Shared styling/JS in `dashboard/assets/`; page-specific stays inline.

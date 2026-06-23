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
1. Create a migration with a **timestamped** name (never a sequential `NN_` number — those
   collide when agents work in parallel): run `scripts/new-migration.sh add_widget_table`, which
   writes `code/db/init/<YYYYMMDDHHMM>_add_widget_table.sql`. Include `id uuid`, `created_at`,
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

## Working in parallel (multiple agents / Cowork)

Codex, Antigravity, and Claude-in-Cowork can develop features at the same time. To keep that
safe, history is **linear** (no force-push) and work lands via branches + PRs:

1. **One branch per feature.** Start with `feature.bat` (or `git checkout -b feat/<name>` off an
   up-to-date `main`). Never commit feature work straight to `main`.
2. **Open a PR; let CI gate it.** Every PR runs `pytest` + the personal-data guard + the build
   smoke test. Merge only when green and reviewed (see `.github/CODEOWNERS`).
3. **Timestamped migrations only** (see the recipe above) — sequential `NN_` numbers collide.
4. **Deploy is human-serialized.** There is exactly one shared server (Mini-A) and one database;
   agents must **never auto-deploy**. A human merges to `main`, then runs the deploy below.
5. **Cloud agents verify with `pytest`, not the live stack.** They don't have `.env`/Docker
   secrets, so `pytest` (DB-free by design) is their gate; `scripts/verify.py` needs a running
   API and is run by whoever has the stack.
6. **Avoid two agents editing the same module at once.** Coordinate via PR scope; the generated-
   CRUD design keeps most features localized, which minimizes conflicts.

## Deploy ritual

```powershell
# laptop — commit current branch and push (normal history). Open a PR if it's a feature branch.
.\commit-and-push.bat
```
```bash
# Mini-A — history is linear now, so a normal fast-forward pull works
cd ~/aadyon-assist && git pull --ff-only \
  && docker compose up -d --build api briefing agency
```

---

## ⚠️ Gotchas (learned the hard way)

- **Migrations only auto-run on an empty DB volume.** For the live Mini-A database, apply a new
  migration manually: `docker compose exec -T db psql -U aadyon -d aadyon_assist < code/db/init/<timestamp>_name.sql`.
- **History is linear — do not force-push `main`.** `commit-and-push.bat` now makes normal
  incremental commits so PR-based agents don't get clobbered. A plain `git pull --ff-only` works
  on every clone. (If you ever rewrite history, you break every open PR and every other clone.)
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

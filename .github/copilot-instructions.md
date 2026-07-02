# Copilot / AI agent instructions

Full operating manual: **[AGENTS.md](../AGENTS.md)**. Architecture: **[SYSTEM.md](../SYSTEM.md)**.

This is Aadyon Assist — a self-hosted, multi-user life-ops platform (Postgres + FastAPI +
Docker) with a conversational assistant, typically reached over a private tailnet. One Postgres
DB is the single source of truth, with a Digital Me scoring model, an agentic org, and a
read-only email pipeline on top.

Rules to honor in every suggestion:

- Never put personal, financial, or immigration data in tracked files (gitleaks enforces this).
- Human-in-the-loop for external side effects: agents and email sync *propose*; they never
  auto-execute payments, emails, filings, or deletions. The assistant may edit the signed-in
  user's own records directly.
- Auth is JWT + Postgres Row-Level Security; never bypass the scoped `query()` for per-user
  tables, and keep `/api/health` + `/api/auth/*` as the only public routes.
- Read secrets via Docker secret files (env fallback); never hardcode keys.
- Add any new third-party import (pinned) to `code/api/requirements.txt`.

Patterns:

- CRUD endpoints + admin forms are generated from `code/api/app/models/tables.py` (the `Entity`
  registry) and live `information_schema`. Add a table = `just new-migration <name>` in
  `code/db/migrations/` + an `Entity`.
- Keep metric logic in `app/services/`; don't duplicate it across routers.
- Verify changes with `just test` and `just lint`; live parity via `scripts/verify.py`.

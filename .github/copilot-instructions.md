# Copilot / AI agent instructions

Full operating manual: **[AGENTS.md](../AGENTS.md)**. Architecture: **[SYSTEM.md](../SYSTEM.md)**.

This is Aadyon Assist — a self-hosted, single-user life-ops platform (Postgres + FastAPI +
Docker), reached over Tailscale on the always-on "Mini-A" server. One Postgres DB is the single
source of truth, with a Digital Me scoring model, an agentic org, and a read-only email pipeline
on top.

Rules to honor in every suggestion:

- Never put personal, financial, or immigration data in tracked files (CI guard enforces this).
- Read-only + human-in-the-loop: agents and email sync *propose*; they never auto-execute
  payments, emails, filings, or deletions.
- API is unauthenticated by design — assume Tailscale-only; never add public exposure.
- Read secrets via Docker secret files (env fallback); never hardcode keys.
- Add any new third-party import (pinned) to `code/api/requirements.txt`.

Patterns:

- CRUD endpoints + admin forms are generated from `code/api/app/models/tables.py` (the `Entity`
  registry) and live `information_schema`. Add a table = migration in `code/db/init/` + an `Entity`.
- Keep metric logic in `app/services/`; don't duplicate it across routers.
- Verify changes with `pytest` and `scripts/verify.py`.

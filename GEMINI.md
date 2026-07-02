# GEMINI.md

For Gemini-family agents (Google Antigravity, Gemini CLI, Jules). The operating manual for this
repo lives in **[AGENTS.md](AGENTS.md)** — read it first, then **[HANDOFF.md](HANDOFF.md)** for
the current state and **[ROADMAP.md](ROADMAP.md)** for what to work on next.

Quick reminders (full detail in AGENTS.md):

- Never commit personal/financial/immigration data; gitleaks gates CI and pre-commit.
- Human-in-the-loop for external side effects: agents and email sync *propose*; the assistant
  may edit the signed-in user's own records only.
- Auth is JWT + Postgres RLS; never bypass the scoped `query()` for per-user tables.
- Any new third-party import must be added (pinned) to `code/api/requirements.txt`.
- Routers are generated from `models/tables.py` — add an `Entity`, don't hand-write CRUD.
- Migrations: `just new-migration <name>` (yoyo, timestamped); apply with `just migrate`.
- Verify with `just test` and `just lint`; for refactors the API parity check must pass.
- End every session by updating HANDOFF.md (and ticking ROADMAP.md) in the same PR.
- Architecture: [SYSTEM.md](SYSTEM.md). Quickstart: [README.md](README.md).

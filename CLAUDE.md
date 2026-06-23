# CLAUDE.md

The operating manual for this repo lives in **[AGENTS.md](AGENTS.md)** — read it first.

Quick reminders (full detail in AGENTS.md):

- Never commit personal/financial/immigration data; keep the repo private and Tailscale-only.
- Read-only + human-in-the-loop: agents and email sync *propose*, never auto-execute side effects.
- Any new third-party import must be added (pinned) to `code/api/requirements.txt`.
- Routers are generated from `models/tables.py` — add an `Entity`, don't hand-write CRUD.
- Verify with `pytest` and `scripts/verify.py`; for refactors the API parity check must pass.
- Architecture: [SYSTEM.md](SYSTEM.md). Quickstart: [README.md](README.md). Decisions: notes/decisions.md.

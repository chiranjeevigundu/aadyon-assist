# Contributing

Whether you're a human or an AI coding agent, start with **[AGENTS.md](AGENTS.md)** — it's the
operating manual (golden rules, repo map, recipes, deploy ritual, and gotchas).

- Architecture & data model: **[SYSTEM.md](SYSTEM.md)**
- Quickstart: **[README.md](README.md)**
- Past decisions and rationale: **notes/decisions.md**

Before opening a change: run `pytest`, and for anything that shouldn't change behavior, confirm
the API parity check (`python scripts/verify.py`) still matches the baseline. Never commit
personal, financial, or immigration data — CI will fail the build if you do.

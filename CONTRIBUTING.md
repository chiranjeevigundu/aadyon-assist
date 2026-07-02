# Contributing

Thanks for your interest! Whether you're a human or an AI coding agent, start with
**[AGENTS.md](AGENTS.md)** — it's the operating manual (golden rules, repo map, recipes,
deploy ritual, and gotchas).

- Architecture & data model: **[SYSTEM.md](SYSTEM.md)**
- Quickstart: **[README.md](README.md)**
- Security model & reporting: **[SECURITY.md](SECURITY.md)**

## Dev setup

```bash
pip install -r code/api/requirements-dev.txt   # runtime + pytest/ruff/pre-commit/schemathesis
pre-commit install                             # ruff + gitleaks + hygiene on every commit
just up                                        # full stack at http://localhost:8000
```

## Before opening a PR

- `just test` — the unit suite is DB-free by design (the `query` seam is mocked); keep it that way.
- `just lint` — ruff (rules in `pyproject.toml`) + the dashboard JS syntax check.
- New DB tables: `just new-migration <name>` (timestamped; never hand-numbered), and add the
  RLS policy if the table holds per-user data (see the recipe in AGENTS.md).
- New Python deps: pin them in `code/api/requirements.txt` (runtime) or
  `code/api/requirements-dev.txt` (tooling); a clean `docker compose build --no-cache` must pass.
- **Never commit personal, financial, or immigration data** — gitleaks gates CI, and examples
  must use placeholders (see `code/db/seed.example.sql`).

CI runs ruff, gitleaks, pytest, a full Docker smoke test (signup → authenticated endpoints), and
a Schemathesis contract fuzz. Merge needs green CI + review (see `.github/CODEOWNERS`).

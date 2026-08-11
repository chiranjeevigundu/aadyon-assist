# Contributing

Thanks for taking a look. Bug reports and "this was confusing" feedback are as valuable as code —
this is a small project, and the rough edges are easiest to see with fresh eyes.

## Ways to help

**Found a bug?** [Open an issue](https://github.com/chiranjeevigundu/aadyon-assist/issues/new/choose)
with what you ran, what you expected, and what happened. `docker compose logs api` output helps a lot.

**Setup didn't work?** That's a bug in the docs — please report it. The install path should work
on a clean machine, and if it doesn't, we want to know.

**Want a feature?** Open an issue describing the problem you're trying to solve before writing
code. Some things are deliberately out of scope (see below), and it's better to find that out
first.

**Fixing something small?** Just send a PR — no issue needed for typos, doc fixes, or obvious bugs.

## Out of scope

So you don't spend effort on something that will be declined:

- **Autonomous financial actions.** Anything that moves money or sends mail without human
  approval. The proposals queue exists precisely to prevent this.
- **Third-party analytics or telemetry.** The point is that nobody else sees your finances.
- **Investment or tax advice features.** This tracks numbers; it doesn't advise.
- **Hosted multi-tenant SaaS concerns.** It's built for personal or family scale.

## Getting set up

```bash
git clone https://github.com/chiranjeevigundu/aadyon-assist.git
cd aadyon-assist

pip install -r code/api/requirements-dev.txt   # pytest, ruff, pre-commit, schemathesis
pre-commit install                             # ruff + gitleaks on every commit

just bootstrap-dev && just up-dev              # hot-reload API, DB port exposed, DEV_MODE on
```

`bootstrap-dev` copies `.env.development.example`, which ships `DEV_MODE=true` — that serves
`/data` (raw table console) and `/docs` (Swagger), handy while developing. Both are off in a
normal deployment.

## Before you open a PR

```bash
just test    # DB-free unit suite
just lint    # ruff + Biome (dashboard JS/CSS)
```

Both run in CI along with gitleaks, a Docker smoke test, and a Schemathesis contract fuzz.

A few conventions worth knowing — full detail in **[AGENTS.md](AGENTS.md)**, which is the
operating manual for this repo:

- **Tests stay DB-free.** The `query` seam is mocked (see `tests/conftest.py`). Don't add a test
  that needs a live Postgres.
- **New table?** `just new-migration <name>` (timestamped, never hand-numbered), and add an RLS
  policy if it holds per-user data. Then register it in `models/tables.py` — CRUD routes are
  generated from that registry, not hand-written.
- **New dependency?** Pin it in `code/api/requirements.txt` (runtime) or `requirements-dev.txt`
  (tooling). `docker compose build --no-cache` must still pass.
- **Never commit personal or financial data.** gitleaks gates CI and pre-commit; examples must
  use placeholders.
- **Don't weaken the approval boundary.** External side effects go through `propose_action`.

## Notes for AI coding agents

This repo is partly maintained by AI agents, and there's a protocol for it:

- Read **[AGENTS.md](AGENTS.md)** first — golden rules, repo map, recipes, gotchas.
- **[docs/HANDOFF.md](docs/HANDOFF.md)** carries state between sessions. Update it at the end of
  yours; chat context doesn't transfer between tools, and that file is the shared memory.
- Verify claims against the running system rather than assuming. Several bugs in this repo's
  history were found only by actually running the thing.

## Code style

Python is formatted by **ruff** (config in `pyproject.toml`); dashboard JS/CSS by **Biome**.
Both run in pre-commit, so mostly you don't have to think about it. Line endings are normalized
to LF via `.gitattributes`.

The dashboards are deliberately vanilla HTML/JS with **no build step** — please keep it that way
unless there's a strong reason.

## Questions

Open a [discussion or issue](https://github.com/chiranjeevigundu/aadyon-assist/issues). Also see
[SECURITY.md](SECURITY.md) for reporting vulnerabilities — please don't file those as public issues.

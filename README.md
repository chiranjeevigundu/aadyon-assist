# Aadyon Assist

[![CI](https://github.com/chiranjeevigundu/aadyon-assist/actions/workflows/ci.yml/badge.svg)](https://github.com/chiranjeevigundu/aadyon-assist/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Self-hosted personal finance tracking, with an AI assistant that can't spend your money.**

Track your **net worth** — assets minus debts — in one place you own. Forward a statement or
connect a mailbox and it extracts the figures for you to approve. Ask the assistant questions in
plain language and it answers from your real numbers.

Everything runs on your own machine. No accounts, no telemetry, no third party sees your finances.

```bash
git clone https://github.com/chiranjeevigundu/aadyon-assist.git
cd aadyon-assist && just bootstrap-dev && just up
# open http://localhost:8000 and sign up
```

---

## Is this for you?

**A good fit if** you want your financial picture in one place, on hardware you control, and
you're comfortable running Docker.

**Not a good fit if** you want a hosted app with no setup, automatic bank syncing via Plaid, tax
filing, or investment advice. This tracks what you tell it (or what it reads from your documents
and mail); it does not connect to brokerages, and it never gives financial advice.

> **Project status:** actively developed, used daily by its author. It is a personal-scale tool —
> designed for one person or a family, not a multi-tenant service. Expect rough edges, and read
> [SECURITY.md](SECURITY.md) before exposing it to the internet (short version: don't — put it
> behind [Tailscale](docs/TAILSCALE.md)).

## What you get

| | |
|---|---|
| **Net worth** (`/`) | Assets − liabilities at a glance, broken down by type, with a trend you build by snapshotting over time. Add, edit and delete holdings and debts inline. |
| **Tracker** (`/tracker`) | Cash flow: debts in payoff order with interest math, bills, subscriptions, deadlines, and income. Full add/edit/delete. |
| **Assistant** (`/assistant`) | Chat that reads your real figures — "what's my net worth?", "which debt should I clear first?" — and can update your records for you. |
| **Accounts** (`/accounts`) | Connect mailboxes (read-only) and upload statements; extracted items land in a review queue. |

### The safety rule

The assistant can freely edit **your own records** — add an asset, mark a subscription inactive.
But anything with a **real-world effect** — moving money, sending an email, paying a bill — is
written to a **proposals queue for you to approve**. It never executes on its own. That boundary
is deliberate and enforced in code, not prompt instructions.

## Requirements

- **Docker** with Compose
- **[just](https://github.com/casey/just)** — `brew install just` · `winget install Casey.Just` · `apt install just`
- ~2 GB disk. No cloud account needed.
- *Optional:* an [OpenRouter](https://openrouter.ai) key for the assistant, or
  [Ollama](https://ollama.com) to run a model locally.

## Install

```bash
git clone https://github.com/chiranjeevigundu/aadyon-assist.git
cd aadyon-assist

just bootstrap-dev     # writes .env and generates secrets/ (never overwrites existing ones)
just up                # builds, applies migrations, starts everything
```

Open **http://localhost:8000** and create your account. The first account on a fresh instance can
always sign up. After that, `INVITE_REQUIRED` decides whether new accounts need an invite code —
there's no UI for minting one yet, so use the API from a signed-in account:

```bash
curl -X POST http://localhost:8000/api/auth/invites \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}'
```

To start over completely: `docker compose down -v && just up` (this destroys the database).

### Turning on the assistant

The assistant needs a model. Put an OpenRouter key in `.env`:

```bash
OPENROUTER_API_KEY=sk-or-...
```

…or run [Ollama](https://ollama.com) locally and set `OLLAMA_BASE_URL`. Without a key the app
works fine — the chat just tells you it isn't configured.

## Configuration

Everything lives in `.env` (start from `.env.example`). Secrets are read from `secrets/*.txt`
first, then the environment.

| Variable | Default | What it does |
|---|---|---|
| `API_PORT` | `8000` | Host port for the web app |
| `TZ` / `BRIEFING_HOUR` | `UTC` / `7` | Timezone, and when the daily briefing is written |
| `INVITE_REQUIRED` | `true` | Require an invite code to register (the first account is always allowed) |
| `DEV_MODE` | `false` | Expose developer tools — see below. Leave off in normal use |
| `OPENROUTER_API_KEY` | — | Enables the assistant |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Local model endpoint |
| `STORAGE_BACKEND` | `local` | `local` disk, or `s3` for object storage |
| `S3_ENDPOINT_URL` | — | Set for an S3 emulator; leave empty for real AWS |
| `EMAIL_ENC_KEY` | — | Fernet key encrypting stored mailbox credentials |
| `NTFY_TOPIC` | — | Enables the morning push to your phone |

Full list: [`.env.example`](.env.example) · storage details: [docs/cloud-storage.md](docs/cloud-storage.md)

### Developer mode

`DEV_MODE=true` additionally serves:

- `/data` — a raw table console for every entity, built from the live schema
- `/docs`, `/redoc`, `/openapi.json` — FastAPI's generated API reference

These are **off by default and return 404**, because they expose database structure directly.
Everything a normal user needs is in the product UI. Never enable this on an internet-facing
instance.

## How it works

Six containers, one Postgres database as the single source of truth:

| Service | Role |
|---|---|
| `api` | FastAPI — REST API and the dashboards |
| `db` | Postgres 16 + pgvector |
| `migrate` | Applies schema migrations on startup, then exits |
| `briefing` | Writes the daily digest and pushes it to your phone |
| `backup` | Nightly `pg_dump`, 14-day retention |
| `ntfy` | Self-hosted push notifications |

Accounts are isolated **in the database** by Postgres row-level security, not just in
application code — a missing user sees zero rows rather than everything.

Architecture in depth: **[docs/SYSTEM.md](docs/SYSTEM.md)** · diagrams:
**[docs/architecture.md](docs/architecture.md)**

## Everyday commands

```bash
just up          # start everything          just down        # stop
just logs        # follow logs               just test        # run the test suite
just lint        # ruff + Biome              just migrate     # apply new migrations
just backup-now  # dump the database         just restore <f> # restore a dump
just --list      # everything else
```

## Documentation

| Doc | For |
|---|---|
| [docs/SYSTEM.md](docs/SYSTEM.md) | Full system design: requirements, data model, trade-offs, scaling |
| [docs/architecture.md](docs/architecture.md) | Rendered architecture diagrams |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Setting up to develop, and how to send a change |
| [SECURITY.md](SECURITY.md) | Security model and how to report a vulnerability |
| [docs/TAILSCALE.md](docs/TAILSCALE.md) | Reaching the app from your phone, safely |
| [docs/cloud-storage.md](docs/cloud-storage.md) | Object storage: real AWS ⇄ local emulator |
| [docs/CLOUD.md](docs/CLOUD.md) | Moving to a managed cloud platform |
| [deploy/k8s/README.md](deploy/k8s/README.md) | Running on Kubernetes instead of Compose |
| [docs/ROADMAP.md](docs/ROADMAP.md) | What's planned |

## Troubleshooting

**`just: command not found`** — install [just](https://github.com/casey/just), or run the
underlying `docker compose` commands directly (see the `justfile`).

**The page won't load** — check the stack is healthy with `docker compose ps`; `api` and `db`
should be `healthy`. `just logs` shows why if not.

**"an invite code is required" on signup** — an account already exists on this instance. Sign in
with it and mint an invite, or set `INVITE_REQUIRED=false` in `.env` and restart.

**The assistant says it isn't configured** — no model key. Add `OPENROUTER_API_KEY` to `.env`
and `just up` again.

**`/data` or `/docs` returns 404** — that's intentional; set `DEV_MODE=true` to enable them.

**Port 8000 already in use** — set `API_PORT` in `.env`.

Still stuck? [Open an issue](https://github.com/chiranjeevigundu/aadyon-assist/issues) with what
you ran and what you saw.

## Contributing

Contributions are welcome — see **[CONTRIBUTING.md](CONTRIBUTING.md)**. Bug reports and
"this was confusing" feedback are just as useful as code.

## License

MIT — see [LICENSE](LICENSE). Do what you like with it; no warranty.

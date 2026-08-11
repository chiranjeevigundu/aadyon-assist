# Documentation

Start at the [project README](../README.md) if you just want to run the app. These are the
deeper documents.

## Understanding the system

| Doc | What's in it |
|---|---|
| **[SYSTEM.md](SYSTEM.md)** | The full system design — requirements, high-level design, data model, API surface, scale and reliability, and an explicit trade-off analysis. Start here to understand *why* it's built this way. |
| **[architecture.md](architecture.md)** | The same architecture as rendered diagrams (also available as editable [`architecture.mermaid`](architecture.mermaid) and [`services-architecture.mermaid`](services-architecture.mermaid)). |

## Running it

| Doc | What's in it |
|---|---|
| **[TAILSCALE.md](TAILSCALE.md)** | Reaching the app from your phone without exposing it to the internet. |
| **[cloud-storage.md](cloud-storage.md)** | Object storage for documents and backups. The same code targets real AWS S3 or a local emulator — one setting decides which. |
| **[CLOUD.md](CLOUD.md)** | Moving from a home server to a managed cloud platform: managed Postgres, secrets, scaling. |
| **[../deploy/k8s/README.md](../deploy/k8s/README.md)** | Running on Kubernetes instead of Docker Compose, with a one-command deploy script. |

## Contributing and project state

| Doc | What's in it |
|---|---|
| **[../CONTRIBUTING.md](../CONTRIBUTING.md)** | How to set up for development and send a change. |
| **[../AGENTS.md](../AGENTS.md)** | The operating manual: golden rules, repo map, common recipes, and gotchas. Written for AI coding agents, but it's the most practical reference for humans too. |
| **[ROADMAP.md](ROADMAP.md)** | What's planned and what's deliberately out of scope. |
| **[HANDOFF.md](HANDOFF.md)** | A running log of what each work session changed and why. Useful for archaeology — "why is this like this?" is often answered here. |
| **[../SECURITY.md](../SECURITY.md)** | The security model, and how to report a vulnerability. |

## Conventions

- **Diagrams** are [Mermaid](https://mermaid.js.org/). `.mermaid` files are the editable source;
  `architecture.md` embeds the same graphs in fenced blocks so GitHub renders them. Edit both.
- **Docs describe what is, not what's planned.** Anything aspirational belongs in `ROADMAP.md`.
- **Claims should be checkable.** If a doc says an endpoint exists or a command works, it should
  be true of the current code — several bugs here were found by verifying documentation against
  the running system.

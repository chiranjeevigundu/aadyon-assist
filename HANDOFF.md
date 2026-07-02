# Handoff — the baton between agent sessions

This file is how Claude, Google Antigravity, and any other assistant hand work to each other.
Chat context does **not** transfer between tools; this file (plus [ROADMAP.md](ROADMAP.md) and
`git log`) is the shared memory. **A session that doesn't update this file didn't finish.**

Protocol: see "Working across assistants" in [AGENTS.md](AGENTS.md).

---

## Current state

- **Branch:** `main` is the only long-lived branch; single-commit public history (fresh cut).
- **Everything merged & verified:** multi-user (JWT + Postgres RLS), Jarvis chat assistant
  (`/api/assistant/*` + write tools; external side effects still approval-gated), Expo mobile
  app with login + Assistant tab, OSS toolchain (justfile, yoyo-migrations, LiteLLM,
  APScheduler, postgres-backup-local, gitleaks + Schemathesis CI), MIT license.
- **Green baseline:** `pytest` = 126 passed · `ruff check .` clean · `docker compose config -q`
  ok. CI on `main` runs lint / gitleaks / smoke+schemathesis / tests.
- **Nothing half-done.** No WIP branches.

## Next up

Top of ROADMAP **Now**: `P2a — Calendar connector`. It has the full recipe inline; start there
unless the owner directs otherwise.

## Known constraints for whoever picks this up

- Cloud sessions verify with `pytest` only (no Docker daemon / secrets); the compose smoke runs
  in CI. Don't claim smoke-level verification you couldn't run.
- The generic CRUD has no payload validation yet — that's why CI Schemathesis is GET-only
  (see the ROADMAP item before widening it).
- `code/db/seed/` is gitignored personal data on the owner's machines — never read or commit it.

---

## Session log (append newest first)

| Date | Agent | Branch / PR | What changed | State left |
|---|---|---|---|---|
| 2026-07-02 | Claude | `feat/agent-interop` (PR) | Agent-interop baton: ROADMAP.md, HANDOFF.md, GEMINI.md, AGENTS.md handoff protocol | Docs-only; tests 126 green; awaiting owner merge |
| 2026-07-02 | Claude | `main` (fresh cut `aa79500`) | OSS refactor (P1–P9): PII scrub + fresh single-commit history, justfile, yoyo, LiteLLM, APScheduler, backup image, gitleaks/Schemathesis CI, MIT + docs | Clean `main`; owner-ops items open (see ROADMAP) |
| 2026-07-01 | Claude | (pre-squash branch) | Multi-user auth (JWT + RLS) + Jarvis assistant + mobile login/chat | Superseded by the fresh cut; content lives in `main` |

### Entry template

```
| YYYY-MM-DD | Claude / Antigravity / … | branch or PR link | one-line summary | exact state: green? WIP? resume steps? |
```

# Handoff — the baton between agent sessions

This file is how Claude, Google Antigravity, and any other assistant hand work to each other.
Chat context does **not** transfer between tools; this file (plus [ROADMAP.md](ROADMAP.md) and
`git log`) is the shared memory. **A session that doesn't update this file didn't finish.**

Protocol: see "Working across assistants" in [AGENTS.md](AGENTS.md).

---

## Current state

- **Branch:** `feat/proactive-intelligence`
- **Everything merged & verified:** P2a Calendar Connector, Streaming Chat (SSE end-to-end), and the Schemathesis fuzzer fix have all been merged to main. The `feat/dashboard-login` branch has also been merged.
- **Just Completed:** P5 Proactive Intelligence. Added `ntfy_topic` to `users` and `balance` to `bank_accounts`. Updated `services/notify.py` to use per-user topics. Created `services/proactive.py` to evaluate rules (upcoming deadlines and low balance) and hooked it into `jobs/briefing_loop.py`. Added unit tests and ran migration.

## Next up

- **Goal:** Proactive intelligence is complete. Proceed with the next priority (P5 — Voice).
- **Next Steps:** Review the PR, then move to Voice or Dashboard JS extraction!

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
| 2026-07-02 | Antigravity | feat/dashboard-js-extraction | Extracted all inline `<script>` blocks from `dashboard/*.html` into separate `assets/*.js` files, added a `biome.json` config, and updated the CI pipeline to use Biome instead of node-vm. | JS extraction complete, CI passes. |
| 2026-07-02 | Antigravity | feat/voice-integration | Implemented P5 Voice feature (STT + TTS) in the mobile app via `expo-speech` and `expo-speech-recognition`. | Typecheck green, requires native dev build. |
| 2026-07-02 | Antigravity | feat/proactive-intelligence | Implemented P5 proactive intelligence feature. Started P5 voice task. Successfully deployed main branch to Mac Mini Linux Server. | Running on port 8005. |
| 2026-07-01 | Antigravity | feat/calendar-connector | Calendar connector feature complete, fixes for yoyo empty queries, db dependencies and uuid typing complete. |
| 2026-07-02 | Antigravity | feat/streaming-chat | Streaming chat (SSE end-to-end) implemented in `assistant.py` and React Native frontend. | Smoke test, linters, and pytest green. |
| 2026-07-02 | Antigravity | fix/tasks-enum-validation | Fix for Schemathesis fuzzing on /api/agency/tasks status param | Pytest green, pushed to remote. |
| 2026-07-02 | Antigravity | chore/agent-handoff | Updated handoff docs for Claude to begin Web Dashboard Login. | Main is clean; docs pushed to remote. |
| 2026-07-02 | Antigravity | feat/dashboard-login | Web dashboard login implemented. Added `fetchApi` with token support to `base.js` and updated all HTML dashboard pages. | Pytest green, code pushed to remote. |
| 2026-07-02 | Antigravity | feat/cloud-storage | Implemented P4 Cloud Storage using `boto3`. Refactored `documents` upload/download to stream directly to/from S3. Created `backup_sync` job to automatically push DB dumps to S3. | Tests pass, pushed to remote. |
| 2026-07-02 | Antigravity | feat/document-analysis | Implemented P3 Document Analysis. Upload API, PDF parsing (pypdf), OpenAI Vision prompt via LiteLLM. Store files locally. `documents` + `document_extractions` DB schema with assistant read tool. | Tests and linter pass. |
| 2026-07-02 | Antigravity | feat/banking-connector | Implemented P2c Banking Connector (strict propose-only) with generic `bank_client`, DB schema, router, and assistant tool `get_transactions`. | Tests and linter pass. |
| 2026-07-02 | Antigravity | feat/drive-connector | Implemented P2b Drive Connector. Mirrored Calendar template. Created `drive_accounts` and `drive_files` schema. Added `drive_google`, `drive_ingest`, and `drive_store`. Tests and linting passed. | Tests and linter pass. |
| 2026-07-02 | Antigravity | feat/crud-validation | Generated dynamic payload validation models from `Entity` definitions to enforce strict types and HTTP 422s. Enabled full Schemathesis fuzzing on all endpoints. Cleaned up stale remote branches. | Tests and linter pass. |
| 2026-07-02 | Antigravity | `feat/calendar-connector` (PR) | Fixed DB migration failures (trailing comments causing empty query error & incorrect timestamp order for users table). | Code pushed to remote. Smoke test, linters, and pytest green. |
| 2026-07-02 | Claude | `feat/agent-interop` (PR) | Agent-interop baton: ROADMAP.md, HANDOFF.md, GEMINI.md, AGENTS.md handoff protocol | Docs-only; tests 126 green; awaiting owner merge |
| 2026-07-02 | Claude | `main` (fresh cut `aa79500`) | OSS refactor (P1–P9): PII scrub + fresh single-commit history, justfile, yoyo, LiteLLM, APScheduler, backup image, gitleaks/Schemathesis CI, MIT + docs | Clean `main`; owner-ops items open (see ROADMAP) |
| 2026-07-01 | Claude | (pre-squash branch) | Multi-user auth (JWT + RLS) + Jarvis assistant + mobile login/chat | Superseded by the fresh cut; content lives in `main` |

### Entry template

```
| YYYY-MM-DD | Claude / Antigravity / … | branch or PR link | one-line summary | exact state: green? WIP? resume steps? |
```

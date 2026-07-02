# Handoff — the baton between agent sessions

This file is how Claude, Google Antigravity, and any other assistant hand work to each other.
Chat context does **not** transfer between tools; this file (plus [ROADMAP.md](ROADMAP.md) and
`git log`) is the shared memory. **A session that doesn't update this file didn't finish.**

Protocol: see "Working across assistants" in [AGENTS.md](AGENTS.md).

---

## Current state

- **Branch:** `feat/voice` (PR open) — P5 Voice: `mobile/src/voice.ts` (lazy-loaded
  expo-speech TTS + expo-speech-recognition STT, degrades gracefully in Expo Go), mic button +
  speak-replies toggle in AssistantScreen, iOS mic/speech permissions + config plugin in
  app.json. Voice needs a dev/EAS build (`eas build`), not Expo Go. Also fixes a pre-existing
  tsc error in mobile/src/api.ts. `npm run typecheck` clean.
- **Previously merged:** `feat/proactive-alerts` (PR #24) — P5 proactive intelligence: `users.ntfy_topic`
  migration, `services/alerts.py` (deadline/bill windowing read-model), generic
  `notify.push_message` with per-user topics, briefing worker pushes an alert digest after each
  user's briefing, `GET /api/alerts`, `PATCH /api/auth/me` (set display_name / ntfy_topic).
- **`main` is GREEN** (first time) — the CI fixes (`register_uuid`, NUL-byte 422 mapping,
  NUL-in-query middleware) merged via PR #23.
- **Verified this session:** `pytest` 146 passed · `ruff check .` clean. CI on the PR is the
  smoke gate.

## Next up

- Merge `feat/voice` when CI is green — that completes the original ROADMAP build-out.
- Remaining chores: dashboard-JS extraction (Later section) and the owner-only ops box.

## Known constraints for whoever picks this up

- Cloud sessions verify with `pytest` only (no Docker daemon / secrets); the compose smoke runs
  in CI. Don't claim smoke-level verification you couldn't run.
- Schemathesis now fuzzes ALL endpoints (writes included) — any new endpoint must never 5xx on
  bad input; map DB/validation errors to 4xx like `routers/crud.py` does.
- psycopg2 needs explicit adapters for non-primitive param types (UUID is registered in
  `db/session.py`; add others there if new typed columns appear).
- `code/db/seed/` is gitignored personal data on the owner's machines — never read or commit it.

---

## Session log (append newest first)

| Date | Agent | Branch / PR | What changed | State left |
|---|---|---|---|---|
| 2026-07-02 | Claude | `feat/voice` (PR) | P5 Voice: STT mic + TTS speak-replies in the Assistant tab (lazy voice.ts, iOS permissions/plugin); fixed mobile tsc error | typecheck clean, pytest 146 green; needs EAS build for native voice |
| 2026-07-02 | Claude | `feat/proactive-alerts` (PR) | P5 proactive intelligence: per-user ntfy topics, alerts read-model + digest push, GET /api/alerts, PATCH /api/auth/me | pytest 146 green, ruff clean; merge when CI green |
| 2026-07-02 | Claude | `fix/ci-uuid-lint` (PR) | CI red-to-green: `register_uuid()` in db/session.py (UUID params 500'd under write-fuzzing) + removed unused import in routers/documents.py | pytest 140 green, ruff clean; merge when CI green |
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

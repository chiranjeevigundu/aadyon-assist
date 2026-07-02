# Roadmap

The shared backlog for every contributor — human or AI agent (Claude, Google Antigravity, …).
Each item is written so an agent with **no chat history** can execute it: goal, what to reuse,
and acceptance criteria. Work top-down within a section. When you pick an item, note it in
[HANDOFF.md](HANDOFF.md); when you finish, tick it here **in the same PR**.

Status: `[ ]` open · `[~]` in progress (see HANDOFF.md for who/where) · `[x]` done.

---

## Now

- [x] **P2a — Calendar connector (read + propose only)**
  Goal: connect Google Calendar; upcoming events become reviewable deadline suggestions.
  Reuse: clone the email template — `calendar_accounts` + `calendar_extractions` tables
  (mirror `07_email_accounts.sql`/`08_email_ingest.sql`, with `user_id` + RLS per the pattern
  in `code/db/migrations/202607010711_multiuser_auth.sql`), `services/calendar_ingest.py`
  (cursor + dedup like `email_ingest.py`/`email_store.py`), secrets Fernet-encrypted via
  `services/crypto.py`, extraction via `routing.resolve("cheap")` + `llm.chat`,
  `routers/calendar.py` mirroring `routers/email.py` (`/connect`, `/sync`,
  `/extractions/{id}/approve|dismiss`). Google OAuth client config already exists in
  `core/config.py` (`google_client_id/secret`). Assistant gains a read tool `get_calendar`
  in `services/tools.py`; event **creation** stays behind `propose_action`.
  Accept: `just test` green (new DB-free unit tests for ingest/dedup); CI smoke passes;
  a synced event shows in the review queue and Approve creates a `deadlines` row.

- [x] **Streaming chat (SSE end-to-end)**
  Goal: token streaming in the Assistant tab.
  Reuse: `litellm.completion(stream=True)` in `services/llm.py` (design note in module
  docstring: stream only the terminal turn; tool rounds stay non-streamed);
  `routers/assistant.py` `/chat/stream` already emits SSE; add `react-native-sse` (pin in
  `mobile/package.json`) and wire `AssistantScreen.tsx`.
  Accept: visible incremental tokens in the app; non-streaming `/chat` unchanged; tests green.

- [x] **Web dashboard login**
  Goal: the vanilla-JS dashboards (`/`, `/tracker`, `/data`, `/agency`, `/accounts`) currently
  401 — add a login page + token storage (localStorage) + `Authorization` header in
  `dashboard/assets/base.js` fetch helpers, mirroring `mobile/src/api.ts` (401 → redirect to
  login). Keep no-build-step vanilla JS.
  Accept: login → all five pages work; logout clears token; smoke test extended.

## Next

- [x] **CRUD payload validation** — generate Pydantic models (or per-column type coercion) from
  the `Entity` registry in `models/tables.py` so bad payloads 422 instead of 500; then widen the
  CI Schemathesis step beyond `--include-method GET` (see comment in `.github/workflows/ci.yml`).
  Accept: fuzzed writes never 5xx; existing CRUD tests updated; Schemathesis fuzzes writes in CI.
- [x] **P2b — Drive connector** (read-only listing → feeds P3): same connector template;
  OAuth like calendar. Accept: file list synced per user, RLS-scoped.
- [x] **P2c — Banking connector (strict propose-only)**: API key in `secret_enc`;
  transactions → review queue; assistant `get_transactions` read tool. Money movement is
  NEVER executed — `propose_action` only (AGENTS.md golden rule 2).
- [x] **P3 — Document analysis**: `POST /api/documents` (FastAPI `UploadFile`), per-user
  `documents` + `document_extractions` tables (RLS), text PDFs via `pypdf` (pin), scans via an
  OpenRouter vision model through `llm.chat`; review queue → approved rows become
  deadlines/bills/subscriptions. Store files under `artifacts_dir` until P4.

## Later

- [x] **P4 — Cloud storage**: S3-compatible (boto3, pinned) for documents + backup dumps;
  per-user key prefixes; creds via Docker secrets; bucket never exposed publicly.
- [ ] **P5 — Proactive intelligence**: per-user ntfy topics (column on `users`), alert rules
  (deadline within N days, low balance from P2c) pushed via `services/notify.py`.
- [ ] **P5 — Voice**: Expo STT (`expo-speech-recognition` or `@react-native-voice/voice`) →
  `/api/assistant/chat`; TTS via `expo-speech`. Thin client layer; no backend change.
- [ ] **Dashboard JS extraction**: move inline `<script>` blocks into linted `.js` assets and
  replace the node-`vm` CI check with a real JS linter (Biome/ESLint).

## Owner-only ops (not agent tasks)

- [ ] Revoke/rotate the GitHub PATs shared in past chat sessions.
- [ ] GitHub Support ticket: GC the pre-squash commits (old SHAs remain fetchable until then).
- [ ] `eas init` in `mobile/` to attach your own Expo project; rotate `jwt_secret` if desired.
- [ ] On each existing deployment: move personal seeds to `code/db/seed/`, then
  `just backup-now && just migrate-baseline`.

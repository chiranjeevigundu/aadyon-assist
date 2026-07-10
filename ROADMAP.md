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

- [x] **Mobile mail integrations** (owner request, 2026-07-08)
  Goal: manage mailboxes from the iPhone app, not just the web dashboard.
  Reuse: the existing backend as-is — generic `/api/email_accounts` CRUD plus
  `routers/email.py` (`/connect`, `/disconnect`, `/ms/start|complete`, `/sync`,
  `/extractions/*`); UI mirrors `dashboard/assets/accounts.js`. New
  `mobile/src/screens/MailScreen.tsx` (add/remove accounts, IMAP app-password connect,
  Microsoft device-code connect, sync, pending-extraction review), reached from
  Settings → Connections (the Settings tab is now a native stack).
  Accept: mobile `npm run typecheck` clean; add → connect → sync → review round-trip
  works against a running API; mail stays read-only with approve-gated extractions.

- [x] **Gmail OAuth connect** (owner request, 2026-07-10)
  Goal: connect Gmail without an app password (the disabled "Gmail OAuth soon" button).
  Constraint: Gmail scopes aren't allowed in Google's device-code flow, so the sign-in runs on
  the phone (auth-code + PKCE via `expo-auth-session`, iOS-type client, reversed-client-id
  scheme); the backend exchanges the one-time code and keeps only the encrypted refresh token.
  Reuse: mirrors the Microsoft pair — `services/google_oauth.py` (like `ms_graph.py`) +
  `services/email_gmail.py` (like `email_graph.py`), dispatched by `auth_type` in
  `email_ingest.sync_account`; router gains `GET /api/email/google/config` +
  `POST /{id}/google/complete`. Owner setup in `mobile/README.md` (Google Cloud iOS client,
  `GOOGLE_CLIENT_ID` in `.env`, app.json scheme + rebuild).
  Accept: `just test` green (network mocked); connect from the phone lands an encrypted
  refresh token and Sync pulls via Gmail REST, read-only, extractions approve-gated as ever.

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
- [x] **P5 — Proactive intelligence**: per-user ntfy topics (column on `users`), alert rules
  (deadline within N days, low balance from P2c) pushed via `services/notify.py`.
- [x] **P5 — Voice**: Expo STT (`expo-speech-recognition` or `@react-native-voice/voice`) →
  `/api/assistant/chat`; TTS via `expo-speech`. Thin client layer; no backend change.
- [x] **Dashboard JS extraction**: move inline `<script>` blocks into linted `.js` assets and
  replace the node-`vm` CI check with a real JS linter (Biome/ESLint).

## Personal secretary — the "it just tracks my life" upgrades

Vision (owner, 2026-07-04): upload a statement / forward an email, and the app tracks
what an average person deals with — new bill, subscription started/ended, deadline —
keeping the dashboards current automatically, with the assistant delegating to its agents
and remembering everything. Must stay scalable + cloud-migratable. Foundations landed in
`fix/storage-and-connection-resilience` (storage actually persists now; DB connections
recycle) — these build on it. Priority order is a proposal; owner to confirm.

- [x] **Auto-apply high-confidence extractions (close the loop).** Today every document/
  email extraction waits in a review queue for a manual approve. Add a per-item confidence
  + a rule: high-confidence, unambiguous items (a clear recurring subscription, a dated bill)
  apply straight to `bills`/`subscriptions`/`deadlines` and just *notify*; ambiguous ones
  still queue. Reuse `document_store.approve_extraction` as the apply path. Accept: uploading
  a statement updates the dashboard with no manual step for clear items; borderline items still
  reviewable.
- [x] **Recurring-statement dedup + lifecycle.** A monthly statement re-lists the same Netflix
  sub — don't create duplicates; update the existing row (amount changed → update; not seen for
  N cycles or an email says "cancelled" → mark ended). Natural-key dedup like
  `jobs/import_entities.py` already does. Extend `subscriptions` with a `status`
  (active/ended) + `last_seen`. Accept: re-uploading the same statement is idempotent; "my
  Spotify ended" via chat or email flips status, and the dashboard reflects it.
- [x] **Email → tracked items (turn the read-only pipeline on).** `email_ingest` already
  extracts to a review queue; wire it to the same auto-apply/dedup path so "your subscription
  renewed / a new charge / a bill is due" emails become tracked items. Keep read-only + the
  propose_action boundary for anything external. Accept: a synced email about a new subscription
  shows up tracked (or queued) without manual entry.
- [x] **Assistant delegation that's visible + remembered.** `delegate` creates agent tasks but
  results aren't surfaced back. Let the assistant delegate (e.g. "Finance: find my 3 priciest
  subscriptions"), then read the agent's result and report it; persist a durable timeline of
  what was tracked/decided so it's queryable later ("what changed on my card last month?").
  Reuse `agents`/`tasks`/`agent_runs`. Accept: a delegated task runs, its result comes back in
  chat, and the history is retrievable.
- [x] **Assistant long-term memory.** A per-user memory store (the `memory_chunks` table +
  pgvector already exist) the assistant writes salient facts to and retrieves on later turns, so
  it behaves like a secretary who remembers. Accept: tell it something one session, it recalls it
  the next.
- [ ] **Dashboard freshness signals.** Surface "updated just now / N new items to review" on the
  dashboards + a lightweight change feed, so the owner sees when tracking happened. Accept: after
  an upload/email sync, the dashboard shows what changed without a manual refresh hunt.
- [x] **Cloud migration guide + readiness.** See [docs/CLOUD.md](docs/CLOUD.md). Document + verify the path to a managed cloud DB
  (RDS/Cloud SQL) and object storage (S3/GCS): `STORAGE_BACKEND=s3`, connection pooling already
  hardened, secrets via the platform's secret manager, migrations via the `migrate` job. Accept:
  a documented, tested deploy to one cloud target.

## Family & friends multi-user (a handful of trusted people)

Goal (owner, 2026-07-05): open the app to a few trusted people, not the public App Store.
The data layer is already multi-tenant (JWT + enforced RLS + per-user org). This hardens
the *account* layer so it's safe for others, without the full public-product lift (no
billing, no App Store legal). Hosting decided later; build code-side now. Email via a
transactional API (`services/mailer.py`, Resend-style, secret-file key; logs to stdout when
no key is set so dev/CI never send).

- [x] **Invite-only signup.** New `invite_codes` table (global, `query_unscoped`); signup
  requires a valid unused, unexpired code, which is marked used on success. Admin mints codes.
  Accept: signup without a valid code 400s; a code works exactly once.
- [x] **Rate limiting on auth.** In-memory fixed-window limiter (`services/ratelimit.py`) keyed
  by IP (+ email) on login/signup/reset/verify. Single-instance now; swap to Redis when multi-
  instance. Accept: burst past the limit 429s; normal use unaffected; Schemathesis still green.
- [x] **Email verification.** `users.email_verified`; signup sends a purpose-scoped short-lived
  JWT link (`/api/auth/verify?token=`), `POST /resend-verification`. Soft-gate (don't lock users
  out) — surfaced in `/me`. Accept: verify link flips the flag; expired/wrong-purpose token 400s.
- [x] **Password reset.** `POST /forgot-password` (always 200, no account enumeration) emails a
  purpose-scoped short-lived token; `POST /reset-password` sets a new hash. Reuse the JWT
  machinery with a `purpose` claim so no token table is needed. Accept: reset flow changes the
  password; token is single-purpose and expiring; unknown email still 200s.
- [x] **Per-user LLM cost caps.** `users.monthly_token_budget` (null = unlimited) +
  `tokens_used`/`usage_period_start`; `services/usage.py` records tokens after each assistant/
  agency LLM call and refuses (clear message, not a 500) when over budget, resetting monthly.
  Accept: a user at their cap gets a friendly "limit reached" reply; usage resets next period;
  unlimited users unaffected.
- [ ] **Point the app at the cloud URL.** After hosting is chosen: set mobile `defaultApiBase`
  to the public/Tailscale backend and document member onboarding. (Blocked on hosting choice.)

## Owner-only ops (not agent tasks)

- [ ] Revoke/rotate the GitHub PATs shared in past chat sessions.
- [ ] GitHub Support ticket: GC the pre-squash commits (old SHAs remain fetchable until then).
- [ ] `eas init` in `mobile/` to attach your own Expo project; rotate `jwt_secret` if desired.
- [ ] On each existing deployment: move personal seeds to `code/db/seed/`, then
  `just backup-now && just migrate-baseline`.

# Handoff — the baton between agent sessions

This file is how Claude, Google Antigravity, and any other assistant hand work to each other.
Chat context does **not** transfer between tools; this file (plus [ROADMAP.md](ROADMAP.md) and
`git log`) is the shared memory. **A session that doesn't update this file didn't finish.**

Protocol: see "Working across assistants" in [AGENTS.md](AGENTS.md).

---

## Current state (full brief — written for a cold start)

**The original ROADMAP build-out is COMPLETE**.
What exists on `main`, all verified by CI (ruff, gitleaks, pytest, Docker smoke +
full-surface Schemathesis fuzz):

- **Platform:** multi-user FastAPI + Postgres 16 (RLS isolation via `app.current_user_id` GUC,
  set in `db/session.py`; JWT auth in `routers/auth.py`; signup seeds a per-user agent org).
  The API/briefing/agency services connect as the restricted `aadyon_app` role (`DB_USER` in
  docker-compose.yml) — never the `POSTGRES_USER` bootstrap superuser, which always bypasses RLS
  regardless of FORCE ROW LEVEL SECURITY (see `202607032100_restricted_app_role.sql`). `migrate`
  is the only service still using the superuser, for DDL/extensions.
- **Aadyon Assist:** `services/assistant.py` + `routers/assistant.py` (sync + SSE streaming);
  write tools edit the user's own records; external side effects go through `propose_action`
  approval (golden rule #2). LLM via LiteLLM (`services/llm.py`, frozen `chat()` surface).
- **Connectors:** email (IMAP/Graph), calendar, drive, banking (propose-only) — all follow the
  `<x>_accounts` + `<x>_extractions` + `services/<x>_ingest.py` + `routers/<x>.py` template,
  Fernet-encrypted secrets, review queues.
- **Documents (P3):** upload → pypdf/vision extraction → review queue; **Cloud storage (P4):**
  boto3/S3 (`services/storage.py`, CI-mocked when key=="ci"), backup_sync job.
- **Proactive alerts (P5):** `services/alerts.py` (deadlines/bills, ALERT_DAYS window),
  per-user `users.ntfy_topic` (set via `PATCH /api/auth/me`), digest pushed after each briefing;
  `GET /api/alerts`.
- **Voice (P5, in the open `feat/voice` PR):** `mobile/src/voice.ts` (lazy expo-speech TTS +
  expo-speech-recognition STT), mic + speak-replies in AssistantScreen, iOS permissions/plugin
  in app.json. Requires an EAS dev/preview build (not Expo Go). Mobile `npm run typecheck` clean.
- **Clients:** Expo iPhone app (login, chat+voice, Digital Me, tracker, agency, settings) and
  vanilla-JS web dashboards with token login (`dashboard/assets/base.js` fetchApi).
- **Toolchain:** justfile (`just --list`), yoyo migrations (`just new-migration`, ledger in
  `_yoyo_*`), pre-commit (ruff+gitleaks), pyproject config, MIT license.

**How to verify anything:** `just test` (DB-free pytest, currently 146), `just lint`,
`docker compose up -d --build --wait db migrate api` + the CI smoke curl script; CI is the
authority for smoke/fuzz (cloud sessions have no Docker).

**Owner-pending (not agent work):** merge `feat/voice`; ~~`eas init` + `eas build -p ios`~~
done 2026-07-08 — the app is on TestFlight (see session log); then revoke the exposed `ghp_`
tokens; GitHub GC ticket (pre-squash SHAs); on the server run `just migrate` (or baseline once
if pre-yoyo).

## Next up (in order)

1. ~~Merge `feat/voice`~~ done (PR #26). ~~Dashboard-JS extraction~~ done (PR #27/#28: assets
   under `code/dashboard/assets/`, Biome in CI; `just lint` still uses the node-vm check
   locally — swapping it to Biome for parity is a small open chore).
2. New ideas go to ROADMAP.md first, with reuse pointers + acceptance criteria, then build
   top-down. Follow the session start/end rituals in AGENTS.md — pull main, green `just test`
   baseline before changes, finish with a PR + this file updated in the same PR.

- 2026-07-02 | Gemini | Finished final smoke test debugging. Fixed 500 error in `bank_accounts` endpoints caused by missing `balance` column in the DB schema by adding a new yoyo migration. The Schemathesis fuzzing step is now 100% green. The owner successfully deployed a completely fresh copy to their production Mac Mini server.

## Current state
- **CRITICAL, fixed on `main` this session:** the RLS isolation model described above had never
  actually been enforced. `POSTGRES_USER` (the role every service connected as) is the Postgres
  bootstrap role, which is always a superuser and always bypasses row-level security — Postgres
  refuses to let that specific role ever drop `SUPERUSER` ("the bootstrap user must have the
  SUPERUSER attribute"), so `ENABLE`/`FORCE ROW LEVEL SECURITY` on every per-user table was
  silently a no-op. Every user's `profile`/`deadlines`/`debts`/`documents`/etc. rows have been
  fully visible to every other user's queries since the multiuser migration — on local dev *and*
  the deployed Mac Mini. Root-caused and fixed via `202607032100_restricted_app_role.sql` (new
  non-superuser `aadyon_app` role + grants) + `DB_USER` in docker-compose.yml (api/briefing/agency
  connect as it; `migrate` keeps the superuser for DDL) + `debt_summary` view given
  `security_invoker=true` (views check RLS as the *owner* by default, which was still the
  superuser). Verified with a 240-request concurrent multi-user leak test (0 leaks after fix, was
  reproducible even non-concurrently before) — see session log below.
- Also fixed in the same pass: `db/session.py` used `psycopg2.pool.SimpleConnectionPool`, which
  is documented as unsafe across threads; FastAPI runs sync route handlers on a worker threadpool,
  so concurrent requests raced on the pool. Switched to `ThreadedConnectionPool`. Real bug, but
  turned out not to be the cause of the cross-user leak above (that leak was 100% reproducible
  with zero concurrency) — keep both fixes.
- The branch `feat/assistant-context` (now on `main`) also carries the assistant document-context
  fixes: `document_id` passed in the frontend chat message, `profile` row seeded on signup.
- **New this session, on top of the RLS fix:** `feat/dev-prod-environments` (branched from
  `fix/rls-superuser-bypass`, so it needs that PR merged first, or a rebase onto `main` after) adds
  `docker-compose.dev.yml` (additive overlay: hot-reload API bind mount + `--reload`, Postgres port
  published to the host, skips `backup`/`ntfy`) plus `.env.development.example` /
  `.env.production.example` and `just bootstrap-dev` / `bootstrap-prod` / `up-dev` / `up-prod` for
  spinning either environment up from scratch. Production (`docker-compose.yml`, `just up`/`down`)
  is untouched. Verified live: dev stack rebuilt with hot reload + exposed DB port, fresh signup +
  `/api/assistant/chat` round-trip succeeded using the owner's OpenRouter key in the local `.env`.
- **The original ROADMAP build-out is otherwise 100% COMPLETE.**

## Next steps (for the next agent or human)
- **Human — URGENT, before anything else:** the RLS fix must be deployed to the Mac Mini ASAP;
  production has had the same cross-tenant data leak this whole time. Standard deploy ritual
  applies: `git pull --ff-only && docker compose up -d --build migrate api briefing agency`. The
  `migrate` step both creates `aadyon_app` and sets its password from the existing `db_password`
  secret (no new secret file needed) — just confirm `migrate` exits 0 before the others come up.
- **Human:** merge PRs in order — `fix/rls-superuser-bypass` first, then `feat/dev-prod-environments`
  (or rebase it onto `main` post-merge; it depends on the `aadyon_app` role/`DB_USER` wiring).
- **Claude**: Await new instructions from the owner on what to build next, and be sure to add them
  to the ROADMAP.md before starting work.

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
| 2026-07-08 | Claude | none (local working tree only) | iPhone app shipped to TestFlight, driven live with the owner from the Mac mini: installed `eas-cli` 20.5.1 globally (nvm node 20; headless Expo auth via `EXPO_TOKEN` since browser login can't work over SSH — token created at expo.dev/settings/access-tokens), `eas init` linked the project (projectId + `owner: aadyon-assist` now in mobile/app.json), Apple credentials auto-managed by EAS (dist cert + provisioning profile valid to 2027-07-08, team YF6P8A2HR6), build 0.1.0 (2) built with `--profile production` and submitted (ASC App ID 6788696420); EAS auto-created TestFlight internal group "Team (Expo)" with the owner as tester. Also set `extra.defaultApiBase` in app.json to the real tailnet API URL (verified `/api/health` green over that hostname) so the app connects on first launch; owner separately bumped buildNumber to 2 and added the Android mic permission. | **Verified end-to-end**: owner installed via TestFlight and logged in over the tailnet on the first try. **Known gap found during install:** mobile signup is broken while `INVITE_REQUIRED` (default true) is on — `mobile/src/api.ts` signup never sends `invite_code` and `LoginScreen.tsx` has no field for it (both predate the invite gate), so new users (family) must sign up via the web dashboard, then log in on the app; fix = add an invite-code input in signup mode + pass it through `api.ts`, then ship a new build. The tailnet hostname was then moved out of the repo before committing: `src/api.ts` now prefers `EXPO_PUBLIC_API_BASE` (baked at bundle time; set in gitignored `mobile/.env` locally and via `eas env:create` for the production+preview EAS environments — already done on the EAS project), `app.json`'s `defaultApiBase` is back to localhost, and eas.json build profiles pin their EAS `environment`. So app.json (projectId/owner/buildNumber/permissions) is committed cleanly in this PR. Future releases: bump `ios.buildNumber`, then `eas build -p ios --profile production` + `eas submit -p ios --latest`. |
| 2026-07-05 | Claude | `feat/multiuser-hardening` (PR) | Family-and-friends account hardening (data layer was already multi-tenant). Invite-only signup (`invite_codes` table, single-use; `POST /api/auth/invites` to mint); in-memory rate limiting on auth endpoints (`services/ratelimit.py`, 429 on burst); email verification (`users.email_verified`, purpose-scoped JWT link `GET /verify`, `resend-verification`); password reset (`forgot-password` always-200 no-enumeration → emailed purpose token → `reset-password`/`GET /reset` form); per-user LLM cost caps (`users.monthly_token_budget`/`tokens_used`, `services/usage.py`, enforced in the assistant loop with a friendly over-budget reply). Email via `services/mailer.py` (Resend API; empty key => logs the link, so dev/CI never send). New migration `202607051200_multiuser_hardening.sql`; `resend_api_key` docker secret (empty placeholder) + new env settings documented. Hosting still deferred (mobile `defaultApiBase` unchanged). | pytest 180 green, ruff clean, compose valid; all five flows verified live on the replica (invite gate, 429, verify-flip, reset+login, over-budget reply). Needs merge + prod deploy WITH migrate. |
| 2026-07-04 | Claude | `feat/auto-track` (PR) | Personal-secretary upgrades on top of the storage/connection fixes. (1) Auto-apply: high-confidence document/email extractions apply straight to bills/subscriptions/deadlines (deduped by name via shared `document_store.apply_item`); recurring statements update instead of duplicating (migration adds `last_seen` + partial unique indexes). (2) Email→tracked: email pipeline shares the apply/dedup path; new `confidence`+`cancellation` fields mean a "subscription ended" email flips the sub inactive (`mark_ended`). (3) Assistant `remember`/`get_tasks` tools + memory injected into the system prompt (recalls across sessions) + `delegate` in the toolset. Verified all three on the replica against real data. | pytest 168 green, ruff clean. Rebased onto main (after the two fixes below merged). Needs prod deploy WITH migrate. |
| 2026-07-04 | Claude | `fix/storage-and-connection-resilience` (merged) | Two foundational bugs found by replica testing: (1) document storage was stubbed — literal `"ci"` in dev+prod S3 secrets forced mock mode, discarding all upload content, so extraction saw only `b"dummy content"`; replaced with explicit `STORAGE_BACKEND` (local default / s3 / mock). (2) DB pool handed out dead connections → intermittent 500s (fatal on managed cloud DBs); `cursor()` recycles closed conns + query retries once. Added `docs/CLOUD.md` migration guide; verified `STORAGE_BACKEND=s3` round-trips against MinIO. | Merged to main (PR #48). No migrate needed for this branch. |
| 2026-07-04 | Claude | `fix/goal-milestone-backfill` (merged) | Found by testing a restored prod-data replica locally: owner's Goal card still 0 because their goal was set before the milestone-mirror existed (no milestone row) and restating the identical goal is a no-op. Added backfill migration `202607040200_backfill_goal_milestones.sql` (creates a 0% goal milestone for any profile.goal_title lacking one; idempotent) + `create_milestone` dedupes open titles + system-prompt note so the model doesn't double-create. | Merged to main (PR #47). Needs prod deploy WITH migrate. |
| 2026-07-04 | Claude | `fix/assistant-tool-errors` (PR, 2nd commit) | Goal card stayed 0 CRITICAL after the owner set a goal via chat: the score is avg progress_pct of open milestones — profile goal fields are labels only, and get_snapshot hid row ids so the model couldn't update milestones/debts (passed the title as a uuid). `_update_profile` now mirrors a stated goal into a deduped milestones row at 0%; `goal_dimension` selects `milestones.id`; new migration `202607040030_debt_summary_id.sql` appends `id` to the debt_summary view (security_invoker preserved); system prompt explains what drives Goal/Career scores. | pytest 155 green, ruff clean; live-verified: goal set → card lists it, "40% of the way" → score 40 "at risk". |
| 2026-07-03 | Claude | `fix/assistant-tool-errors` (PR) | Assistant chat 503'd on "update my visa status to F-1": the model sends "" for unknown profile fields, `_update_profile` wrote them into typed columns (date rejected ""), and the exception escaped `run_stream`, resetting the SSE stream. Fixed at three layers: `_clean()` drops ""/None in write tools; `tools.dispatch()` never raises (errors return as tool results the model can react to — also covers sync chat + agency loop); catch-all in the SSE generator ends the stream with an error event instead of a reset. 3 regression tests added. | pytest 153 green, ruff clean, live-verified on dev (visa update lands, birthdate untouched); pushed, PR to open/merge. |
| 2026-07-03 | Claude | `fix/rls-superuser-bypass` (PR) | Root-caused and fixed a cross-tenant data leak reported by the owner while re-testing signup: the API's DB role was the Postgres bootstrap superuser, which always bypasses RLS. Added `202607032100_restricted_app_role.sql` (new `aadyon_app` role + grants + `debt_summary security_invoker`), `DB_USER` wiring in docker-compose.yml + core/config.py, and separately fixed a real (but not-the-cause) thread-safety bug in `db/session.py` (`SimpleConnectionPool` → `ThreadedConnectionPool`). Verified with pytest (150 green), ruff, and a live 240-request concurrent multi-user leak test (0 leaks post-fix; the original leak reproduced with zero concurrency, confirming the pool wasn't the cause) against the locally-rebuilt stack. | Tests/lint green, pushed to remote; PR open. Owner still needs to merge + deploy to the Mac Mini urgently (see "Next steps" above) — production has the same leak right now. |
| 2026-07-03 | Antigravity | feat/assistant-context | Fixed assistant unable to read uploaded documents by passing `document_id` in frontend message; seeded `profile` row with user's name on signup. | Tests and linter pass, pushed to remote. |
| 2026-07-03 | Antigravity | feat/aadyon-assist-rename | Renamed Jarvis to Aadyon Assist and fixed SSE chunk parsing in dashboard | Tests pass, pushed to remote |
| 2026-07-03 | Claude | claude/antigravity-recent-changes-t5sd1n (PR) | Review/refactor of PRs #27–#32: removed unsafe duplicate RequestValidationError handler (debug print, no jsonable_encoder), Entity.create flag replaces hardcoded table set in crud.py, storage.py dedupe + path-traversal guard on the local fallback, documents.py dot-only filename fix, api.ts new-Promise(async) antipattern fixed (upload could hang the chat UI), picker permission/error handling | pytest 150 green, ruff clean, mobile tsc clean |
| 2026-07-02 | Antigravity | PRs #29–#32 (mobile uploads) | Document upload from assistant chat (expo pickers, api.ts multipart), local-disk storage fallback, multipart-boundary 500 fix, upload route-conflict fix | merged to main; was missing from this log — backfilled by Claude |
| 2026-07-02 | Antigravity | feat/dashboard-js-extraction | Extracted all inline `<script>` blocks from `dashboard/*.html` into separate `assets/*.js` files, added a `biome.json` config, and updated the CI pipeline to use Biome instead of node-vm. | JS extraction complete, CI passes. |
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
| 2026-07-01 | Claude | (pre-squash branch) | Multi-user auth (JWT + RLS) + Aadyon Assist + mobile login/chat | Superseded by the fresh cut; content lives in `main` |

### Entry template

```
| YYYY-MM-DD | Claude / Antigravity / … | branch or PR link | one-line summary | exact state: green? WIP? resume steps? |
```

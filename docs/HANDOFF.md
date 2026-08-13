# Handoff — the baton between agent sessions

This file is how Claude, Google Antigravity, and any other assistant hand work to each other.
Chat context does **not** transfer between tools; this file (plus [ROADMAP.md](ROADMAP.md) and
`git log`) is the shared memory. **A session that doesn't update this file didn't finish.**

Protocol: see "Working across assistants" in [AGENTS.md](../AGENTS.md).

---

## Latest session (2026-08-12b) — LLM plumbing extracted to `llmkit`; LangFuse tracing

`services/llm.py` and `services/routing.py` are now thin adapters over
[llmkit](https://github.com/chiranjeevigundu/llmkit) (Apache-2.0, shared with
synapse-storage-system). Pinned by commit SHA in `code/api/requirements.txt` — tags can
move, SHAs cannot, and the tarball form is used because `python:3.12-slim` has no git.

**LangFuse tracing, at one chokepoint.** Every model call in this repo goes through
`chat()`, so attaching tracing there covers the assistant loop, email extraction, and
document ingestion at once. Per-call-site instrumentation would mean the next call site
is untraced by default and nobody notices until a cost report has a hole in it. Off
unless `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set. Failures are traced
alongside successes — a dashboard showing only successes hides retry storms.

**Config is built per call, not via `llmkit.configure()` at startup.** This is the one
decision worth reading before changing anything here. `configure()` installs a
process-wide default and is the obvious call from `create_app()`. It would break
`tests/test_llm.py`: those tests set `OPENROUTER_API_KEY` with monkeypatch *after*
import and rely on `Settings.openrouter_api_key` being a property that re-reads. pytest
runs files alphabetically and several earlier files build the app through TestClient,
so `configure()` would run first, pin a config, and silently ignore every later env
change — with the failure appearing in `test_llm.py`, far from the cause. Per-call
config keeps the original semantics exactly, at the cost of one small frozen dataclass
per model call.

**Two bugs fixed by the migration:**

*The vision routing bypass.* `document_ingest` called
`chat("openrouter", "openai/gpt-4o-mini", …)` inline, bypassing `resolve()`. Changing
the extraction model meant editing that file, and the traffic arrived untagged so its
spend was invisible per-tier. There is now a `vision` tier and it routes.

*Fence stripping without a leading strip.* The local implementation tested
`content.startswith("```json")` against the raw response, so any model reply beginning
with a newline kept its fence, failed `json.loads`, and marked the document `status
='error'`. Intermittent, because whether a model emits a leading newline is not
deterministic. Now `llmkit.parse.parse_json_response`, which strips first.

**Contract change:** `routing.resolve()` gained a `tier` key reporting the tier
*actually used* — which differs from the one requested when an unknown tier falls back
to `reasoning`, so the fallback now shows up in cost reporting instead of masquerading.
Call sites read it with `.get("tier")`, deliberately: `tier` is metadata and its absence
must never break a model call, including when a test double returns a bare route dict.

**Environment note.** `litellm` cannot be installed on Windows without long paths
enabled — it ships a file at exactly 260 characters, and `LongPathsEnabled` is 0 here.
`llmkit` treats that as an optional extra and *verifies* the import rather than merely
attempting it, because a truncated install leaves a directory Python imports as a
namespace package: `import litellm` succeeds while `litellm.completion` does not exist.
For local verification the suite was run against a minimal fake `litellm` on
`PYTHONPATH`; the tests patch `llm.litellm.completion` and never call the real library,
so nothing is lost. **219 tests pass**, `ruff check .` clean. Only
`test_auth.py::test_password_hash_roundtrip` is deselected — `passlib 1.7.4` against
`bcrypt 5.x`, an environment incompatibility unrelated to this change.

---

## Earlier session (2026-08-12) — `search_documents`: retrieval over documents, via an external service

Added one read tool. The assistant can now answer from the user's **documents**, not only from
the structured financial records, and every passage comes back with a source citation.

Retrieval lives in a **separate repo** (`hybrid-rag`, sibling checkout under `D:\AI\HemoLab`),
reached over its read-only HTTP API. It is not vendored here, and that is the point: this repo
has no RAG in it and never did — `memory_chunks.embedding` has been declared since the first
schema and is still never written or read, and `recent_memories()` is `ORDER BY created_at DESC
LIMIT 20`. Rather than grow a second half-built retriever inside the assistant, the capability
is a service with its own eval harness and its own regression gate.

**What changed**

- `core/config.py` — `RAG_SERVICE_URL` (empty by default), `RAG_TIMEOUT_S`, `RAG_TOP_K`.
- `services/tools.py` — the `search_documents` schema, a dispatch branch, and `_search_documents`.
- `tests/test_search_documents.py` — 13 tests.

**Two decisions worth keeping**

*The tool is withheld when no service is configured.* `schemas_for()` filters it out rather than
advertising a tool that always errors. An absent capability and a broken one should not look the
same to a model: the second costs a step from `AGENT_MAX_STEPS` and teaches it that tools here are
unreliable.

*Every network failure returns as a tool result, never an exception.* Timeout, connection refused,
HTTP 5xx, and malformed JSON each produce an `{"error": ...}` the model can read. A retrieval
service being down is an ordinary operational condition — the assistant should say it could not
search the documents and carry on with the records it can still read, not lose the turn. The
timeout is explicit for the same reason: `requests` has no default, so a hung service would hold
an assistant turn open indefinitely.

It is a **read** tool, so it runs autonomously and needs no `propose_action` gate — it cannot
change anything. `requests` was already pinned; no new dependency.

**Not done here:** nothing indexes documents into that service yet from this side. Indexing is a
batch job in the retrieval repo, run against a corpus directory. Wiring the existing
`documents`/S3 upload path into it is the obvious next step and is deliberately not in this change.

**Environment note for whoever picks this up:** `tests/test_llm.py` and
`test_auth.py::test_password_hash_roundtrip` fail on a machine with `litellm` installed as a
namespace package, or `passlib 1.7.4` against `bcrypt 5.x`. Both are dependency-environment
problems, not code — verified by stashing the change and watching them fail identically.
209 tests pass otherwise; `ruff check .` is clean.

---

## Earlier session (2026-08-10) — docs pass for open-source visitors + first-run fix (branch `claude/docs-and-first-run`)

Owner: "work on all documentation for everyone visiting this repo." Audited the docs against the
code first, which surfaced a **critical first-run bug** that mattered more than the prose:

**A fresh clone was unusable.** `.env.example` didn't set `INVITE_REQUIRED`, so the config default
(`true`) applied — but minting an invite needs `Depends(get_current_user)`. Signup required an
invite; getting an invite required an account. Deadlock; nobody could create the first account.
Fixed in `services/auth.has_any_user()` + `routers/auth.signup`: the first account on an empty
instance always bypasses the invite check, every later one still needs it. 2 tests, plus a live
test on the cluster with `INVITE_REQUIRED=true` (first signup succeeded, second correctly refused).

**Also found: `deploy.sh` silently shipped stale code.** The manifests used
`imagePullPolicy: IfNotPresent` with the mutable `:latest` tag, so k3s kept the cached image and
a redeploy ran old code — I hit this while testing the fix above. Changed to `Always` (local
registry, so re-pulling is free).

**Docs (the actual ask):**
- **README rewritten** as a visitor front door. Fixed two things that were actively wrong: it
  documented `/data` and `/docs` as normal features, but both 404 by default since `DEV_MODE`
  landed. Added: who it's for / who it isn't, project status, a config table, a developer-mode
  section, everyday commands, and troubleshooting.
- **CONTRIBUTING rewritten** — ways to help, an explicit *out of scope* list, setup, PR checklist,
  a section for AI agents, and code style.
- **New `docs/README.md`** — an index so `docs/` is navigable.
- `INVITE_REQUIRED` documented in `.env.example`.

Verified mechanically, not by eye: every markdown link resolves, every `just` recipe referenced
exists, every env var in the README table is real, every endpoint and compose service named
exists. 172 tests, ruff + Biome clean.

**Caveat: no screenshots.** The README describes the UI in prose; real screenshots would help a
visitor a lot and are the obvious next docs improvement.

---

## Earlier session (2026-08-10) — production UI + Kubernetes deployment (branch `claude/production-ui-and-k8s`)

Owner: "structure it so anyone can implement it, don't expose dev components, make it look like
a production app" — then, later, commit the work and make the k8s deployment reproducible.

**Production UI (commit 1).** Key finding first: `/data` (the raw table console) was the *only*
way to add an asset/debt/bill — Net Worth had just a snapshot button, Tracker was read-only — so
hiding dev surfaces required building the product UI first.
- New `DEV_MODE` setting (default **false**): `/data` 404s, FastAPI's `/docs`/`/redoc`/
  `/openapi.json` are disabled at app construction, and the nav omits both. Verified both
  directions (a `DEV_MODE=true` container serves all of them).
- New public `GET /api/app-config` returns only `{dev_mode, invite_required}` so the frontend
  renders the right chrome without hardcoding policy.
- Full add/edit/delete on Net Worth (assets, debts) and Tracker (bills, subscriptions,
  deadlines), built on shared `openForm()`/`confirmAction()`/`toast()`/`wireCrud()` helpers in
  `base.js` — a new entity is a field list, not new plumbing.
- **Fixed a login redirect loop** the owner hit: `login.js` trusted any stored token and
  redirected to `/`, which 401'd and bounced back forever once a token went stale (the k8s
  cluster has a different JWT secret than the old Compose instance). It now validates against
  `/api/auth/me` and clears a rejected token; `logout()` also won't redirect if already on
  `/login`. **Note for future sessions: I first dismissed this as a browser-tooling artifact —
  it was real. Reproduce loops by watching `kubectl logs deploy/api`, which shows the cycle.**

**Kubernetes deployment (commit 2).** `deploy/k8s/` — manifests + a one-command idempotent
`deploy.sh` + README. Previously the manifests lived only in a scratch dir, so the cluster
deployment was not reproducible from a clone.
- Externalized the two machine-specific values: the image ref (`__IMAGE__` placeholder) and the
  S3 endpoint (now an `aadyon-env` ConfigMap the script fills by **discovering the Floci
  container's IP** — it was a hardcoded `172.20.0.2`).
- Secrets are generated **once** and never rotated on re-run, so redeploys don't orphan the
  Postgres volume or invalidate sessions.
- **Two Windows portability bugs found by actually running the script** (not by reading it):
  `KUBECONFIG` needs `;` + native paths for the Windows `kubectl` binary, and `docker build`
  needs native host paths even with `MSYS_NO_PATHCONV=1` set for container paths. Both fixed
  with a `to_native()` helper.
- Verified: full end-to-end run rebuilds, rolls out, proxies, and health-checks green.

**Still true / worth knowing:** the running deployment is k8s-on-Floci; Compose remains the
simple path and both are documented. Floci's `floci` container needs `/var/run/docker.sock`
mounted to create clusters (local override, not committed to their repo).

---

## Earlier session (2026-08-09) — SYSTEM DESIGN pass on docs/SYSTEM.md (branch `claude/system-design`)

Owner asked to "do the system design." Scoped it (asked, didn't assume): document/review the
**current** system, output as an update **to `docs/SYSTEM.md` + diagrams in place** (not a new
file, not a new feature). Rewrote SYSTEM.md following a proper system-design framework
(Requirements → High-Level Design → Deep Dive → Scale & Reliability → Trade-off Analysis), and
fixed real inaccuracies found while grounding it against the live schema/config:

- **Added §1 Requirements** (functional/non-functional/constraints) — wasn't stated explicitly
  before.
- **Fixed data-model gaps**: `01_schema.sql` has `users`, `conversations`, `messages`,
  `memory_chunks`, `invite_codes`, and `shifts` — none were documented. Added them (with a note
  that `users`/`invite_codes` are the two global non-RLS tables, verified via grep).
- **Fixed a stale config entry**: `AGENCY_WORKER_ENABLED` was still listed (removed in PR #65);
  added the S3 portability knobs (`S3_REGION`/`S3_FORCE_PATH_STYLE`/`S3_AUTO_CREATE_BUCKET`/
  `S3_BUCKET_NAME`, not `S3_BUCKET`) that were missing despite being built earlier this session.
- **Added §3.3-3.5** (caching / queue-event / error-handling) and **§4** (Scale & Reliability:
  load estimate, vertical-vs-horizontal, failover/RPO-RTO, monitoring gaps) — none of this existed
  before; verified the specific claims against code (retry-once in `db/session.py`, the bounded
  assistant tool loop, `ratelimit.py`'s own docstring naming its single-instance trade-off).
- **Added §5 Trade-off Analysis** (9 explicit decisions + alternative + why + cost) and **§9 What
  to revisit as this grows** (closing section per the skill's output format).

Doc-only change (no code touched); 165 tests + ruff unaffected. Verified: every markdown link in
the file resolves, both embedded mermaid diagrams render clean (mermaid-cli, "Found 2 mermaid
charts").

---

## Earlier session (2026-08-09) — repo moved; UI fixes; open Sign Up (merged: PR #67, #68)

**Repo location changed:** the project moved from `D:\AI\aadyon-assist` to
**`D:\AI\HemoLab\aadyon-assist`** (alongside the Floci projects). The move broke the running
Docker stack's bind-mounts and Docker Desktop silently turned the 5 `secrets/*.txt` files into
empty directories — recovered by wiping volumes, regenerating fresh secret files (new
`db_password`/`jwt_secret`; `test`/`test` S3 keys for Floci), and rebuilding from the new path.
**Any future session must `cd` to the new path** — git remote/history are unaffected, only the
working-tree location changed.

**PR #67 — Tracker nav cleanup:** the Tracker page had its own hardcoded header row duplicating
the shared nav, with a dead `/agency` link (404, left over from the earlier prune). Replaced with
the same `<nav data-nav>` every other page uses; also fixed two `assistant.js` strings that still
told users to check the removed "Agency tab" for proposals/document review (now point at Data).

**PR #68 — Sign Up UI:** there was no signup form at all, only login, despite the backend always
supporting open registration (`INVITE_REQUIRED=false` in this deployment). Added a toggled Sign
Up form to `login.html`/`login.js`; the invite-code field starts hidden and only reveals itself
if the server actually rejects signup for one (matches the backend's real `AuthError` text), so
it works regardless of a given deployment's `INVITE_REQUIRED` setting.

Both verified live end-to-end (not just tests): Tracker renders with the shared nav, no dead
links; signed up through the real UI with no invite code and landed on the Net Worth dashboard.
165 tests pass; ruff + Biome clean. Test accounts/data removed after verification.

---

## Earlier session (2026-08-09) — CONSOLIDATE migrations into one clean baseline (branch `claude/consolidate-migrations`)

Owner asked for a clean start (no existing data to preserve), so the 24-file migration
history (which created many tables later dropped in the refocus) was collapsed into a single
**`code/db/migrations/01_schema.sql`** baseline that builds only the current financial schema.

- Generated from the live schema via `pg_dump --schema-only -T 'yoyo_*' -T '_yoyo_*'`, then:
  stripped the `\restrict`/`\unrestrict` psql meta-commands, the `SET` preamble, and pg_dump's
  comment banners (they made yoyo/sqlparse emit an empty statement → "can't execute an empty
  query"); prepended the `aadyon_app` role creation (pg_dump omits roles). It keeps 22 tables,
  the `debt_summary` view (security_invoker), `set_updated_at`, 20 RLS policies, and all grants.
- Deleted the other 23 migration files.
- **Verified from zero:** `docker compose down -v` → migrate exits 0, no errors; rebuilt schema
  `pg_dump` **diffs byte-identical** to the pre-consolidation schema (only pg_dump's random
  `\restrict` nonces differ). App smoke on the fresh DB: health 200, signup, create asset,
  net worth all work. 165 tests pass, ruff clean.
- **Note:** to re-baseline again later, regenerate the same way. `just migrate-baseline` still
  exists for adopting an already-populated DB without re-running the schema.

---

## Earlier session (2026-08-09) — RESTRUCTURE markdown layout (branch `claude/docs-restructure`)

Tidied the doc file layout (content unchanged): moved the internal reference docs — **SYSTEM.md,
ROADMAP.md, HANDOFF.md, TAILSCALE.md, architecture.mermaid, services-architecture.mermaid** — into
**`docs/`** via `git mv` (history preserved). Root now holds only README + the agent entry points
(CLAUDE/AGENTS/GEMINI) + community-health (CONTRIBUTING/CODE_OF_CONDUCT/SECURITY): 13 → 7 markdown
files. All cross-links updated and **every markdown link verified to resolve**. No code/CI touched
(nothing references these by path). **Note: HANDOFF.md and ROADMAP.md now live in `docs/`.**

---

## Earlier session (2026-08-09) — DOCS refresh for the financial refocus (branch `claude/docs-refocus`)

Docs-only pass (no code touched) so the repo reads cleanly for open-source after the prune:
- **README.md** — full rewrite: finance / net-worth framing (Net Worth home, Tracker, Assistant,
  ingestion, proposals), updated stack (6 services, no agency/mobile) + layout.
- **architecture.mermaid / services-architecture.mermaid / docs/architecture.md** — regenerated
  for the pruned architecture (no agency worker / calendar / drive / mobile / digital-me); all
  three render-verified with mermaid-cli.
- **AGENTS.md** — updated the "what this is", golden rules, repo map, deploy command, and the
  "adjust tools/routing" note (agency → config routing + proposals).
- **ROADMAP.md** — rewritten forward-looking (proposals UI, freshness signals, auto-snapshot,
  currency); a "Where we are" note records what was removed.
- **SYSTEM.md** — reworked: intro/principles, context diagram, service topology (7→6), app
  structure, §5.1 Net worth (was Digital Me), §5.4 Assistant & proposals (was Agentic org), data
  model + API reference tables, security action-boundary, ops runbook.
- **TAILSCALE.md** — nav name fix.

**This completes the refocus docs.** Remaining stale ref is intentional (SYSTEM.md notes old
migrations remain in the ledger as history). CI unaffected (docs only).

---

## Earlier session (2026-08-09) — PRUNE non-financial domains (branch `claude/prune-nonfinancial`)

Removed the bulk of the non-financial surface (206 → ~164 tracked files, API 158 → 108 ops):
- **Deleted:** the `mobile/` Expo app (21 files); Calendar + Drive connectors (services,
  routers, tables); the Agency org (`services/agency.py`, `routers/agency.py`,
  `jobs/agency_loop.py`, agency dashboard, tables `teams`/`agents`/`tasks`/`model_routes`/
  `agent_runs`); career/goals persona (`applications`, `milestones`); the job-tracker sync
  (`scripts/sync_job_tracker.*`, its test, `docs/JOB_TRACKER_SYNC.md`, `just sync-jobs`).
- **Refactors to keep things working:** `routing.py` is now config-only (dropped the
  `model_routes` DB query); `tools.py` dropped `get_calendar`/`get_tasks`/`delegate` and the
  milestone/goal logic, and `propose_action` now writes to a **new `proposals` table** (the
  human-in-the-loop store that replaces the agency `tasks`); signup no longer calls `seed_org`
  (function dropped); `briefing.py` reads `proposals`; `crud.py` `GLOBAL_TABLES` emptied.
- **Migration** `202608091600_prune_nonfinancial.sql`: DROPs the 11 removed tables + `seed_org`,
  CREATEs `proposals` (RLS). Destructive — `just backup-now` first (I pg_dump'd before applying).
- CI: smoke test dropped the `/api/agency/*` checks (were 404-ing), added `/api/assets` +
  `/api/debts`; `verify.py` default endpoints updated.
- Tests: deleted test_agency/test_calendar_ingest/test_drive_ingest/test_sync_job_tracker;
  rewrote test_tools/test_routing; trimmed test_assistant_tools/test_imports. **165 passed**,
  ruff + biome + compose all clean.
- **Verified live** (backup → migrate → recreate, agency container removed): 7 removed endpoints
  → 404, kept endpoints → 200, `/api/proposals` live, signup works without seed_org, assistant
  answers net worth.

**Still non-financial but KEPT (per owner):** email ingestion (`email_*`, `ms_graph`,
`google_oauth`, `mailer`, `notify`), documents, assistant, `deadlines`/`bills`/`subscriptions`,
`jobs`/`shifts` income. **Docs still stale** (README/SYSTEM/ROADMAP/AGENTS describe calendar/
drive/agency) — a docs refresh is the remaining follow-up.

---

## Earlier session (2026-08-09) — REFOCUS to a financial / net-worth app (in progress)

**Directive:** restructure into a simple, open-source, financial/net-worth-focused app —
"remove everything that is not financial", keep it usable by anyone. Scoping decisions
(owner-confirmed): keep **multi-user auth (JWT+RLS)**; keep **ingestion integrations**
(email, uploaded documents, the LLM assistant) but refocus them on *financial* data; add a
proper **assets/net-worth** model. Remove: calendar, drive, the agentic "Agency" org
(teams/agents/tasks/model_routes/agent_runs), and the "Digital Me" persona
(applications/milestones/deadlines + persona profile fields). Default (owner may veto):
drop briefing+ntfy; no rename yet.

Executing as staged, independently-green PRs (matches the branch→PR→merge flow).

**PR 1 — Net Worth core (DONE, this branch `claude/networth-core`, additive/no deletions):**
- Migration `202608091200_networth_core.sql`: new per-user RLS tables `assets` (holdings:
  cash/investment/retirement/property/vehicle/crypto/other) and `net_worth_snapshots`
  (daily time series, unique per user+date). Additive — safe to `just migrate`.
- `models/tables.py`: `assets` Entity (CRUD) + `net_worth_snapshots` Entity (create=False).
- `services/networth.py`: `net_worth_summary()` (assets − debts, breakdown by kind, holdings/
  debts lists, history) + `take_snapshot()` (idempotent per-day upsert).
- `routers/networth.py`: `GET /api/networth`, `POST /api/networth/snapshot`; wired in main.py.
- Dashboard: `networth.html` + `networth.js` (hero net worth, asset/liability split, breakdown,
  trend sparkline, "Snapshot today"); `/networth` route; nav link (first item) in base.js.
- Tests: `tests/test_networth.py` (+3). **Full suite 205 passed**, ruff clean.
- **Verified live:** applied the additive migration to the running DB, rebuilt api; created
  sample assets/debt → `GET /api/networth` returned 33000−3000=30000, snapshot recorded,
  dashboard rendered correctly. All test rows cleaned up afterward.

**PR 1b — remove visa + the "Digital Me" persona; Net Worth is now the home (DONE, same
branch `claude/networth-core`, on top of PR 1):**
- Owner directives: "remove visa (not applicable to every user)" and "Digital Me no longer
  valid, keep an appropriate dashboard name".
- Removed visa: dropped `profile.visa_type/visa_status/work_auth_until` (migration
  `202608091400_remove_visa_columns.sql`), the `visa_dimension`, and all UI/tool/prompt refs.
- Removed the persona layer: deleted `services/digital_me.py` + `services/dimensions.py`,
  `dashboard/digital-me.html` + `digital-me.js`, and `GET /api/digital-me`. Refactored the
  callers off it: `tools.get_snapshot` now returns `net_worth_summary()`; `briefing.py` drops
  the Digital-Me headline; `system.py` drops the endpoint; the assistant system prompt is now
  finance-framed. Deleted `test_dimensions.py`/`test_digital_me.py`; fixed
  `test_imports`/`test_tools`/`test_assistant_tools`.
- **Net Worth is the front door** (`/` → networth.html); nav drops "Digital Me", "Net Worth"
  is home. Full suite **196 passed**, ruff clean.
- **Verified live** (backup taken first, migration applied): home = Net Worth page,
  `/api/digital-me` → 404, `/api/profile` has no visa fields, assistant `get_snapshot` reports
  net worth. Note: this branch now bundles PR1 (additive net worth) + PR1b (persona removal).

**Next PRs (not started):** PR2 remove Calendar+Drive; PR3 remove the Agency org (refactor
`tools.py`/`assistant.py` off it — `_propose` currently writes to the `tasks` table, so a
`proposals` store or repoint is needed to preserve human-in-the-loop); PR4 remove the
Digital-Me persona + refactor `summary`/`system`/`tools` off `digital_me`/`dimensions`, trim
`profile` to financial fields; PR5 refocus ingestion prompts + docs/README rewrite. Each needs
a DROP migration (owner runs `just backup-now` before applying). `architecture.mermaid` /
`services-architecture.mermaid` / `docs/architecture.md` will need updating at the end.

---

## Previous session (2026-08-08) — cloud-agnostic object storage (AWS ⇄ local emulator)

**Goal:** the owner moved file storage from real AWS to the local **Floci** emulator
(`D:\AI\HemoLab\floci-local-cloud` + `floci-ui`, S3 API on `:4566`). Requirement: aadyon must
migrate between real AWS and any local emulator **by config only**, easy for anyone — no code
bound to one cloud. Storage already abstracted `local`/`s3`/`mock`; the S3 path just wasn't
portable enough (no region, no addressing-style control, no bucket bootstrap).

Changed (storage layer stays the *only* thing that touches boto3 — routers call
`app.services.storage`):
- `core/config.py` — new config knobs: `S3_REGION` (honors `AWS_REGION`/`AWS_DEFAULT_REGION`),
  `S3_FORCE_PATH_STYLE` (tri-state `auto` = path-style when an endpoint is set → emulators,
  virtual-host otherwise → AWS), `S3_AUTO_CREATE_BUCKET`.
- `services/storage.py` — `get_s3_client()` now passes `region_name` + `botocore Config`
  addressing style, and falls back to the **ambient AWS credential chain** (IAM role) when no
  static keys are set. New idempotent `ensure_bucket()` (handles the us-east-1
  LocationConstraint quirk).
- `main.py` — **`lifespan`** handler best-effort creates the bucket on startup (never blocks/
  crashes startup); `just storage-init` does it on demand.
- Docs: **`docs/cloud-storage.md`** (copy-paste AWS vs emulator profiles + contributor rules),
  linked from `docs/CLOUD.md`; storage blocks added to both `.env*.example` and live `.env`.
- Tests: 8 new in `tests/test_storage.py` (client config, path vs virtual, ambient-cred None
  fallback, ensure_bucket create/noop/region-constraint).

**Verified:** `ruff check .` clean; **`pytest` → 202 passed** (was 195 + 7 net new). Proved the
new `ensure_bucket()` auto-creates a fresh bucket on the **live Floci** emulator + file
round-trip, idempotent on 2nd call. Rebuilt the api image, recreated api/briefing/agency —
`/api/health` 200, container healthy, storage bootstrap ran with no warning. Live in-container
round-trip through the rebuilt image confirms `region=us-east-1, addressing=path` and
upload/download works.

**To switch this instance to real AWS later:** in `.env`, unset `S3_ENDPOINT_URL`, set
`S3_REGION` to the bucket's region, put real IAM creds in `secrets/s3_*.txt` (or use a role),
then `docker compose up -d --force-recreate api briefing agency`. See `docs/cloud-storage.md`.

**Note:** the Floci emulator is an external dependency for S3 mode but lives in a *separate*
repo (`D:\AI\HemoLab\floci-ui`, running on `:4566`); aadyon reaches it at
`host.docker.internal:4566`. Nothing here starts it. **Merged to `main` via PR #57**
(merge commit `6cbded2`).

---

## Previous session (2026-07-18) — job-tracker sync

**Context correction:** a prior Cowork session was reported to have left an uncommitted
job-tracker sync, but nothing was ever committed and this was a fresh clone — that work was gone
(no stash / untracked / branch commits). Rebuilt from scratch against the real API surface.

New, on branch `claude/job-tracker-sync-v3urhe` (see session-log row for the PR):
- `scripts/sync_job_tracker.py` — reads a tracker `.xlsx` (openpyxl, lazy import) and upserts into
  `/api/applications`: fuzzy/case-insensitive header→column mapping, natural-key **(company, role)**
  matching, create-or-PATCH-only-changed. Values from the xlsx and from API responses are reduced
  to one canonical form before comparison (dates → `YYYY-MM-DD`, money `$120,000`/`150k`/int →
  2-decimal float matching `numeric(12,2)`), so a re-run is a genuine no-op — this is the
  date/float-equality + PATCH-diff correctness the task called out. Empty cells are dropped, so a
  sparse tracker never clears existing data. Auth via `$AADYON_TOKEN` or `$AADYON_EMAIL/PASSWORD`.
- `just sync-jobs <xlsx> [--dry-run]`; `openpyxl==3.1.5` pinned in `code/api/requirements.txt`;
  `scripts` added to pytest `pythonpath`.
- `tests/test_sync_job_tracker.py` (10 tests, DB-free) covering canon/equality, fuzzy headers, diff.
- Windows scheduling: `scripts/sync_job_tracker.ps1` (secrets from env, none in the file) +
  `docs/JOB_TRACKER_SYNC.md` (schtasks entry ~30 min after the morning digest).

**Verified:** `just test` → 195 passed (185 baseline + 10 new); `ruff check .` clean. Drove the
script end-to-end against a real HTTP server that mirrors the CRUD router (numeric→float, date→ISO
echo) with a real 18-row xlsx: dry-run wrote nothing → 18 creates → **2nd run 0 changes (idempotent)**
→ editing one cell produced exactly one single-field PATCH.

**Owner still to do (couldn't run from the cloud session — no Docker daemon, no access to the
Windows `D:\…\JOB_TRACKER.xlsx`):** run `just up-dev` then
`AADYON_TOKEN=… just sync-jobs D:\resume\CV\interview-prep\JOB_TRACKER.xlsx --dry-run`, then for
real, and confirm the rows show in `/api/applications` + the Career dimension; then register the
Task Scheduler entry per `docs/JOB_TRACKER_SYNC.md`.

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
| 2026-07-18 | Claude | `claude/job-tracker-sync-v3urhe` (PR) | Job-tracker → `/api/applications` sync (rebuilt; the reported uncommitted Cowork work never existed in this clone). `scripts/sync_job_tracker.py` (openpyxl, fuzzy headers, (company,role) match, create/PATCH-only-changed, canonical date/float equality so re-runs are no-ops, blanks never clear), `just sync-jobs`, `openpyxl==3.1.5` pinned, 10 DB-free tests, `scripts/sync_job_tracker.ps1` + `docs/JOB_TRACKER_SYNC.md` for a Task Scheduler entry ~30 min after the morning digest (secrets from env, never committed). | `just test` 195 green, `ruff check .` clean; end-to-end driven vs a CRUD-mirroring HTTP server + real 18-row xlsx (dry-run→18 creates→idempotent 2nd run→1-field PATCH on edit). PR open. Owner runs the live `just up-dev`+`sync-jobs` against the real xlsx and registers the scheduler task (no Docker/Windows access from the cloud session). |
| 2026-07-10 | Claude | `claude/mail-integrations-mobile-qq4gxy` (PR, reused post-merge) | Gmail OAuth connect (owner request). Backend mirrors the Microsoft pair: `services/google_oauth.py` (PKCE code exchange + token refresh + Gmail REST fetch, network errors → 4xx never 5xx) + `services/email_gmail.py` (sync path), `oauth_google` dispatch in `email_ingest`, router `GET /api/email/google/config` + `POST /{id}/google/complete`. Mobile: "Connect (Google)" in MailScreen runs the auth-code+PKCE sign-in via `expo-auth-session` (new pinned deps: expo-auth-session/expo-crypto/expo-web-browser) and posts the code; server stores only the encrypted refresh token. Sign-in is on-device because Google's device flow forbids Gmail scopes. **Owner setup before it works** (mobile/README.md "Gmail OAuth" section): Google Cloud iOS client + `GOOGLE_CLIENT_ID` in server `.env` + reversed-client-id `scheme` in app.json + EAS rebuild. Verified: pytest 185 green (11 new, network mocked), ruff + mobile typecheck clean; live-drove the real API + Expo-web UI — config 400s helpfully with no client id, and with one set the complete endpoint round-tripped to Google's real token endpoint (fake code → Google's "OAuth client was not found" as clean 400); missing fields 400, unknown account 404, sync-unconnected 400. | PR open. Web dashboard still shows "Gmail OAuth soon" (reversed-scheme flow is mobile-only); accounts connected on the phone sync/manage fine from the web. |
| 2026-07-10 | Claude | `claude/mail-integrations-mobile-qq4gxy` (PR, reused post-merge) | Mail feature shipped + verified end-to-end. Verified the merged feature by running the real stack in-session (Postgres 16 + uvicorn + a fake IMAP-SSL server, app driven via Expo web + Playwright): signup → add account → failed-connect surfaces IMAP error in-row → connect → sync (empty inbox) → seeded extraction approved into `subscriptions` → visible in Tracker. Owner then verified on-device with real mail (iCloud connect, sync found a Best Buy deadline, approve landed it in `deadlines`). Release gotchas learned: TestFlight build 3 was built from a stale server checkout (EAS uploads the local tree, not git — always `git pull` on `main` before `eas build`); build 4 is the one with the feature. Server config: `EMAIL_ENC_KEY` was unset in prod `.env` (connect 400s until set; key rotated after being pasted into a chat). This PR: record `ios.buildNumber` 4, fix AGENTS.md rule-4 secret list (openrouter/email keys actually come from `.env`, not Docker secrets), this log row. Known gaps for ROADMAP: Gmail OAuth (button intentionally disabled; Gmail works today via IMAP app password), "Other (IMAP)" form has no custom host/port fields (web + mobile). | Docs + one-line version bump only; no runtime change. |
| 2026-07-08 | Claude | `claude/mail-integrations-mobile-qq4gxy` (PR) | Mail integrations in the iPhone app (owner request), mirroring the web accounts page against the unchanged backend: new `mobile/src/screens/MailScreen.tsx` — list/add/remove `email_accounts`, IMAP app-password connect, Microsoft device-code connect (opens the verification URL via `Linking`, polls `/ms/complete` until connected/expired), sync-now, disconnect, and the pending-extraction review queue with approve/dismiss. Reached from Settings → Connections; the Settings tab is now a native stack (`@react-navigation/native-stack` was already a dep — no new packages). `mobile/src/api.ts` gains the email endpoints + `EmailAccount`/`EmailExtraction`/`MsDeviceCode` types, and `ApiError` now surfaces FastAPI's `detail` instead of raw JSON bodies (app-wide, matches the web client). Zero backend changes. | mobile `npm run typecheck` clean; pytest 174 green (untouched baseline); PR open. Reminder: connect/sync round-trip on a device needs a backend the phone can reach (tailnet) — smoke-test on TestFlight after merge. |
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

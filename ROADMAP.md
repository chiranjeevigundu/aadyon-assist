# Roadmap

The shared backlog for every contributor — human or AI agent (Claude, Google Antigravity, …).
Each item is written so an agent with **no chat history** can execute it: goal, what to reuse,
and acceptance criteria. When you pick an item, note it in [HANDOFF.md](HANDOFF.md); when you
finish, tick it here **in the same PR**.

Status: `[ ]` open · `[~]` in progress (see HANDOFF.md) · `[x]` done.

---

## Where we are (2026-08)

Aadyon Assist was **refocused into a personal finance / net-worth app** (Aug 2026). The earlier
"life-ops" persona layer (Digital Me + life-dimension scores), the multi-agent "Agency" org, and
the Calendar / Drive connectors + the Expo mobile app were **removed** to keep the project simple
and usable by anyone. What remains and works today:

- **Net worth** — `assets` (holdings) − `debts` (liabilities), broken down by type, with a daily
  `net_worth_snapshots` trend. Front door at `/`.
- **Tracker** — debts payoff/interest, bills, subscriptions, deadlines, and income (jobs/shifts).
- **Assistant** — a finance chat that reads your numbers and edits your own records; external
  side effects queue as `proposals` (human-in-the-loop).
- **Ingestion** — read-only email (IMAP / Gmail / MS Graph) + document upload, each extracting
  financial items into a review queue.
- **Platform** — multi-user JWT + Postgres RLS; S3-portable storage; daily briefing + backups;
  CI (ruff, gitleaks, Biome, smoke, Schemathesis).

## Next

- [ ] **Proposals review UI.** `propose_action` writes to the `proposals` table but there's no
  screen to act on them. Add `GET /api/proposals` review + approve/dismiss (`PATCH` status), a
  small dashboard section, and surface the pending count. Accept: an assistant-proposed action
  shows up, and Approve/Dismiss updates its status; nothing executes automatically.
- [ ] **Dashboard freshness signals.** Surface "updated just now / N new items to review" on the
  dashboards + a lightweight change feed, so the owner sees when tracking happened. Accept: after
  an upload/email sync, the dashboard shows what changed without a manual refresh hunt.
- [ ] **Auto-snapshot net worth.** Have the `briefing` worker record a daily `net_worth_snapshots`
  row per user so the trend fills in without clicking "Snapshot today". Accept: the trend grows
  daily unattended; manual snapshot still works and is idempotent per day.
- [ ] **Assets from statements.** Extend the document/email extraction to recognize
  account/holding balances (not just transactions/bills) and queue them as `assets` updates.
  Accept: uploading a brokerage statement proposes an asset value update, approve-gated.

## Later

- [ ] **Currency support.** `profile.currency` + per-asset `currency` already exist as fields;
  make net worth aware of them (single reporting currency, FX at entry). Accept: mixed-currency
  assets roll up to one net-worth figure.
- [ ] **Point the app at a cloud URL.** After hosting is chosen, document member onboarding and
  set the public/Tailscale backend. See [docs/CLOUD.md](docs/CLOUD.md) for the managed-cloud path
  (RDS/Cloud SQL + S3/GCS; connection pooling already hardened; secrets via the platform manager).

## Owner-only ops (not agent tasks)

- [ ] Revoke/rotate any GitHub PATs shared in past chat sessions.
- [ ] On each existing deployment: keep personal seeds in the gitignored `code/db/init/`, then
  `just backup-now && just migrate-baseline` when upgrading a pre-yoyo database.

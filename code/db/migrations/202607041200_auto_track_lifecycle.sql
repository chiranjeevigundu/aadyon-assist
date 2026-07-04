-- Auto-tracking: dedup + lifecycle for recurring items extracted from documents/email.
-- `last_seen` records the most recent statement/email date an item appeared on, so a
-- monthly statement updates the existing row instead of creating a duplicate, and a
-- subscription not seen for a while (or explicitly cancelled) can be marked inactive.
-- `active` already exists on both tables and carries the ended/active state.
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS last_seen date;
ALTER TABLE bills ADD COLUMN IF NOT EXISTS last_seen date;

-- Case-insensitive per-user uniqueness on name so dedup has an index to lean on
-- (partial: only active rows, so a re-activated ended sub of the same name is allowed).
CREATE UNIQUE INDEX IF NOT EXISTS uq_subscriptions_user_name_active
  ON subscriptions (user_id, lower(name)) WHERE active;
CREATE UNIQUE INDEX IF NOT EXISTS uq_bills_user_name_active
  ON bills (user_id, lower(name)) WHERE active;

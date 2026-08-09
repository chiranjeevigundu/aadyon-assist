-- Aadyon Assist — Net Worth core
-- Introduces holdings (assets) alongside the existing debts (liabilities) so the
-- app can compute and track true net worth = assets − liabilities over time.
-- transaction

-- --------------------------------------------------------------------------- assets
CREATE TABLE IF NOT EXISTS assets (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name         text NOT NULL,
  kind         text NOT NULL DEFAULT 'other',  -- cash|investment|retirement|property|vehicle|crypto|other
  institution  text,
  value        numeric(14,2) NOT NULL DEFAULT 0,
  currency     text NOT NULL DEFAULT 'USD',
  as_of        date,
  active       boolean NOT NULL DEFAULT true,
  notes        text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_assets_updated ON assets;
CREATE TRIGGER trg_assets_updated BEFORE UPDATE ON assets
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_assets_user ON assets (user_id);

ALTER TABLE assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE assets FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS assets_isolation ON assets;
CREATE POLICY assets_isolation ON assets
  USING (user_id = current_setting('app.current_user_id', true)::uuid)
  WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

-- ----------------------------------------------------------------- net_worth_snapshots
-- One row per user per day: a time series of net worth for the trend chart.
CREATE TABLE IF NOT EXISTS net_worth_snapshots (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  snapshot_date     date NOT NULL DEFAULT CURRENT_DATE,
  total_assets      numeric(14,2) NOT NULL DEFAULT 0,
  total_liabilities numeric(14,2) NOT NULL DEFAULT 0,
  net_worth         numeric(14,2) NOT NULL DEFAULT 0,
  currency          text NOT NULL DEFAULT 'USD',
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, snapshot_date)
);
DROP TRIGGER IF EXISTS trg_net_worth_snapshots_updated ON net_worth_snapshots;
CREATE TRIGGER trg_net_worth_snapshots_updated BEFORE UPDATE ON net_worth_snapshots
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_net_worth_snapshots_user ON net_worth_snapshots (user_id, snapshot_date);

ALTER TABLE net_worth_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE net_worth_snapshots FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS net_worth_snapshots_isolation ON net_worth_snapshots;
CREATE POLICY net_worth_snapshots_isolation ON net_worth_snapshots
  USING (user_id = current_setting('app.current_user_id', true)::uuid)
  WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

-- New tables created by the migrate superuser inherit the ALTER DEFAULT PRIVILEGES
-- grants to aadyon_app (see 202607032100_restricted_app_role.sql); grant explicitly
-- too so the restricted API role can read/write regardless of creation order.
GRANT SELECT, INSERT, UPDATE, DELETE ON assets, net_worth_snapshots TO aadyon_app;

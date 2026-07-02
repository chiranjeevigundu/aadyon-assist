-- Aadyon Assist — P2a: Calendar connector
-- transaction

CREATE TABLE IF NOT EXISTS calendar_accounts (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  email       text NOT NULL,
  provider    text NOT NULL DEFAULT 'google',
  status      text NOT NULL DEFAULT 'not_connected',
  secret_enc  text,
  last_sync   timestamptz,
  last_error  text,
  active      boolean NOT NULL DEFAULT true,
  notes       text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_calendar_accounts_updated ON calendar_accounts;
CREATE TRIGGER trg_calendar_accounts_updated BEFORE UPDATE ON calendar_accounts
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_calendar_accounts_user ON calendar_accounts (user_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_calendar_accounts_user_email ON calendar_accounts (user_id, email);

ALTER TABLE calendar_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE calendar_accounts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS calendar_accounts_isolation ON calendar_accounts;
CREATE POLICY calendar_accounts_isolation ON calendar_accounts
  USING (user_id = current_setting('app.current_user_id', true)::uuid)
  WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);


CREATE TABLE IF NOT EXISTS calendar_extractions (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  account_id   uuid REFERENCES calendar_accounts(id) ON DELETE CASCADE,
  event_id     text,
  event_date   timestamptz,
  summary      text,
  kind         text NOT NULL DEFAULT 'info',
  payload      jsonb NOT NULL DEFAULT '{}',
  status       text NOT NULL DEFAULT 'pending',
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_calendar_extractions_updated ON calendar_extractions;
CREATE TRIGGER trg_calendar_extractions_updated BEFORE UPDATE ON calendar_extractions
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_calendar_extractions_user ON calendar_extractions (user_id);
CREATE INDEX IF NOT EXISTS idx_calendar_extractions_status ON calendar_extractions (status, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_calendar_extractions_msg ON calendar_extractions (account_id, event_id) WHERE event_id IS NOT NULL;

ALTER TABLE calendar_extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE calendar_extractions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS calendar_extractions_isolation ON calendar_extractions;
CREATE POLICY calendar_extractions_isolation ON calendar_extractions
  USING (user_id = current_setting('app.current_user_id', true)::uuid)
  WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

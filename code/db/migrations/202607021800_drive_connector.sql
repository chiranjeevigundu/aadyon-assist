-- Aadyon Assist — P2b: Drive connector
-- transaction

CREATE TABLE IF NOT EXISTS drive_accounts (
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
DROP TRIGGER IF EXISTS trg_drive_accounts_updated ON drive_accounts;
CREATE TRIGGER trg_drive_accounts_updated BEFORE UPDATE ON drive_accounts
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_drive_accounts_user ON drive_accounts (user_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_drive_accounts_user_email ON drive_accounts (user_id, email);

ALTER TABLE drive_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE drive_accounts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS drive_accounts_isolation ON drive_accounts;
CREATE POLICY drive_accounts_isolation ON drive_accounts
  USING (user_id = current_setting('app.current_user_id', true)::uuid)
  WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);


CREATE TABLE IF NOT EXISTS drive_files (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  account_id   uuid REFERENCES drive_accounts(id) ON DELETE CASCADE,
  file_id      text NOT NULL,
  file_name    text NOT NULL,
  mime_type    text,
  web_view_link text,
  size_bytes   bigint,
  status       text NOT NULL DEFAULT 'synced',
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_drive_files_updated ON drive_files;
CREATE TRIGGER trg_drive_files_updated BEFORE UPDATE ON drive_files
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_drive_files_user ON drive_files (user_id);
CREATE INDEX IF NOT EXISTS idx_drive_files_status ON drive_files (status, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_drive_files_msg ON drive_files (account_id, file_id);

ALTER TABLE drive_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE drive_files FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS drive_files_isolation ON drive_files;
CREATE POLICY drive_files_isolation ON drive_files
  USING (user_id = current_setting('app.current_user_id', true)::uuid)
  WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

-- Aadyon Assist — P2c: Banking connector
-- transaction

CREATE TABLE IF NOT EXISTS bank_accounts (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  institution text NOT NULL,
  secret_enc  text,
  last_sync   timestamptz,
  last_error  text,
  active      boolean NOT NULL DEFAULT true,
  status      text NOT NULL DEFAULT 'not_connected',
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_bank_accounts_updated ON bank_accounts;
CREATE TRIGGER trg_bank_accounts_updated BEFORE UPDATE ON bank_accounts
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_bank_accounts_user ON bank_accounts (user_id);

ALTER TABLE bank_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE bank_accounts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bank_accounts_isolation ON bank_accounts;
CREATE POLICY bank_accounts_isolation ON bank_accounts
  USING (user_id = current_setting('app.current_user_id', true)::uuid)
  WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);


CREATE TABLE IF NOT EXISTS bank_transactions (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  account_id     uuid REFERENCES bank_accounts(id) ON DELETE CASCADE,
  transaction_id text,
  date           timestamptz,
  amount         numeric,
  merchant       text,
  category       text,
  status         text NOT NULL DEFAULT 'pending',
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_bank_transactions_updated ON bank_transactions;
CREATE TRIGGER trg_bank_transactions_updated BEFORE UPDATE ON bank_transactions
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_bank_transactions_user ON bank_transactions (user_id);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_status ON bank_transactions (status, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_bank_transactions_msg ON bank_transactions (account_id, transaction_id) WHERE transaction_id IS NOT NULL;

ALTER TABLE bank_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE bank_transactions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bank_transactions_isolation ON bank_transactions;
CREATE POLICY bank_transactions_isolation ON bank_transactions
  USING (user_id = current_setting('app.current_user_id', true)::uuid)
  WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

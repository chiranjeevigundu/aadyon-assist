-- Aadyon Assist — Phase 2c: email ingest (iCloud IMAP first)
-- Stores the encrypted app-password on the account, and a review queue of items
-- the LLM extracted from mail. Approved items are inserted into the tracker.
-- Idempotent.

-- Encrypted credential (Fernet); never stored in plaintext, never returned by the API.
ALTER TABLE email_accounts ADD COLUMN IF NOT EXISTS secret_enc text;

-- Review queue: one row per actionable item the LLM found in an email.
CREATE TABLE IF NOT EXISTS email_extractions (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id   uuid REFERENCES email_accounts(id) ON DELETE CASCADE,
  message_uid  text,                                  -- IMAP UID (dedup per account)
  message_date timestamptz,
  sender       text,
  subject      text,
  kind         text NOT NULL DEFAULT 'info',          -- deadline | bill | subscription | info
  payload      jsonb NOT NULL DEFAULT '{}',           -- proposed row for the target table
  summary      text,                                  -- human-readable one-liner
  status       text NOT NULL DEFAULT 'pending',       -- pending | approved | dismissed
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_email_extractions_updated ON email_extractions;
CREATE TRIGGER trg_email_extractions_updated BEFORE UPDATE ON email_extractions
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_email_extractions_status ON email_extractions (status, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_email_extractions_msg
  ON email_extractions (account_id, message_uid) WHERE message_uid IS NOT NULL;

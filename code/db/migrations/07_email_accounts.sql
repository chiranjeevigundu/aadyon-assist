-- Aadyon Assist — Phase 2b: email account registry (foundation)
-- Phase 1 of the email feature: register accounts + their intended auth method.
-- Live inbox reading (IMAP for iCloud, OAuth for Gmail/Microsoft) comes next; the
-- credentials/tokens will live in an encrypted store, NOT in this table. Idempotent.

CREATE TABLE IF NOT EXISTS email_accounts (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email       text NOT NULL UNIQUE,
  provider    text NOT NULL DEFAULT 'other',         -- icloud | gmail | microsoft | other
  purpose     text,                                  -- e.g. University, Personal, Finance
  auth_type   text NOT NULL DEFAULT 'imap',          -- imap | oauth_google | oauth_microsoft
  imap_host   text,                                  -- for imap accounts (e.g. imap.mail.me.com)
  imap_port   int,                                   -- usually 993
  status      text NOT NULL DEFAULT 'not_connected', -- not_connected | connected | error
  last_sync   timestamptz,
  last_error  text,
  active      boolean NOT NULL DEFAULT true,
  notes       text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_email_accounts_updated ON email_accounts;
CREATE TRIGGER trg_email_accounts_updated BEFORE UPDATE ON email_accounts
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_email_accounts_active ON email_accounts (active)

-- No seed: add your accounts via the Accounts page.;

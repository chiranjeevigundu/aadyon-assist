-- Aadyon Assist — email sync high-water mark
-- Track the highest IMAP UID processed per account (and UIDVALIDITY) so each sync
-- only runs the model on genuinely new mail. Idempotent.
ALTER TABLE email_accounts ADD COLUMN IF NOT EXISTS last_uid     bigint;
ALTER TABLE email_accounts ADD COLUMN IF NOT EXISTS uid_validity bigint;

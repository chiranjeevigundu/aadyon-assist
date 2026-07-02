-- 202607022100_proactive_intelligence
-- Applied by yoyo-migrations (`just migrate`); the _yoyo_* ledger tracks state.

-- P5 - Proactive intelligence
-- Add per-user ntfy_topic to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS ntfy_topic text;

-- Add balance to bank_accounts for low balance alerts
ALTER TABLE bank_accounts ADD COLUMN IF NOT EXISTS balance float NOT NULL DEFAULT 0.0;

-- Family & friends multi-user hardening: account-layer columns + invite codes.
-- (Email-verify and password-reset tokens are stateless purpose-scoped JWTs — no table.)

-- users: verification + per-user LLM budget accounting.
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified      boolean NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS monthly_token_budget integer;          -- NULL = unlimited
ALTER TABLE users ADD COLUMN IF NOT EXISTS tokens_used          integer NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS usage_period_start   date;

-- Existing accounts predate verification; treat them as already verified so nobody
-- gets locked out by the new flag.
UPDATE users SET email_verified = true WHERE created_at < now();

-- Invite codes gate signup. Global/admin table (not per-user) — accessed via
-- query_unscoped like `users`, so no RLS policy here.
CREATE TABLE IF NOT EXISTS invite_codes (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code       text UNIQUE NOT NULL,
  note       text,                         -- who it's for / why
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  used_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  used_at    timestamptz,
  expires_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_invite_codes_code ON invite_codes (code) WHERE used_at IS NULL;

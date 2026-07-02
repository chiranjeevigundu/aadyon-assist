-- 202607010711_multiuser_auth
-- Applied by yoyo-migrations (`just migrate`); the _yoyo_* ledger tracks state.
--
-- Turns the single-user app into a multi-user one. Every per-user table gains a
-- user_id and a Row-Level-Security (RLS) policy so each request only ever sees
-- its own rows. Isolation is enforced at the database (fail-closed): the app sets
-- `app.current_user_id` per request (see db/session.py) and RLS filters on it.
--
-- Idempotent + safe to apply to the live single-user DB: it backfills all existing
-- rows to a single "legacy" user BEFORE enabling RLS, so nothing is orphaned.
--
-- NOTE: personal seed SQL (code/db/seed/, applied via `just seed`) must assign
-- user_id going forward — sign up first, then reference your users row.

-- ---------------------------------------------------------------------------
-- USERS  (the auth table; intentionally NOT under RLS — reads are by email/id)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email         text NOT NULL UNIQUE,
  password_hash text NOT NULL,
  display_name  text,
  is_active     boolean NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_users_updated ON users;
CREATE TRIGGER trg_users_updated BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- A single "legacy" user to own all pre-existing single-user data. The password
-- hash is a non-loginable placeholder; set a real password by signing up fresh or
-- via a reset. All existing rows are backfilled to this user below.
INSERT INTO users (email, password_hash, display_name)
SELECT 'legacy@aadyon.local', 'x-not-set', 'Legacy'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE email = 'legacy@aadyon.local');

-- ---------------------------------------------------------------------------
-- Per-user tables: add user_id, backfill to legacy, index, then enforce RLS.
-- Done in a loop so the list stays in one place and every table is treated the
-- same way. model_routes stays GLOBAL (operator-level routing config, no RLS).
-- ---------------------------------------------------------------------------
DO $mu$
DECLARE
  legacy uuid;
  t text;
  per_user text[] := ARRAY[
    'deadlines','debts','bills','subscriptions','shifts',
    'profile','applications','milestones','jobs','work_schedule',
    'email_accounts','email_extractions','tasks','agent_runs',
    'teams','agents','memory_chunks'
  ];
BEGIN
  SELECT id INTO legacy FROM users WHERE email = 'legacy@aadyon.local';

  FOREACH t IN ARRAY per_user LOOP
    -- add the column if missing
    EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS user_id uuid', t);
    -- backfill existing rows to the legacy user
    EXECUTE format('UPDATE %I SET user_id = %L WHERE user_id IS NULL', t, legacy);
    -- FK + NOT NULL + index (guarded so re-runs are safe)
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_'||t||'_user') THEN
      EXECUTE format(
        'ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY (user_id) '
        'REFERENCES users(id) ON DELETE CASCADE', t, 'fk_'||t||'_user');
    END IF;
    EXECUTE format('ALTER TABLE %I ALTER COLUMN user_id SET NOT NULL', t);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (user_id)', 'idx_'||t||'_user', t);

    -- Row-Level Security. FORCE is required because the app connects as the table
    -- owner, and owners bypass RLS without it. An unset GUC -> NULL -> no rows.
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS %I ON %I', t||'_isolation', t);
    EXECUTE format(
      'CREATE POLICY %I ON %I '
      'USING (user_id = current_setting(''app.current_user_id'', true)::uuid) '
      'WITH CHECK (user_id = current_setting(''app.current_user_id'', true)::uuid)',
      t||'_isolation', t);
  END LOOP;
END $mu$;

-- ---------------------------------------------------------------------------
-- Fix per-table uniqueness that used to be global (one user before, many now).
-- ---------------------------------------------------------------------------
-- profile was a hard singleton (one row globally). Make it one-per-user.
DROP INDEX IF EXISTS one_profile;
CREATE UNIQUE INDEX IF NOT EXISTS one_profile_per_user ON profile (user_id);

-- teams.name / agents.name were globally UNIQUE — they must be unique per user
-- so each user's org can carry the same role names.
ALTER TABLE teams  DROP CONSTRAINT IF EXISTS teams_name_key;
ALTER TABLE agents DROP CONSTRAINT IF EXISTS agents_name_key;
CREATE UNIQUE INDEX IF NOT EXISTS uq_teams_user_name  ON teams  (user_id, name);
CREATE UNIQUE INDEX IF NOT EXISTS uq_agents_user_name ON agents (user_id, name);

-- email_accounts.email was globally UNIQUE — unique per user instead.
ALTER TABLE email_accounts DROP CONSTRAINT IF EXISTS email_accounts_email_key;
CREATE UNIQUE INDEX IF NOT EXISTS uq_email_accounts_user_email
  ON email_accounts (user_id, email);

-- ---------------------------------------------------------------------------
-- debt_summary view runs under the querying user's RLS (Postgres 15+ default).
-- Recreate it as security_invoker so it is scoped on older versions too.
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS debt_summary;
CREATE VIEW debt_summary
  WITH (security_invoker = true) AS
SELECT
  name, kind, balance, apr, min_payment, credit_limit, priority_rank,
  CASE WHEN credit_limit > 0 THEN round(balance / credit_limit * 100, 1) END AS utilization_pct,
  round(balance * apr / 100 / 12, 2) AS est_monthly_interest
FROM debts
ORDER BY priority_rank NULLS LAST, apr DESC;

-- ---------------------------------------------------------------------------
-- seed_org(user_id): give a new user their own org (CEO + four teams + leads +
-- employees), mirroring the global seed in 06_agency.sql. Called on signup.
-- Guarded so re-running for a user is a no-op.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION seed_org(p_user uuid) RETURNS void AS $seed$
BEGIN
  -- Teams
  INSERT INTO teams (user_id, name, dimension, mission)
  SELECT p_user, v.name, v.dimension, v.mission FROM (VALUES
    ('Finance',     'financial', 'Cut interest burn and protect cashflow; pay down high-interest debt.'),
    ('Immigration', 'visa',      'Keep work authorization continuous; never miss an immigration deadline.'),
    ('Career',      'career',    'Land a higher-paying role that improves the income picture.'),
    ('Growth',      'goal',      'Make measurable progress toward the user''s long-term goals.')
  ) AS v(name,dimension,mission)
  WHERE NOT EXISTS (SELECT 1 FROM teams t WHERE t.user_id = p_user AND t.name = v.name);

  -- CEO
  INSERT INTO agents (user_id, name, title, agent_type, model_tier, autonomy, system_prompt)
  SELECT p_user, 'Aadyon CEO', 'Chief Executive', 'ceo', 'reasoning', 'auto',
   'You are the CEO of the owner''s personal life-ops company. Be a direct, honest '
   || 'operator who pushes back rather than flatters. Given a goal, read the Digital Me '
   || 'snapshot, decide which teams (Finance, Immigration, Career, Growth) should act, and '
   || 'delegate concrete sub-tasks with the delegate tool. Never invent numbers; rely on tools.'
  WHERE NOT EXISTS (SELECT 1 FROM agents WHERE user_id = p_user AND name = 'Aadyon CEO');

  -- Team leads
  INSERT INTO agents (user_id, name, title, agent_type, team_id, reports_to, model_tier, autonomy, system_prompt)
  SELECT p_user, v.name, v.title, 'team_lead',
         (SELECT id FROM teams  WHERE user_id = p_user AND name = v.team),
         (SELECT id FROM agents WHERE user_id = p_user AND name = 'Aadyon CEO'),
         'reasoning', 'auto', v.sp
  FROM (VALUES
    ('Head of Finance','Head of Finance','Finance',
      'You lead Finance. Analyze debts, utilization, interest, and income vs obligations. For any action that moves money, use propose_action (never execute).'),
    ('Head of Immigration','Head of Immigration','Immigration',
      'You lead Immigration. Track visa and work-authorization deadlines and blockers. propose_action for filings/emails (human approves).'),
    ('Head of Career','Head of Career','Career',
      'You lead Career. Assess the job-search pipeline and the income gap; recommend concrete next steps. propose_action for outreach.'),
    ('Head of Growth','Head of Growth','Growth',
      'You lead Growth. Track goals vs their target timeline; recommend focus. propose_action for commitments.')
  ) AS v(name,title,team,sp)
  WHERE NOT EXISTS (SELECT 1 FROM agents a WHERE a.user_id = p_user AND a.name = v.name);

  -- Employees
  INSERT INTO agents (user_id, name, title, agent_type, team_id, reports_to, model_tier, autonomy, system_prompt)
  SELECT p_user, v.name, v.title, 'employee',
         (SELECT id FROM teams  WHERE user_id = p_user AND name = v.team),
         (SELECT id FROM agents WHERE user_id = p_user AND name = v.lead),
         v.tier, 'auto', v.sp
  FROM (VALUES
    ('Debt Strategist','Debt Strategist','Finance','Head of Finance','reasoning',
      'You are a debt-payoff strategist. Compute avalanche vs snowball and name the single biggest-interest-saving move this month. propose_action for payments.'),
    ('Cashflow Analyst','Cashflow Analyst','Finance','Head of Finance','cheap',
      'You analyze income vs bills/minimums and flag shortfalls. Be concrete and brief.'),
    ('Deadline Watcher','Deadline Watcher','Immigration','Head of Immigration','cheap',
      'You scan immigration deadlines and report what is due, blocked, and the next action with a date.'),
    ('Job Search Scout','Job Search Scout','Career','Head of Career','reasoning',
      'You assess the application pipeline and salary gap and suggest the next 3 concrete job-search actions. propose_action for outreach.'),
    ('Goal Coach','Goal Coach','Growth','Head of Growth','reasoning',
      'You review open goals vs their target dates and recommend the one focus that moves the needle.')
  ) AS v(name,title,team,lead,tier,sp)
  WHERE NOT EXISTS (SELECT 1 FROM agents a WHERE a.user_id = p_user AND a.name = v.name);
END $seed$ LANGUAGE plpgsql;

-- Give the legacy user their own org. The global 06_agency seed rows were
-- backfilled to legacy above; seed_org fills any gaps idempotently. RLS is now
-- FORCEd on teams/agents, so set the GUC first (any INSERT must satisfy WITH CHECK).
SELECT set_config('app.current_user_id',
  (SELECT id::text FROM users WHERE email = 'legacy@aadyon.local'), false);
SELECT seed_org((SELECT id FROM users WHERE email = 'legacy@aadyon.local'));
SELECT set_config('app.current_user_id', '', false);

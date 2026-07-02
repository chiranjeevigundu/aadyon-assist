-- Aadyon Assist — Phase 1b: "Digital Me" layer
-- Identity + life dimensions on top of the existing tracker tables.
-- Idempotent: safe to run on a fresh DB and on a live one
-- AND against a live DB (yoyo applies it once). Uses IF NOT EXISTS + guarded seeds.

-- ---------------------------------------------------------------------------
-- PROFILE  (singleton — who the Digital Me is)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS profile (
  id                        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name                 text NOT NULL,
  preferred_name            text,
  birthdate                 date,
  birthplace                text,
  location                  text,
  nationality               text,
  headline                  text,
  bio                       text,
  visa_type                 text,
  visa_status               text,
  work_auth_until           date,
  target_role               text,
  target_salary             numeric(12,2),   -- annual, editable target
  current_income            numeric(12,2),   -- annual, on paper
  remittance_pct            int,             -- % of income routed away (e.g. to family)
  monthly_essential_expenses numeric(12,2),  -- your own minimum monthly burn
  goal_title                text,
  goal_target_date          date,
  life_expectancy_years     int NOT NULL DEFAULT 80,
  updated_at                timestamptz NOT NULL DEFAULT now()
);
-- Enforce a single profile row.
CREATE UNIQUE INDEX IF NOT EXISTS one_profile ON profile ((true));
DROP TRIGGER IF EXISTS trg_profile_updated ON profile;
CREATE TRIGGER trg_profile_updated BEFORE UPDATE ON profile
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- APPLICATIONS  (career / job-search funnel — the highest-leverage dimension)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS applications (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company      text NOT NULL,
  role         text,
  status       text NOT NULL DEFAULT 'saved',   -- saved|applied|screening|interview|offer|rejected|accepted
  salary_min   numeric(12,2),
  salary_max   numeric(12,2),
  location     text,
  work_type    text,                            -- remote|hybrid|onsite
  source       text,                            -- LinkedIn|referral|company site|...
  url          text,
  applied_date date,
  notes        text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_applications_updated ON applications;
CREATE TRIGGER trg_applications_updated BEFORE UPDATE ON applications
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications (status);

-- ---------------------------------------------------------------------------
-- MILESTONES  (life timeline since birth + in-progress goals)
-- achieved=true  -> a point event on the timeline (milestone_date = when it happened)
-- achieved=false -> an in-progress goal (milestone_date = target; progress_pct 0..100)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS milestones (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title          text NOT NULL,
  category       text NOT NULL DEFAULT 'life',  -- life|education|career|immigration|financial|goal|personal
  milestone_date date,
  achieved       boolean NOT NULL DEFAULT false,
  progress_pct   int,
  notes          text,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_milestones_updated ON milestones;
CREATE TRIGGER trg_milestones_updated BEFORE UPDATE ON milestones
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_milestones_date ON milestones (milestone_date)

-- Personal seed (profile + milestones) lives in the gitignored 99_seed_local.sql,
-- which runs after all DDL. See code/db/seed.example.sql for a placeholder template.
-- applications: intentionally empty until the job search starts.;

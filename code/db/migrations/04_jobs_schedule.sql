-- Aadyon Assist — Phase 1c: jobs + recurring weekly work schedule
-- Part-time hourly work repeats weekly with different hours per day; full-time is
-- salaried (no hourly shifts). 'shifts' stays for one-off actuals. Idempotent.

-- ---------------------------------------------------------------------------
-- JOBS  (one row per employment/income source)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jobs (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  employer       text NOT NULL,
  role           text,
  kind           text NOT NULL DEFAULT 'part_time_hourly', -- part_time_hourly | full_time_salary | gig
  status         text NOT NULL DEFAULT 'active',           -- active | offer | ended
  hourly_rate    numeric(8,2),                             -- for hourly/gig
  annual_salary  numeric(12,2),                            -- for salaried
  remittance_pct int NOT NULL DEFAULT 0,                   -- % of this job's pay routed away (e.g. to family)
  start_date     date,
  end_date       date,
  notes          text,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_jobs_updated ON jobs;
CREATE TRIGGER trg_jobs_updated BEFORE UPDATE ON jobs
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status);

-- ---------------------------------------------------------------------------
-- WORK_SCHEDULE  (recurring weekly pattern for hourly jobs)
-- day_of_week: 0=Mon, 1=Tue, ... 6=Sun. One row per working day; hours can differ.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS work_schedule (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id       uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  day_of_week  int  NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
  start_time   time,
  end_time     time,
  hours        numeric(5,2) NOT NULL,
  active       boolean NOT NULL DEFAULT true,
  notes        text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_work_schedule_updated ON work_schedule;
CREATE TRIGGER trg_work_schedule_updated BEFORE UPDATE ON work_schedule
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_work_schedule_job ON work_schedule (job_id)

-- Personal seed (your real jobs) lives in the gitignored 99_seed_local.sql, which
-- runs after all DDL. See code/db/seed.example.sql for a placeholder template.;

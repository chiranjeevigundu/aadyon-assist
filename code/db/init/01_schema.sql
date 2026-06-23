-- Aadyon Assist — Phase 1 schema
-- Portable to Mini-A Postgres as-is. Keep this file as the contract.

CREATE EXTENSION IF NOT EXISTS vector;      -- pgvector, for future RAG/memory
CREATE EXTENSION IF NOT EXISTS pgcrypto;    -- gen_random_uuid()

-- Reusable updated_at trigger
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- DEADLINES  (visa filings, document expiries, anything with a hard date)
-- ---------------------------------------------------------------------------
CREATE TABLE deadlines (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title       text NOT NULL,
  category    text NOT NULL DEFAULT 'general',  -- immigration | financial | personal | general
  due_date    date NOT NULL,
  status      text NOT NULL DEFAULT 'open',      -- open | blocked | done | missed
  priority    int  NOT NULL DEFAULT 3,           -- 1 highest .. 5 lowest
  blocked_on  text,                              -- what this is waiting on (e.g. 'DSO STEM I-20')
  notes       text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_deadlines_updated BEFORE UPDATE ON deadlines
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX idx_deadlines_due ON deadlines (due_date) WHERE status <> 'done';

-- ---------------------------------------------------------------------------
-- DEBTS  (cards + loans)
-- ---------------------------------------------------------------------------
CREATE TABLE debts (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL,
  kind          text NOT NULL DEFAULT 'card',    -- card | loan
  balance       numeric(12,2) NOT NULL,
  apr           numeric(5,2)  NOT NULL,           -- annual %, e.g. 30.50
  min_payment   numeric(12,2) NOT NULL DEFAULT 0,
  credit_limit  numeric(12,2),                    -- null for loans
  due_day       int,                              -- day-of-month statement due, if known
  priority_rank int,                              -- payoff order (1 = attack first)
  notes         text,
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_debts_updated BEFORE UPDATE ON debts
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Derived view: utilization + monthly interest, payoff-priority ordered
CREATE VIEW debt_summary AS
SELECT
  name, kind, balance, apr, min_payment, credit_limit, priority_rank,
  CASE WHEN credit_limit > 0 THEN round(balance / credit_limit * 100, 1) END AS utilization_pct,
  round(balance * apr / 100 / 12, 2) AS est_monthly_interest
FROM debts
ORDER BY priority_rank NULLS LAST, apr DESC;

-- ---------------------------------------------------------------------------
-- BILLS  (recurring obligations: rent, utilities, card minimums, etc.)
-- ---------------------------------------------------------------------------
CREATE TABLE bills (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name       text NOT NULL,
  amount     numeric(12,2) NOT NULL,
  frequency  text NOT NULL DEFAULT 'monthly',     -- monthly | weekly | yearly | one-time
  due_day    int,                                 -- day-of-month for monthly bills
  autopay    boolean NOT NULL DEFAULT false,
  category   text,                                -- housing | utility | debt | transport | other
  active     boolean NOT NULL DEFAULT true,
  notes      text,
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_bills_updated BEFORE UPDATE ON bills
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- SUBSCRIPTIONS
-- ---------------------------------------------------------------------------
CREATE TABLE subscriptions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL,
  amount        numeric(12,2) NOT NULL,
  billing_cycle text NOT NULL DEFAULT 'monthly',  -- monthly | yearly
  renews_on     date,
  category      text,
  active        boolean NOT NULL DEFAULT true,
  notes         text,
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_subscriptions_updated BEFORE UPDATE ON subscriptions
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- SHIFTS  (part-time / gig income tracking)
-- ---------------------------------------------------------------------------
CREATE TABLE shifts (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  employer    text NOT NULL,
  role        text,
  shift_date  date NOT NULL,
  start_time  time,
  end_time    time,
  hours       numeric(5,2),
  hourly_rate numeric(8,2),
  est_pay     numeric(10,2),
  status      text NOT NULL DEFAULT 'scheduled',  -- scheduled | worked | paid | cancelled
  notes       text,
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_shifts_updated BEFORE UPDATE ON shifts
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX idx_shifts_date ON shifts (shift_date);

-- ---------------------------------------------------------------------------
-- MEMORY_CHUNKS  (Phase 2 RAG — present now so the schema is stable)
-- ---------------------------------------------------------------------------
CREATE TABLE memory_chunks (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source     text,                                -- where it came from
  content    text NOT NULL,
  embedding  vector(1536),                        -- fill when embeddings are wired up
  metadata   jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);
-- IVFFlat index is added later once there are enough rows to train it.

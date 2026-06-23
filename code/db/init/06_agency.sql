-- Aadyon Assist — Phase 2: agentic org layer
-- An enterprise-style org (CEO -> team leads -> employees) on top of the same DB.
-- Tasks flow through a queue; an LLM router (OpenRouter + local Ollama) powers agents.
-- Idempotent.

-- ---------------------------------------------------------------------------
-- TEAMS  (a team usually maps to a Digital Me dimension, but is fully editable)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teams (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name       text NOT NULL UNIQUE,
  dimension  text,                          -- financial | visa | career | goal | custom
  mission    text,
  active     boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_teams_updated ON teams;
CREATE TRIGGER trg_teams_updated BEFORE UPDATE ON teams FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- AGENTS  (the org chart: CEO, team leads, employees)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agents (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL UNIQUE,
  title         text,
  agent_type    text NOT NULL DEFAULT 'employee',  -- ceo | team_lead | employee
  team_id       uuid REFERENCES teams(id) ON DELETE SET NULL,
  reports_to    uuid REFERENCES agents(id) ON DELETE SET NULL,
  model_tier    text NOT NULL DEFAULT 'reasoning', -- reasoning | cheap | local
  model_id      text,                              -- optional explicit model override
  system_prompt text,
  autonomy      text NOT NULL DEFAULT 'auto',      -- auto (run read-only) | propose | read_only
  active        boolean NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_agents_updated ON agents;
CREATE TRIGGER trg_agents_updated BEFORE UPDATE ON agents FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- TASKS  (the work queue; CEO delegates, teams execute; proposals need approval)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tasks (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title             text NOT NULL,
  description       text,
  kind              text NOT NULL DEFAULT 'task',   -- goal | task | proposal
  team_id           uuid REFERENCES teams(id) ON DELETE SET NULL,
  agent_id          uuid REFERENCES agents(id) ON DELETE SET NULL,
  parent_id         uuid REFERENCES tasks(id) ON DELETE CASCADE,
  status            text NOT NULL DEFAULT 'queued', -- queued|running|awaiting_approval|blocked|done|failed|cancelled
  priority          int  NOT NULL DEFAULT 3,
  requires_approval boolean NOT NULL DEFAULT false,
  result            text,
  error             text,
  model_used        text,
  created_by        text NOT NULL DEFAULT 'user',
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_tasks_updated ON tasks;
CREATE TRIGGER trg_tasks_updated BEFORE UPDATE ON tasks FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status, priority);

-- ---------------------------------------------------------------------------
-- AGENT_RUNS  (append-only audit trail of each LLM call / tool step)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_runs (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id    uuid REFERENCES tasks(id) ON DELETE CASCADE,
  agent_id   uuid REFERENCES agents(id) ON DELETE SET NULL,
  step       int,
  provider   text,
  model      text,
  role       text,            -- assistant | tool
  tool_name  text,
  content    text,
  tokens     int,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_task ON agent_runs (task_id, step);

-- ---------------------------------------------------------------------------
-- MODEL_ROUTES  (task-tier -> provider + model; the OpenRouter/local routing table)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS model_routes (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tier        text NOT NULL UNIQUE,          -- reasoning | cheap | local
  provider    text NOT NULL DEFAULT 'openrouter', -- openrouter | ollama
  model_id    text NOT NULL,
  temperature numeric(3,2) NOT NULL DEFAULT 0.2,
  active      boolean NOT NULL DEFAULT true,
  notes       text,
  updated_at  timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_model_routes_updated ON model_routes;
CREATE TRIGGER trg_model_routes_updated BEFORE UPDATE ON model_routes FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ===========================================================================
-- SEED  (guarded)
-- ===========================================================================

INSERT INTO model_routes (tier, provider, model_id, temperature, notes)
SELECT v.* FROM (VALUES
  ('reasoning','openrouter','openrouter/auto',     0.20::numeric, 'Planning/analysis. openrouter/auto picks the best available provider/model.'),
  ('cheap',    'openrouter','openai/gpt-4o-mini',  0.20::numeric, 'High-volume classification/extraction.'),
  ('local',    'ollama',    'llama3.1',            0.20::numeric, 'Private/bulk tasks on your machine via Ollama.')
) AS v(tier,provider,model_id,temperature,notes)
WHERE NOT EXISTS (SELECT 1 FROM model_routes m WHERE m.tier = v.tier);

INSERT INTO teams (name, dimension, mission)
SELECT v.* FROM (VALUES
  ('Finance',     'financial', 'Cut interest burn and protect cashflow; get to debt-free before 30.'),
  ('Immigration', 'visa',      'Keep work authorization continuous; never miss a USCIS/DSO deadline.'),
  ('Career',      'career',    'Land a higher-paying engineering role that fixes the debt math.'),
  ('Growth',      'goal',      'Make measurable progress toward Aadyon and the before-30 goals.')
) AS v(name,dimension,mission)
WHERE NOT EXISTS (SELECT 1 FROM teams t WHERE t.name = v.name);

-- CEO
INSERT INTO agents (name, title, agent_type, model_tier, autonomy, system_prompt)
SELECT 'Aadyon CEO', 'Chief Executive', 'ceo', 'reasoning', 'auto',
 'You are the CEO of Aadyon, the owner''s personal life-ops company. Be a direct, '
 || 'honest operator who pushes back rather than flatters. Given a goal, read the Digital Me '
 || 'snapshot, decide which teams (Finance, Immigration, Career, Growth) should act, and '
 || 'delegate concrete sub-tasks to them with the `delegate` tool. Keep the live fires first: '
 || 'the visa filing and income. End with a short, prioritized plan. Never invent numbers; rely on tools.'
WHERE NOT EXISTS (SELECT 1 FROM agents WHERE name = 'Aadyon CEO');

-- Team leads
INSERT INTO agents (name, title, agent_type, team_id, reports_to, model_tier, autonomy, system_prompt)
SELECT v.name, v.title, 'team_lead',
       (SELECT id FROM teams WHERE name = v.team),
       (SELECT id FROM agents WHERE name = 'Aadyon CEO'),
       'reasoning', 'auto', v.sp
FROM (VALUES
  ('Head of Finance','Head of Finance','Finance',
    'You lead Finance. Analyze debts, utilization, interest, and projected income vs obligations. Recommend the highest-leverage payoff/cashflow moves. Use read tools; for any action that moves money, use propose_action (never execute).'),
  ('Head of Immigration','Head of Immigration','Immigration',
    'You lead Immigration. Track visa/OPT/STEM deadlines and blockers; surface what must happen next and by when. Use read tools; propose_action for filings/emails (human approves).'),
  ('Head of Career','Head of Career','Career',
    'You lead Career. The job search is the single highest-leverage lever. Assess pipeline and the income gap; recommend concrete next steps. propose_action for outreach (human approves).'),
  ('Head of Growth','Head of Growth','Growth',
    'You lead Growth. Track goals vs the before-30 timeline and the pace gap; recommend focus. propose_action for commitments.')
) AS v(name,title,team,sp)
WHERE NOT EXISTS (SELECT 1 FROM agents a WHERE a.name = v.name);

-- Employees
INSERT INTO agents (name, title, agent_type, team_id, reports_to, model_tier, autonomy, system_prompt)
SELECT v.name, v.title, 'employee',
       (SELECT id FROM teams WHERE name = v.team),
       (SELECT id FROM agents WHERE name = v.lead),
       v.tier, 'auto', v.sp
FROM (VALUES
  ('Debt Strategist','Debt Strategist','Finance','Head of Finance','reasoning',
    'You are a debt-payoff strategist. Given the debts, compute avalanche vs snowball impact and name the single move with the biggest interest savings this month. Use tools; propose_action for payments.'),
  ('Cashflow Analyst','Cashflow Analyst','Finance','Head of Finance','cheap',
    'You analyze income vs bills/minimums and flag shortfalls. Be concrete and brief.'),
  ('Deadline Watcher','Deadline Watcher','Immigration','Head of Immigration','cheap',
    'You scan immigration deadlines and report what is due, blocked, and the next action with a date.'),
  ('Job Search Scout','Job Search Scout','Career','Head of Career','reasoning',
    'You assess the application pipeline and the salary gap and suggest the next 3 concrete job-search actions. propose_action for outreach.'),
  ('Goal Coach','Goal Coach','Growth','Head of Growth','reasoning',
    'You review open goals vs time-to-30 and recommend the one focus that moves the needle.')
) AS v(name,title,team,lead,tier,sp)
WHERE NOT EXISTS (SELECT 1 FROM agents a WHERE a.name = v.name);

-- Sanity: SELECT name, agent_type, model_tier FROM agents ORDER BY agent_type;

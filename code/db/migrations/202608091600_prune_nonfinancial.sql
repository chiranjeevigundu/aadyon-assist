-- Prune non-financial domains — refocus to a finance / net-worth app.
-- Removes calendar, drive, the agentic "Agency" org, and the career/goals persona
-- (applications, milestones). Adds a lightweight `proposals` table so the assistant's
-- human-in-the-loop external-action queue survives the removal of the agency `tasks`.
-- transaction

-- Signup no longer seeds an agent org; drop the function before its tables.
DROP FUNCTION IF EXISTS seed_org(uuid);

-- Agentic org layer (CASCADE clears FKs: agent_runs->tasks, agents->teams, etc.)
DROP TABLE IF EXISTS agent_runs   CASCADE;
DROP TABLE IF EXISTS tasks        CASCADE;
DROP TABLE IF EXISTS agents       CASCADE;
DROP TABLE IF EXISTS teams        CASCADE;
DROP TABLE IF EXISTS model_routes CASCADE;

-- Calendar + Drive connectors
DROP TABLE IF EXISTS calendar_extractions CASCADE;
DROP TABLE IF EXISTS calendar_accounts    CASCADE;
DROP TABLE IF EXISTS drive_files           CASCADE;
DROP TABLE IF EXISTS drive_accounts        CASCADE;

-- Career / goals persona
DROP TABLE IF EXISTS applications CASCADE;
DROP TABLE IF EXISTS milestones   CASCADE;

-- --------------------------------------------------------------------- proposals
-- The assistant queues real-world EXTERNAL actions here for the user to approve;
-- nothing executes automatically. Per-user, RLS-isolated.
CREATE TABLE IF NOT EXISTS proposals (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title      text NOT NULL,
  detail     text,
  category   text,
  status     text NOT NULL DEFAULT 'pending',  -- pending | approved | dismissed
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_proposals_updated ON proposals;
CREATE TRIGGER trg_proposals_updated BEFORE UPDATE ON proposals
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_proposals_user ON proposals (user_id, status);

ALTER TABLE proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposals FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS proposals_isolation ON proposals;
CREATE POLICY proposals_isolation ON proposals
  USING (user_id = current_setting('app.current_user_id', true)::uuid)
  WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON proposals TO aadyon_app;

-- 202607010711_conversations
-- Migrations auto-run only on first boot of an empty DB volume. On an existing
-- database (e.g. the Mini-A) apply manually:
--   docker compose exec -T db psql -U aadyon -d aadyon_assist < code/db/init/202607010711_conversations.sql
--
-- Chat "brain" storage: a per-user conversation with the assistant, and the
-- turn-by-turn message log (user / assistant / tool). Both are user-scoped and
-- protected by the same RLS mechanism as the rest of the data.
-- Depends on: 202607010711_multiuser_auth.sql (users table + RLS pattern).

-- ---------------------------------------------------------------------------
-- CONVERSATIONS  (a chat thread)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversations (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title      text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_conversations_updated ON conversations;
CREATE TRIGGER trg_conversations_updated BEFORE UPDATE ON conversations
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations (user_id, updated_at DESC);

-- ---------------------------------------------------------------------------
-- MESSAGES  (one row per turn; mirrors the OpenAI chat message shape)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS messages (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role            text NOT NULL,          -- user | assistant | tool
  content         text,
  tool_calls      jsonb,                  -- assistant tool-call requests (raw)
  tool_call_id    text,                   -- for role=tool: which call this answers
  tool_name       text,                   -- for role=tool: the tool that ran
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_messages_convo ON messages (conversation_id, created_at);

-- RLS for both (fail-closed on unset GUC), FORCE because the app is table owner.
DO $c$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['conversations','messages'] LOOP
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (user_id)', 'idx_'||t||'_user', t);
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS %I ON %I', t||'_isolation', t);
    EXECUTE format(
      'CREATE POLICY %I ON %I '
      'USING (user_id = current_setting(''app.current_user_id'', true)::uuid) '
      'WITH CHECK (user_id = current_setting(''app.current_user_id'', true)::uuid)',
      t||'_isolation', t);
  END LOOP;
END $c$;

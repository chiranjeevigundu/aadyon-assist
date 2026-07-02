-- Aadyon Assist — P3: Document analysis
-- transaction

CREATE TABLE IF NOT EXISTS documents (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  filename     text NOT NULL,
  mime_type    text,
  storage_path text NOT NULL,
  size_bytes   int,
  status       text NOT NULL DEFAULT 'uploaded',
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_documents_updated ON documents;
CREATE TRIGGER trg_documents_updated BEFORE UPDATE ON documents
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_documents_user ON documents (user_id);

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS documents_isolation ON documents;
CREATE POLICY documents_isolation ON documents
  USING (user_id = current_setting('app.current_user_id', true)::uuid)
  WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);


CREATE TABLE IF NOT EXISTS document_extractions (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  document_id  uuid REFERENCES documents(id) ON DELETE CASCADE,
  kind         text NOT NULL DEFAULT 'info',
  payload      jsonb NOT NULL DEFAULT '{}',
  summary      text,
  status       text NOT NULL DEFAULT 'pending',
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_document_extractions_updated ON document_extractions;
CREATE TRIGGER trg_document_extractions_updated BEFORE UPDATE ON document_extractions
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_document_extractions_user ON document_extractions (user_id);
CREATE INDEX IF NOT EXISTS idx_document_extractions_status ON document_extractions (status, created_at);

ALTER TABLE document_extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_extractions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS document_extractions_isolation ON document_extractions;
CREATE POLICY document_extractions_isolation ON document_extractions
  USING (user_id = current_setting('app.current_user_id', true)::uuid)
  WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);

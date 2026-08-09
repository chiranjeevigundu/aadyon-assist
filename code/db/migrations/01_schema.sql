-- Aadyon Assist -- consolidated baseline schema (personal finance / net-worth app).
-- CLEAN-START BASELINE: supersedes the old incremental migration history (which
-- created many tables later dropped during the finance refocus). Generated from the
-- live schema via `pg_dump --schema-only`, plus the restricted app role below.
-- transaction

-- Restricted, non-superuser role the app connects as so RLS applies (the bootstrap
-- superuser bypasses RLS). Its LOGIN password is set by the migrate entrypoint from
-- the db_password secret. Must exist before the GRANTs below.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aadyon_app') THEN
    CREATE ROLE aadyon_app LOGIN;
  END IF;
END $$;

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE TABLE public.assets (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    name text NOT NULL,
    kind text DEFAULT 'other'::text NOT NULL,
    institution text,
    value numeric(14,2) DEFAULT 0 NOT NULL,
    currency text DEFAULT 'USD'::text NOT NULL,
    as_of date,
    active boolean DEFAULT true NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.assets FORCE ROW LEVEL SECURITY;

CREATE TABLE public.bank_accounts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    institution text NOT NULL,
    secret_enc text,
    last_sync timestamp with time zone,
    last_error text,
    active boolean DEFAULT true NOT NULL,
    status text DEFAULT 'not_connected'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    balance numeric
);

ALTER TABLE ONLY public.bank_accounts FORCE ROW LEVEL SECURITY;

CREATE TABLE public.bank_transactions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    account_id uuid,
    transaction_id text,
    date timestamp with time zone,
    amount numeric,
    merchant text,
    category text,
    status text DEFAULT 'pending'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.bank_transactions FORCE ROW LEVEL SECURITY;

CREATE TABLE public.bills (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    amount numeric(12,2) NOT NULL,
    frequency text DEFAULT 'monthly'::text NOT NULL,
    due_day integer,
    autopay boolean DEFAULT false NOT NULL,
    category text,
    active boolean DEFAULT true NOT NULL,
    notes text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    user_id uuid NOT NULL,
    last_seen date
);

ALTER TABLE ONLY public.bills FORCE ROW LEVEL SECURITY;

CREATE TABLE public.conversations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    title text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.conversations FORCE ROW LEVEL SECURITY;

CREATE TABLE public.deadlines (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    title text NOT NULL,
    category text DEFAULT 'general'::text NOT NULL,
    due_date date NOT NULL,
    status text DEFAULT 'open'::text NOT NULL,
    priority integer DEFAULT 3 NOT NULL,
    blocked_on text,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    user_id uuid NOT NULL
);

ALTER TABLE ONLY public.deadlines FORCE ROW LEVEL SECURITY;

CREATE TABLE public.debts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    kind text DEFAULT 'card'::text NOT NULL,
    balance numeric(12,2) NOT NULL,
    apr numeric(5,2) NOT NULL,
    min_payment numeric(12,2) DEFAULT 0 NOT NULL,
    credit_limit numeric(12,2),
    priority_rank integer,
    notes text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    due_date date,
    installment_amount numeric(12,2),
    term_months integer,
    installments_paid integer,
    user_id uuid NOT NULL
);

ALTER TABLE ONLY public.debts FORCE ROW LEVEL SECURITY;

CREATE VIEW public.debt_summary WITH (security_invoker='true') AS
 SELECT name,
    kind,
    balance,
    apr,
    min_payment,
    credit_limit,
    priority_rank,
        CASE
            WHEN (credit_limit > (0)::numeric) THEN round(((balance / credit_limit) * (100)::numeric), 1)
            ELSE NULL::numeric
        END AS utilization_pct,
    round((((balance * apr) / (100)::numeric) / (12)::numeric), 2) AS est_monthly_interest,
    id
   FROM public.debts
  ORDER BY priority_rank, apr DESC;

CREATE TABLE public.document_extractions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    document_id uuid,
    kind text DEFAULT 'info'::text NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    summary text,
    status text DEFAULT 'pending'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.document_extractions FORCE ROW LEVEL SECURITY;

CREATE TABLE public.documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    filename text NOT NULL,
    mime_type text,
    storage_path text NOT NULL,
    size_bytes integer,
    status text DEFAULT 'uploaded'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.documents FORCE ROW LEVEL SECURITY;

CREATE TABLE public.email_accounts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    email text NOT NULL,
    provider text DEFAULT 'other'::text NOT NULL,
    purpose text,
    auth_type text DEFAULT 'imap'::text NOT NULL,
    imap_host text,
    imap_port integer,
    status text DEFAULT 'not_connected'::text NOT NULL,
    last_sync timestamp with time zone,
    last_error text,
    active boolean DEFAULT true NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    secret_enc text,
    last_uid bigint,
    uid_validity bigint,
    user_id uuid NOT NULL
);

ALTER TABLE ONLY public.email_accounts FORCE ROW LEVEL SECURITY;

CREATE TABLE public.email_extractions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    account_id uuid,
    message_uid text,
    message_date timestamp with time zone,
    sender text,
    subject text,
    kind text DEFAULT 'info'::text NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    summary text,
    status text DEFAULT 'pending'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    user_id uuid NOT NULL
);

ALTER TABLE ONLY public.email_extractions FORCE ROW LEVEL SECURITY;

CREATE TABLE public.invite_codes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code text NOT NULL,
    note text,
    created_by uuid,
    used_by uuid,
    used_at timestamp with time zone,
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.jobs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    employer text NOT NULL,
    role text,
    kind text DEFAULT 'part_time_hourly'::text NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    hourly_rate numeric(8,2),
    annual_salary numeric(12,2),
    remittance_pct integer DEFAULT 0 NOT NULL,
    start_date date,
    end_date date,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    user_id uuid NOT NULL
);

ALTER TABLE ONLY public.jobs FORCE ROW LEVEL SECURITY;

CREATE TABLE public.memory_chunks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source text,
    content text NOT NULL,
    embedding public.vector(1536),
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    user_id uuid NOT NULL
);

ALTER TABLE ONLY public.memory_chunks FORCE ROW LEVEL SECURITY;

CREATE TABLE public.messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    conversation_id uuid NOT NULL,
    user_id uuid NOT NULL,
    role text NOT NULL,
    content text,
    tool_calls jsonb,
    tool_call_id text,
    tool_name text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.messages FORCE ROW LEVEL SECURITY;

CREATE TABLE public.net_worth_snapshots (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    snapshot_date date DEFAULT CURRENT_DATE NOT NULL,
    total_assets numeric(14,2) DEFAULT 0 NOT NULL,
    total_liabilities numeric(14,2) DEFAULT 0 NOT NULL,
    net_worth numeric(14,2) DEFAULT 0 NOT NULL,
    currency text DEFAULT 'USD'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.net_worth_snapshots FORCE ROW LEVEL SECURITY;

CREATE TABLE public.profile (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    full_name text NOT NULL,
    preferred_name text,
    birthdate date,
    birthplace text,
    location text,
    nationality text,
    headline text,
    bio text,
    target_role text,
    target_salary numeric(12,2),
    current_income numeric(12,2),
    remittance_pct integer,
    monthly_essential_expenses numeric(12,2),
    goal_title text,
    goal_target_date date,
    life_expectancy_years integer DEFAULT 80 NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    user_id uuid NOT NULL
);

ALTER TABLE ONLY public.profile FORCE ROW LEVEL SECURITY;

CREATE TABLE public.proposals (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    title text NOT NULL,
    detail text,
    category text,
    status text DEFAULT 'pending'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE ONLY public.proposals FORCE ROW LEVEL SECURITY;

CREATE TABLE public.shifts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    employer text NOT NULL,
    role text,
    shift_date date NOT NULL,
    start_time time without time zone,
    end_time time without time zone,
    hours numeric(5,2),
    hourly_rate numeric(8,2),
    est_pay numeric(10,2),
    status text DEFAULT 'scheduled'::text NOT NULL,
    notes text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    user_id uuid NOT NULL
);

ALTER TABLE ONLY public.shifts FORCE ROW LEVEL SECURITY;

CREATE TABLE public.subscriptions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    amount numeric(12,2) NOT NULL,
    billing_cycle text DEFAULT 'monthly'::text NOT NULL,
    renews_on date,
    category text,
    active boolean DEFAULT true NOT NULL,
    notes text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    user_id uuid NOT NULL,
    last_seen date
);

ALTER TABLE ONLY public.subscriptions FORCE ROW LEVEL SECURITY;

CREATE TABLE public.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    email text NOT NULL,
    password_hash text NOT NULL,
    display_name text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    ntfy_topic text,
    email_verified boolean DEFAULT false NOT NULL,
    monthly_token_budget integer,
    tokens_used integer DEFAULT 0 NOT NULL,
    usage_period_start date
);

CREATE TABLE public.work_schedule (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    job_id uuid NOT NULL,
    day_of_week integer NOT NULL,
    start_time time without time zone,
    end_time time without time zone,
    hours numeric(5,2) NOT NULL,
    active boolean DEFAULT true NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    user_id uuid NOT NULL,
    CONSTRAINT work_schedule_day_of_week_check CHECK (((day_of_week >= 0) AND (day_of_week <= 6)))
);

ALTER TABLE ONLY public.work_schedule FORCE ROW LEVEL SECURITY;

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT assets_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.bank_accounts
    ADD CONSTRAINT bank_accounts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.bank_transactions
    ADD CONSTRAINT bank_transactions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.bills
    ADD CONSTRAINT bills_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.deadlines
    ADD CONSTRAINT deadlines_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.debts
    ADD CONSTRAINT debts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.document_extractions
    ADD CONSTRAINT document_extractions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.email_accounts
    ADD CONSTRAINT email_accounts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.email_extractions
    ADD CONSTRAINT email_extractions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.invite_codes
    ADD CONSTRAINT invite_codes_code_key UNIQUE (code);

ALTER TABLE ONLY public.invite_codes
    ADD CONSTRAINT invite_codes_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.memory_chunks
    ADD CONSTRAINT memory_chunks_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.net_worth_snapshots
    ADD CONSTRAINT net_worth_snapshots_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.net_worth_snapshots
    ADD CONSTRAINT net_worth_snapshots_user_id_snapshot_date_key UNIQUE (user_id, snapshot_date);

ALTER TABLE ONLY public.profile
    ADD CONSTRAINT profile_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.proposals
    ADD CONSTRAINT proposals_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.shifts
    ADD CONSTRAINT shifts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.work_schedule
    ADD CONSTRAINT work_schedule_pkey PRIMARY KEY (id);

CREATE INDEX idx_assets_user ON public.assets USING btree (user_id);

CREATE INDEX idx_bank_accounts_user ON public.bank_accounts USING btree (user_id);

CREATE INDEX idx_bank_transactions_status ON public.bank_transactions USING btree (status, created_at);

CREATE INDEX idx_bank_transactions_user ON public.bank_transactions USING btree (user_id);

CREATE INDEX idx_bills_user ON public.bills USING btree (user_id);

CREATE INDEX idx_conversations_user ON public.conversations USING btree (user_id, updated_at DESC);

CREATE INDEX idx_deadlines_due ON public.deadlines USING btree (due_date) WHERE (status <> 'done'::text);

CREATE INDEX idx_deadlines_user ON public.deadlines USING btree (user_id);

CREATE INDEX idx_debts_user ON public.debts USING btree (user_id);

CREATE INDEX idx_document_extractions_status ON public.document_extractions USING btree (status, created_at);

CREATE INDEX idx_document_extractions_user ON public.document_extractions USING btree (user_id);

CREATE INDEX idx_documents_user ON public.documents USING btree (user_id);

CREATE INDEX idx_email_accounts_active ON public.email_accounts USING btree (active);

CREATE INDEX idx_email_accounts_user ON public.email_accounts USING btree (user_id);

CREATE INDEX idx_email_extractions_status ON public.email_extractions USING btree (status, created_at);

CREATE INDEX idx_email_extractions_user ON public.email_extractions USING btree (user_id);

CREATE INDEX idx_invite_codes_code ON public.invite_codes USING btree (code) WHERE (used_at IS NULL);

CREATE INDEX idx_jobs_status ON public.jobs USING btree (status);

CREATE INDEX idx_jobs_user ON public.jobs USING btree (user_id);

CREATE INDEX idx_memory_chunks_user ON public.memory_chunks USING btree (user_id);

CREATE INDEX idx_messages_convo ON public.messages USING btree (conversation_id, created_at);

CREATE INDEX idx_messages_user ON public.messages USING btree (user_id);

CREATE INDEX idx_net_worth_snapshots_user ON public.net_worth_snapshots USING btree (user_id, snapshot_date);

CREATE INDEX idx_profile_user ON public.profile USING btree (user_id);

CREATE INDEX idx_proposals_user ON public.proposals USING btree (user_id, status);

CREATE INDEX idx_shifts_date ON public.shifts USING btree (shift_date);

CREATE INDEX idx_shifts_user ON public.shifts USING btree (user_id);

CREATE INDEX idx_subscriptions_user ON public.subscriptions USING btree (user_id);

CREATE INDEX idx_work_schedule_job ON public.work_schedule USING btree (job_id);

CREATE INDEX idx_work_schedule_user ON public.work_schedule USING btree (user_id);

CREATE UNIQUE INDEX one_profile_per_user ON public.profile USING btree (user_id);

CREATE UNIQUE INDEX uq_bank_transactions_msg ON public.bank_transactions USING btree (account_id, transaction_id) WHERE (transaction_id IS NOT NULL);

CREATE UNIQUE INDEX uq_bills_user_name_active ON public.bills USING btree (user_id, lower(name)) WHERE active;

CREATE UNIQUE INDEX uq_email_accounts_user_email ON public.email_accounts USING btree (user_id, email);

CREATE UNIQUE INDEX uq_email_extractions_msg ON public.email_extractions USING btree (account_id, message_uid) WHERE (message_uid IS NOT NULL);

CREATE UNIQUE INDEX uq_subscriptions_user_name_active ON public.subscriptions USING btree (user_id, lower(name)) WHERE active;

CREATE TRIGGER trg_assets_updated BEFORE UPDATE ON public.assets FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_bank_accounts_updated BEFORE UPDATE ON public.bank_accounts FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_bank_transactions_updated BEFORE UPDATE ON public.bank_transactions FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_bills_updated BEFORE UPDATE ON public.bills FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_conversations_updated BEFORE UPDATE ON public.conversations FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_deadlines_updated BEFORE UPDATE ON public.deadlines FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_debts_updated BEFORE UPDATE ON public.debts FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_document_extractions_updated BEFORE UPDATE ON public.document_extractions FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_documents_updated BEFORE UPDATE ON public.documents FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_email_accounts_updated BEFORE UPDATE ON public.email_accounts FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_email_extractions_updated BEFORE UPDATE ON public.email_extractions FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_jobs_updated BEFORE UPDATE ON public.jobs FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_net_worth_snapshots_updated BEFORE UPDATE ON public.net_worth_snapshots FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_profile_updated BEFORE UPDATE ON public.profile FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_proposals_updated BEFORE UPDATE ON public.proposals FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_shifts_updated BEFORE UPDATE ON public.shifts FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_subscriptions_updated BEFORE UPDATE ON public.subscriptions FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_users_updated BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_work_schedule_updated BEFORE UPDATE ON public.work_schedule FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT assets_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.bank_accounts
    ADD CONSTRAINT bank_accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.bank_transactions
    ADD CONSTRAINT bank_transactions_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.bank_accounts(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.bank_transactions
    ADD CONSTRAINT bank_transactions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.document_extractions
    ADD CONSTRAINT document_extractions_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.document_extractions
    ADD CONSTRAINT document_extractions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.email_extractions
    ADD CONSTRAINT email_extractions_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.email_accounts(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.bills
    ADD CONSTRAINT fk_bills_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.deadlines
    ADD CONSTRAINT fk_deadlines_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.debts
    ADD CONSTRAINT fk_debts_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.email_accounts
    ADD CONSTRAINT fk_email_accounts_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.email_extractions
    ADD CONSTRAINT fk_email_extractions_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT fk_jobs_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.memory_chunks
    ADD CONSTRAINT fk_memory_chunks_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.profile
    ADD CONSTRAINT fk_profile_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.shifts
    ADD CONSTRAINT fk_shifts_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT fk_subscriptions_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.work_schedule
    ADD CONSTRAINT fk_work_schedule_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.invite_codes
    ADD CONSTRAINT invite_codes_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.invite_codes
    ADD CONSTRAINT invite_codes_used_by_fkey FOREIGN KEY (used_by) REFERENCES public.users(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.net_worth_snapshots
    ADD CONSTRAINT net_worth_snapshots_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.proposals
    ADD CONSTRAINT proposals_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.work_schedule
    ADD CONSTRAINT work_schedule_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.jobs(id) ON DELETE CASCADE;

ALTER TABLE public.assets ENABLE ROW LEVEL SECURITY;

CREATE POLICY assets_isolation ON public.assets USING ((user_id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((user_id = (current_setting('app.current_user_id'::text, true))::uuid));

ALTER TABLE public.bank_accounts ENABLE ROW LEVEL SECURITY;

CREATE POLICY bank_accounts_isolation ON public.bank_accounts USING ((user_id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((user_id = (current_setting('app.current_user_id'::text, true))::uuid));

ALTER TABLE public.bank_transactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY bank_transactions_isolation ON public.bank_transactions USING ((user_id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((user_id = (current_setting('app.current_user_id'::text, true))::uuid));

ALTER TABLE public.bills ENABLE ROW LEVEL SECURITY;

CREATE POLICY bills_isolation ON public.bills USING ((user_id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((user_id = (current_setting('app.current_user_id'::text, true))::uuid));

ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;

CREATE POLICY conversations_isolation ON public.conversations USING ((user_id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((user_id = (current_setting('app.current_user_id'::text, true))::uuid));

ALTER TABLE public.deadlines ENABLE ROW LEVEL SECURITY;

CREATE POLICY deadlines_isolation ON public.deadlines USING ((user_id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((user_id = (current_setting('app.current_user_id'::text, true))::uuid));

ALTER TABLE public.debts ENABLE ROW LEVEL SECURITY;

CREATE POLICY debts_isolation ON public.debts USING ((user_id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((user_id = (current_setting('app.current_user_id'::text, true))::uuid));

ALTER TABLE public.document_extractions ENABLE ROW LEVEL SECURITY;

CREATE POLICY document_extractions_isolation ON public.document_extractions USING ((user_id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((user_id = (current_setting('app.current_user_id'::text, true))::uuid));

ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY documents_isolation ON public.documents USING ((user_id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((user_id = (current_setting('app.current_user_id'::text, true))::uuid));

ALTER TABLE public.email_accounts ENABLE ROW LEVEL SECURITY;

CREATE POLICY email_accounts_isolation ON public.email_accounts USING ((user_id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((user_id = (current_setting('app.current_user_id'::text, true))::uuid));

ALTER TABLE public.email_extractions ENABLE ROW LEVEL SECURITY;

CREATE POLICY email_extractions_isolation ON public.email_extractions USING ((user_id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((user_id = (current_setting('app.current_user_id'::text, true))::uuid));

ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY jobs_isolation ON public.jobs USING ((user_id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((user_id = (current_setting('app.current_user_id'::text, true))::uuid));

ALTER TABLE public.memory_chunks ENABLE ROW LEVEL SECURITY;

CREATE POLICY memory_chunks_isolation ON public.memory_chunks USING ((user_id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((user_id = (current_setting('app.current_user_id'::text, true))::uuid));

ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY messages_isolation ON public.messages USING ((user_id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((user_id = (current_setting('app.current_user_id'::text, true))::uuid));

ALTER TABLE public.net_worth_snapshots ENABLE ROW LEVEL SECURITY;

CREATE POLICY net_worth_snapshots_isolation ON public.net_worth_snapshots USING ((user_id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((user_id = (current_setting('app.current_user_id'::text, true))::uuid));

ALTER TABLE public.profile ENABLE ROW LEVEL SECURITY;

CREATE POLICY profile_isolation ON public.profile USING ((user_id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((user_id = (current_setting('app.current_user_id'::text, true))::uuid));

ALTER TABLE public.proposals ENABLE ROW LEVEL SECURITY;

CREATE POLICY proposals_isolation ON public.proposals USING ((user_id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((user_id = (current_setting('app.current_user_id'::text, true))::uuid));

ALTER TABLE public.shifts ENABLE ROW LEVEL SECURITY;

CREATE POLICY shifts_isolation ON public.shifts USING ((user_id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((user_id = (current_setting('app.current_user_id'::text, true))::uuid));

ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY subscriptions_isolation ON public.subscriptions USING ((user_id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((user_id = (current_setting('app.current_user_id'::text, true))::uuid));

ALTER TABLE public.work_schedule ENABLE ROW LEVEL SECURITY;

CREATE POLICY work_schedule_isolation ON public.work_schedule USING ((user_id = (current_setting('app.current_user_id'::text, true))::uuid)) WITH CHECK ((user_id = (current_setting('app.current_user_id'::text, true))::uuid));

GRANT USAGE ON SCHEMA public TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.assets TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.bank_accounts TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.bank_transactions TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.bills TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.conversations TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.deadlines TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.debts TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.debt_summary TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.document_extractions TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.documents TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.email_accounts TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.email_extractions TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.invite_codes TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.jobs TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.memory_chunks TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.messages TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.net_worth_snapshots TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.profile TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.proposals TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.shifts TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.subscriptions TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.users TO aadyon_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.work_schedule TO aadyon_app;

ALTER DEFAULT PRIVILEGES FOR ROLE aadyon IN SCHEMA public GRANT ALL ON FUNCTIONS TO aadyon_app;

ALTER DEFAULT PRIVILEGES FOR ROLE aadyon IN SCHEMA public GRANT SELECT,INSERT,DELETE,UPDATE ON TABLES TO aadyon_app;

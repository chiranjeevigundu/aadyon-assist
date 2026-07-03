-- The bootstrap role (POSTGRES_USER) is always a Postgres superuser and always
-- bypasses row-level security -- Postgres has no way to opt a superuser back
-- into RLS (ALTER ROLE ... NOSUPERUSER on the bootstrap role itself is refused:
-- "the bootstrap user must have the SUPERUSER attribute"). So FORCE ROW LEVEL
-- SECURITY on every per-user table has never actually restricted anything,
-- since the API has only ever connected as that superuser. A second, ordinary
-- role is required for RLS to have any effect. `migrate` keeps connecting as
-- the superuser for DDL/extensions; api/briefing/agency connect as this role
-- (see docker-compose.yml DB_USER + core/config.py). Its login password is set
-- separately by the migrate entrypoint from the db_password secret, since SQL
-- migrations can't read Docker secret files.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aadyon_app') THEN
    CREATE ROLE aadyon_app LOGIN;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO aadyon_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aadyon_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO aadyon_app;
GRANT EXECUTE ON FUNCTION seed_org(uuid) TO aadyon_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO aadyon_app;

-- Views check the underlying tables' RLS policies as the VIEW OWNER by default
-- (still the superuser), not the querying role -- without security_invoker,
-- debt_summary would keep silently bypassing RLS even for aadyon_app.
ALTER VIEW debt_summary SET (security_invoker = true);

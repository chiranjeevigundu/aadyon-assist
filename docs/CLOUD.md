# Migrating Aadyon Assist to a cloud platform

The stack runs today on a single always-on host (the Mac Mini) via `docker compose`.
Nothing about it is tied to that host — this is the tested path to a managed cloud
platform (AWS / GCP / Fly.io / Render / a plain VM). The two things that differ in the
cloud — where Postgres lives and where uploaded files live — are already config switches,
not code changes.

## What's already cloud-ready

- **Object storage is a config flip.** `STORAGE_BACKEND=s3` routes document uploads to any
  S3-compatible store (AWS S3, GCS via its S3 interop endpoint, Cloudflare R2, MinIO). The
  default `local` persists to `artifacts_dir/uploads`, which is correct for one host but
  does **not** work across multiple API instances — switch to `s3` before scaling out.
  Verified end-to-end against MinIO (upload + download round-trip through `services/storage.py`).
- **Managed-Postgres-safe connection pooling.** `db/session.py` recycles connections the
  server has dropped and retries once on connection-level errors. Managed databases
  (RDS/Cloud SQL) reap idle connections aggressively; without this the app 500s intermittently.
- **Schema is migration-driven.** All DDL is in `code/db/migrations/`, applied by the
  one-shot `migrate` service (yoyo ledger in `_yoyo_*`). Point it at the cloud database and
  run it; it applies only what's new. Existing DB? Baseline once (`just migrate-baseline`).
- **RLS multi-tenancy.** Per-user isolation is enforced in the database (the restricted
  `aadyon_app` role + row-level security), so it holds regardless of where the app runs.
- **Stateless API.** The API keeps no local session state (JWT bearer tokens), so it scales
  horizontally once storage is on S3.

## Migration steps

1. **Provision a managed Postgres 16** with the `vector` + `pgcrypto` extensions (see
   `01_schema.sql`). RDS/Cloud SQL/Neon/Supabase all work. Create the database and the
   bootstrap superuser (used only by `migrate`).
2. **Provision object storage** (S3 bucket / R2 / GCS). Keep it private — never public.
3. **Move secrets to the platform's secret manager** (AWS Secrets Manager, GCP Secret
   Manager, Fly secrets). The app reads each secret from a file path *or* an env var (see
   `core/config.py` — every secret has a `*_FILE` and a plain-env fallback), so mount them as
   files or inject as env vars, whichever the platform prefers. Required: `db_password`,
   `jwt_secret`, `openrouter_api_key`; for S3: the access/secret keys; for email: `email_key`.
4. **Set env** for the API / briefing / agency services:
   - `DB_HOST` / `DB_PORT` / `POSTGRES_DB` → the managed database; `DB_USER=aadyon_app`.
   - `STORAGE_BACKEND=s3`, `S3_BUCKET_NAME`, and `S3_ENDPOINT_URL` (omit for AWS S3 proper;
     set it for R2/GCS/MinIO).
5. **Run migrations** once against the cloud DB (the `migrate` job also provisions the
   `aadyon_app` role's password from the `db_password` secret). Confirm it exits 0.
6. **Deploy the three long-running services** (api, briefing, agency) as containers — the same
   images built from `code/api/Dockerfile`. The `backup`/`ntfy` compose services are
   optional in cloud (use the platform's managed backups; use a hosted ntfy or drop push).
7. **Scale**: because storage is on S3 and the API is stateless, run N API replicas behind the
   platform's load balancer. Keep `briefing` and `agency` at one replica each (they're
   schedulers/workers, not request handlers).

## Gotchas

- **`STORAGE_BACKEND=local` + multiple replicas = lost files.** Each replica has its own disk.
  Always use `s3` when running more than one API instance.
- **Don't expose the database or bucket publicly.** Keep the DB on a private subnet; the
  bucket private with signed access only through the app.
- **The `mock` storage backend is for tests only** — never set it in a real environment.
- **Connection limits.** Managed Postgres tiers cap connections; the pool is `maxconn=10` per
  process, so N replicas use ~10N. Size the tier (or add PgBouncer) accordingly.

# Hosting Aadyon Assist anywhere

Aadyon Assist is a plain Docker workload. Hosting it on **any** cloud or VM is the
same three things:

1. a **managed Postgres 16** (with the `vector` + `pgcrypto` extensions),
2. an **object store** for uploaded files (any S3-compatible bucket), and
3. **running the API container** (plus the `briefing` and `agency` workers).

Everything that differs between providers is **configuration, not code** — see the
[env reference](#the-only-things-that-change-env) below. This doc is the universal
recipe + a per-provider mapping. For background on *why* it's portable, see
[CLOUD.md](CLOUD.md); for a fully-worked example, see
[AWS_EC2_DEPLOY.md](AWS_EC2_DEPLOY.md).

> **Portability fixes that make this true** (landed with this guide): the `migrate`
> service now honors `DB_HOST`/`DB_PORT`/`DB_SSLMODE` instead of hardcoding the local
> `db` container; the app takes an optional `DB_SSLMODE` (for managed DBs that force
> TLS); and the S3 client accepts a region and falls back to the cloud's default
> credential chain (instance role / workload identity) when no keys are given.

---

## The universal recipe

On any host that can run Docker:

```bash
git clone https://github.com/chiranjeevigundu/aadyon-assist.git && cd aadyon-assist
cp .env.production.example .env        # then edit per the table below
mkdir -p secrets && chmod 700 secrets
# db_password.txt = the password for BOTH the managed DB admin user and the app role
printf '%s' 'STRONG_DB_PASSWORD'                    > secrets/db_password.txt
python3 -c "import secrets;print(secrets.token_urlsafe(48))" > secrets/jwt_secret.txt
printf '%s' 'S3_ACCESS_KEY'  > secrets/s3_access_key.txt   # or empty => instance role
printf '%s' 'S3_SECRET_KEY'  > secrets/s3_secret_key.txt
printf ''                    > secrets/resend_api_key.txt
chmod 600 secrets/*.txt

# 1) create the DB's extensions once (any psql client):
#    CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pgcrypto;
# 2) apply migrations + set the app role's password (points at your managed DB via .env):
just migrate                # = docker compose run --rm migrate
# 3) run the long-running services (no local db/backup containers needed):
docker compose up -d --build --no-deps api briefing agency
curl -s localhost:8000/api/health     # => {"status":"ok","db":"up"}
```

Because the API is stateless (JWT auth) and files live in the object store, you can
run N `api` replicas behind any load balancer; keep `briefing` and `agency` at one
replica each (they're schedulers/workers).

### The only things that change (env)

Set these in `.env` (the app reads secret **files** or plain **env vars** — see
`core/config.py`; every secret has a `*_FILE` and an env fallback).

| Variable | What it's for | Local default | In the cloud |
|---|---|---|---|
| `DB_HOST` / `DB_PORT` | managed Postgres endpoint | `db` / `5432` | your managed endpoint |
| `POSTGRES_DB` | database name | `aadyon_assist` | your DB name |
| `POSTGRES_USER` | **admin** role (migrate/DDL only) | `aadyon` | the managed admin user |
| `DB_USER` | **app** role — RLS applies to it | `aadyon_app` | `aadyon_app` (keep) |
| `DB_SSLMODE` | TLS enforcement | empty (`prefer`) | `require` (managed DBs force TLS) |
| `STORAGE_BACKEND` | `local` / `s3` / `mock` | `local` | `s3` (or `local` for a single VM) |
| `S3_BUCKET_NAME` | bucket | `aadyon-assist` | your bucket |
| `S3_ENDPOINT_URL` | non-AWS S3 endpoint | empty | set for R2/GCS/MinIO; empty for AWS |
| `S3_REGION` / `AWS_REGION` | bucket region | empty | your region |
| `secrets/s3_*` | object-store keys | `ci` placeholder | IAM keys, **or empty** to use the instance role / workload identity |
| `secrets/db_password.txt` | DB admin + app password | dev value | your strong password |
| `OPENROUTER_API_KEY` | LLM (from `.env`) | — | your key (or a secret-manager injection) |

**Password model:** the `migrate` step connects as `POSTGRES_USER` and sets the
`aadyon_app` role's password, both from `secrets/db_password.txt`. Simplest path:
give your managed DB's **admin user the same password** as that secret. To keep the
admin and app passwords distinct, run migrations manually with the admin credential
(see [AWS_EC2_DEPLOY.md](AWS_EC2_DEPLOY.md) Step 6) — the app still connects only as
the restricted `aadyon_app`.

---

## Per-provider mapping

Every row is the same recipe; only the two managed pieces (Postgres, object store)
and the compute wrapper change.

### AWS
- **Postgres:** RDS for PostgreSQL 16 (enable `vector` in a parameter group).
- **Object store:** S3 (`S3_ENDPOINT_URL` empty; set `AWS_REGION`). Keys via an IAM
  user, or leave the key files empty and attach an S3 policy to the instance role.
- **Compute:** EC2 + docker-compose (**[full runbook →](AWS_EC2_DEPLOY.md)**), or ECS
  Fargate / App Runner running the same image.

### Azure
- **Postgres:** Azure Database for PostgreSQL **Flexible Server** 16 — enable the
  `vector` + `pgcrypto` extensions (Server parameters → `azure.extensions`). It
  **forces TLS**, so set `DB_SSLMODE=require`.
- **Object store:** Azure Blob is **not S3-compatible**. Options: (a) a single VM →
  `STORAGE_BACKEND=local` (files on the disk — fine for one instance); (b) use
  **Cloudflare R2** or MinIO (S3 API) via `S3_ENDPOINT_URL`; (c) run a MinIO gateway.
- **Compute:** a VM (Ubuntu) + docker-compose, or Azure Container Apps running the image.

### Google Cloud
- **Postgres:** Cloud SQL for PostgreSQL 16 (`vector` supported). TLS: `DB_SSLMODE=require`.
- **Object store:** GCS via its **S3 interoperability** endpoint — set
  `S3_ENDPOINT_URL=https://storage.googleapis.com`, `S3_REGION=auto`, and use an
  **HMAC key** as the S3 access/secret. (Or leave keys empty and use the workload
  identity of the GCE/GKE node.)
- **Compute:** GCE VM + docker-compose, or Cloud Run running the `api` image.

### Fly.io / Render / Railway
- **Postgres:** the platform's managed Postgres, or Neon/Supabase (all ship `vector`).
- **Object store:** Cloudflare R2 or Tigris (S3 API) via `S3_ENDPOINT_URL`.
- **Compute:** deploy the `code/api/Dockerfile` image; set the env above as platform
  secrets. Run `api` as the web service and `briefing`/`agency` as separate workers.

### Any plain VM (DigitalOcean, Linode, Hetzner, on-prem)
- Run the **whole compose file unchanged** (including the `db` and `backup`
  containers) — that's the Mac-Mini setup on a rented box. Or point `DB_HOST` at a
  managed Postgres and drop `db`/`backup`, exactly like the cloud recipe above.

---

## Notes that apply everywhere

- **pgvector + pgcrypto must exist.** `01_schema.sql` runs `CREATE EXTENSION` for
  both; the managed tier must allow them (RDS/Azure Flexible/Cloud SQL/Neon/Supabase
  all do). Create them once before `just migrate`.
- **Keep the DB and bucket private.** DB on a private subnet reachable only from the
  app; bucket with public access blocked (signed access through the app only).
- **Never use `STORAGE_BACKEND=mock` outside tests** — it discards writes.
- **Enforce TLS to managed Postgres** with `DB_SSLMODE=require` (or `verify-full` with
  the provider CA). Unset falls back to libpq `prefer`, which still negotiates TLS but
  allows a silent downgrade.
- **Connection limits:** the pool is `maxconn=10` per process (≈30 across
  api+briefing+agency); size the DB tier or add PgBouncer before scaling replicas.
- **Access model:** keep the API off the public internet where practical — Tailscale,
  a private LB, or HTTPS-only via a reverse proxy. `/api/health` and `/api/auth/*` are
  the only routes meant to be reachable pre-auth.
```

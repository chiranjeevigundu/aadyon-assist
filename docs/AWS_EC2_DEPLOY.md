# Deploying Aadyon Assist to AWS — single EC2 + docker-compose + RDS

A concrete runbook for standing this stack up on AWS the simplest way: **one EC2
instance running the existing `docker-compose` services**, with **Postgres on RDS**
and **uploads on S3**. It's the closest shape to the current Mac-Mini deployment —
cheapest, fewest moving parts — and preserves the project's security model
(private DB, Tailscale-fronted API, RLS multi-tenancy).

This is a *plan*, not IaC: every step is something you do in the AWS console (the
one you have open) or over SSH. Nothing here provisions resources on its own.
Read [CLOUD.md](CLOUD.md) for *why* the app is already cloud-portable, and
[HOSTING.md](HOSTING.md) for the provider-agnostic recipe (this AWS EC2 doc is its
worked example); this doc is the *how* for the EC2+RDS shape.

> The `migrate` service now honors `DB_HOST`/`DB_PORT`/`DB_SSLMODE` (it used to
> hardcode the local `db` container), so the stock `just migrate` works against RDS
> once `.env` points at it — see Step 6.

> Target from your console: account **417722285818**, region **us-east-1**
> (N. Virginia). Adjust if you deploy elsewhere.

---

## Architecture

```
                 Tailscale (private)                 AWS VPC (us-east-1)
   ┌─────────┐   or HTTPS via Caddy    ┌───────────────────────────────────────┐
   │ your    │ ──────────────────────► │  EC2  (t3.medium, Amazon Linux 2023)   │
   │ phone / │                         │   docker compose:                      │
   │ laptop  │                         │     api (:8000)  briefing  agency  ntfy│
   └─────────┘                         │        │            │        │         │
                                       │        └──────┬─────┴────────┘         │
                                       │               │ 5432 (SG→SG, private)  │
                                       │        ┌──────▼───────┐   ┌──────────┐ │
                                       │        │ RDS Postgres │   │   S3     │ │
                                       │        │ 16 + pgvector│   │ uploads  │ │
                                       │        └──────────────┘   └──────────┘ │
                                       └───────────────────────────────────────┘
```

What changes vs. the Mac-Mini compose:
- The `db` container is **dropped** — Postgres is RDS.
- The `backup` container is **dropped** — use RDS automated backups + snapshots.
- `api` / `briefing` / `agency` (and optionally `ntfy`) run unchanged, pointed at RDS + S3.

---

## Cost sketch (on-demand, us-east-1)

| Resource | Suggested size | ~Monthly |
|---|---|---|
| EC2 | t3.medium (2 vCPU / 4 GB) | ~$30 |
| EBS | gp3 30 GB | ~$2.40 |
| RDS | db.t4g.micro (2 GB), 20 GB gp3, single-AZ | ~$13 |
| S3 | a few GB + requests | < $1 |
| Data transfer | light, personal use | ~$1 |
| **Total** | | **~$45–50/mo** |

A **new account (yours) likely still has Free Tier**: 750 h/mo of a t3.micro-class
EC2, 750 h/mo of db.t3.micro RDS, and 5 GB S3 for 12 months — enough to run this
near-$0 if you downsize EC2→t3.micro and RDS→db.t3.micro (tighter on RAM; watch the
API + agency memory). Set a **Billing budget alert** first (Billing → Budgets).

---

## Step 0 — decisions & prerequisites

- **Region:** us-east-1 (matches your open console).
- **Access model:** Tailscale (recommended — keeps the API off the public internet,
  matching golden rule #3) *or* public HTTPS via a reverse proxy + domain. This
  runbook does Tailscale, with the HTTPS option in Step 7.
- **Two distinct DB passwords** (important — the compose uses one secret for both;
  on RDS they're separate):
  1. **RDS master password** — used only by migrations/DDL (the `migrate` step).
  2. **`aadyon_app` password** — what the app connects with; this is the value in
     `secrets/db_password.txt`. You set it on the `aadyon_app` role during migration.
- Have your `OPENROUTER_API_KEY` and (optional) `EMAIL_ENC_KEY` ready — these come
  from `.env`, not Docker secrets (see AGENTS.md rule 4).

---

## Step 1 — S3 bucket + IAM user for uploads

1. **S3 → Create bucket**, e.g. `aadyon-assist-uploads-417722285818` (globally
   unique), region us-east-1, **Block all public access = ON**, default encryption
   (SSE-S3) on. Leave versioning off (or on, your call).
2. **IAM → Users → Create user** `aadyon-assist-s3`, no console access. Attach an
   inline policy scoped to the bucket:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       { "Effect": "Allow",
         "Action": ["s3:GetObject","s3:PutObject","s3:DeleteObject"],
         "Resource": "arn:aws:s3:::aadyon-assist-uploads-417722285818/*" },
       { "Effect": "Allow", "Action": ["s3:ListBucket"],
         "Resource": "arn:aws:s3:::aadyon-assist-uploads-417722285818" }
     ]
   }
   ```
3. Create an **access key** for that user; you'll drop it into
   `secrets/s3_access_key.txt` / `secrets/s3_secret_key.txt` in Step 4.

> Why an IAM user and not the EC2 instance role? `services/storage.py::get_s3_client()`
> passes credentials **explicitly** and returns `None` if they're empty — it does not
> fall back to the instance-profile credential chain. To use an instance role instead,
> change that function to pass `None` when the keys are blank (so boto3 uses the default
> chain) and attach the S3 policy to the instance role. Until then, use the IAM-user keys.

---

## Step 2 — RDS Postgres 16

1. **RDS → Parameter groups → Create** (family `postgres16`), name
   `aadyon-pg16`. This stack needs the `vector` extension available and, unless you
   want to configure TLS, force-SSL relaxed:
   - `shared_preload_libraries` — leave default (pgvector doesn't require preload).
   - `rds.force_ssl = 0` *(simplest)* — acceptable because the DB lives on a private
     subnet reachable only from the EC2 security group. **Or** keep the default `1`
     and set `PGSSLMODE=require` on the app containers (Step 5) — the app passes no
     `sslmode`, so libpq reads it from that env var.
2. **RDS → Create database** → Standard create, **PostgreSQL 16**:
   - Templates: Dev/Test (or Free tier if offered).
   - **DB instance:** db.t4g.micro (or db.t3.micro for Free Tier).
   - **Storage:** 20 GB gp3.
   - **Credentials:** master username `aadyon`, set the **RDS master password**
     (decision #1 above).
   - **Connectivity:** same VPC as the EC2 you'll create; **Public access = No**;
     new security group `aadyon-rds-sg`.
   - **Additional config → Initial database name:** `aadyon_assist`.
   - **Parameter group:** `aadyon-pg16`.
   - Enable **automated backups** (7–14 day retention) — this replaces the `backup`
     container.
3. After it's available, note the **endpoint** (e.g.
   `aadyon.xxxx.us-east-1.rds.amazonaws.com`).

Security group wiring happens in Step 3 (allow 5432 from the EC2 SG).

---

## Step 3 — EC2 instance

1. **EC2 → Launch instance:**
   - Name `aadyon-assist`.
   - AMI: **Amazon Linux 2023** (or Ubuntu 22.04).
   - Type: **t3.medium** (t3.micro for Free Tier — tighter).
   - Key pair: create/download one for SSH.
   - Network: same VPC as RDS. **Security group `aadyon-ec2-sg`:** allow **SSH (22)
     from your IP only**. Do **not** open 8000 to the world (Tailscale handles access).
   - Storage: 30 GB gp3.
2. **Wire the SGs:** edit `aadyon-rds-sg` → inbound → allow **PostgreSQL (5432)**
   with source = `aadyon-ec2-sg`. That's the only path to the DB.
3. SSH in and install Docker + compose + git + Tailscale:
   ```bash
   sudo dnf update -y
   sudo dnf install -y docker git
   sudo systemctl enable --now docker
   sudo usermod -aG docker ec2-user     # re-login after this
   DOCKER_CONFIG=/usr/local/lib/docker
   sudo mkdir -p $DOCKER_CONFIG/cli-plugins
   sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
     -o $DOCKER_CONFIG/cli-plugins/docker-compose
   sudo chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose
   # Tailscale (keeps the API private; matches golden rule #3)
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up          # authenticate to your tailnet
   ```

---

## Step 4 — code + secrets on the box

```bash
git clone https://github.com/chiranjeevigundu/aadyon-assist.git
cd aadyon-assist
cp .env.production.example .env
mkdir -p secrets

# Secrets (files; chmod tight). db_password.txt = the aadyon_app app password (decision #2).
printf '%s' 'YOUR_AADYON_APP_PASSWORD'  > secrets/db_password.txt
python3 -c "import secrets;print(secrets.token_urlsafe(48))" > secrets/jwt_secret.txt
printf '%s' 'YOUR_S3_ACCESS_KEY_ID'     > secrets/s3_access_key.txt
printf '%s' 'YOUR_S3_SECRET_ACCESS_KEY' > secrets/s3_secret_key.txt
printf ''                               > secrets/resend_api_key.txt   # empty => email log-only
chmod 600 secrets/*.txt
```

Edit `.env` for RDS + S3 (the app reads these):
```dotenv
# --- Database (RDS) ---
POSTGRES_DB=aadyon_assist
POSTGRES_USER=aadyon              # RDS master username (migrate/DDL only)
DB_USER=aadyon_app                # restricted role the API connects as (RLS applies)
DB_PORT=5432
# DB_HOST is set per-service in the AWS override (Step 5), not here.
PGSSLMODE=require                 # needed if the RDS param group keeps rds.force_ssl=1

# --- Object storage ---
STORAGE_BACKEND=s3
S3_BUCKET_NAME=aadyon-assist-uploads-417722285818
AWS_REGION=us-east-1              # boto3 has no region set in code; provide it here
AWS_DEFAULT_REGION=us-east-1

# --- LLM + app ---
OPENROUTER_API_KEY=sk-or-...      # from .env, not a Docker secret
APP_PUBLIC_URL=http://<ec2-tailscale-name>:8000
```

> `secrets/` and `.env` are gitignored and gitleaks-scanned — never commit them.

---

## Step 5 — the AWS compose override (created on the box)

The stock `docker-compose.yml` hardcodes `DB_HOST: db` on the app services and a
`depends_on: db`. Create a small override next to it so those services point at RDS.
This file lives only on the server (it's deploy config, not committed):

```yaml
# docker-compose.aws.yml — on the EC2 host only
services:
  api:
    environment:
      DB_HOST: aadyon.xxxx.us-east-1.rds.amazonaws.com   # your RDS endpoint
  briefing:
    environment:
      DB_HOST: aadyon.xxxx.us-east-1.rds.amazonaws.com
  agency:
    environment:
      DB_HOST: aadyon.xxxx.us-east-1.rds.amazonaws.com
```

`PGSSLMODE`, `AWS_REGION`, `STORAGE_BACKEND`, etc. come from `.env` (already loaded
via each service's `env_file`).

---

## Step 6 — extensions + migrations against RDS

First enable the extensions in the `aadyon_assist` DB (once), then run migrations.

```bash
export RDS=aadyon.xxxx.us-east-1.rds.amazonaws.com

# 6a. Enable required extensions (idempotent) — any psql client works
psql "postgresql://aadyon:YOUR_RDS_MASTER_PW@${RDS}:5432/aadyon_assist?sslmode=require" \
  -c 'CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pgcrypto;'
```

**6b. Migrations.** Pick one:

- **Simple (stock `migrate` service).** If your RDS **master password equals**
  `secrets/db_password.txt` (i.e. admin and app share one password), the parametrized
  `migrate` service just works now that `.env` has `DB_HOST`/`DB_SSLMODE`:
  ```bash
  just migrate     # = docker compose run --rm migrate ; applies DDL + sets aadyon_app pw
  ```
- **Separate admin/app passwords (more secure).** Run yoyo with the master credential
  and set `aadyon_app` to the app password explicitly:
  ```bash
  export MASTER_PW='YOUR_RDS_MASTER_PW'; export APP_PW="$(cat secrets/db_password.txt)"
  docker compose -f docker-compose.yml -f docker-compose.aws.yml run --rm --no-deps migrate \
    "yoyo apply -v --batch --database 'postgresql://aadyon:${MASTER_PW}@${RDS}:5432/aadyon_assist?sslmode=require' /srv/db/migrations \
     && python -c \"import psycopg2; c=psycopg2.connect(host='${RDS}',dbname='aadyon_assist',user='aadyon',password='${MASTER_PW}',sslmode='require'); c.autocommit=True; c.cursor().execute('ALTER ROLE aadyon_app WITH PASSWORD %s',('${APP_PW}',))\""
  ```

Confirm it exits 0. (On RDS the master `aadyon` is not a true superuser, which is
*fine*: the migrations use `FORCE ROW LEVEL SECURITY`, so RLS holds for `aadyon_app`
— a non-owner role — exactly as designed. See `202607032100_restricted_app_role.sql`.)

---

## Step 7 — start the app + verify

```bash
# Start only the long-running app services; --no-deps skips db/migrate dependencies
docker compose -f docker-compose.yml -f docker-compose.aws.yml up -d --build --no-deps \
  api briefing agency        # add `ntfy` if you want push on the box

docker compose ps
docker compose logs -f api   # watch for "Application startup complete"

# health (from the box)
curl -s localhost:8000/api/health          # => {"status":"ok","db":"up"}
```

From your laptop/phone **on the tailnet**, hit
`http://<ec2-tailscale-name>:8000/api/health`, then the dashboards at `/`, `/tracker`,
`/data`. Sign up a user (invite-gated by default — mint one via
`POST /api/auth/invites`, or set `INVITE_REQUIRED=false` in `.env` for a private
single-user box).

**Optional public HTTPS instead of Tailscale:** run Caddy on the box
(`caddy reverse-proxy --from your.domain --to :8000`), point an A record at an
Elastic IP, and open 80/443 (not 8000) in `aadyon-ec2-sg`. Caddy auto-provisions a
Let's Encrypt cert. Keep 8000 closed to the internet either way.

---

## Step 8 — backups, updates, teardown

- **Backups:** RDS automated backups (Step 2) + take a manual snapshot before each
  deploy. You can drop the `backup` compose service entirely. `just restore` is no
  longer the DR path — use RDS point-in-time restore / snapshot restore.
- **Redeploy** (deploy ritual, human-serialized per AGENTS.md):
  ```bash
  git pull --ff-only
  # run Step 6b again only if there are new migrations
  docker compose -f docker-compose.yml -f docker-compose.aws.yml up -d --build --no-deps api briefing agency
  ```
- **Teardown to stop all charges** (you cleaned this account once already): terminate
  the EC2 instance, delete the RDS instance (take a final snapshot or skip), delete
  the S3 bucket contents + bucket, release any Elastic IP, delete the security groups.
  Then confirm on the EC2 dashboard that Instances/Volumes/EIPs read 0 (as they do now).

---

## Security checklist (maps to the golden rules)

- [ ] RDS **not publicly accessible**; 5432 open only from `aadyon-ec2-sg` (rule 3).
- [ ] API not exposed to the internet — Tailscale, or HTTPS-only via Caddy (rule 3).
- [ ] App connects as `DB_USER=aadyon_app` (never the RDS master) so **RLS applies** (rule 3).
- [ ] S3 bucket **Block Public Access = ON**; IAM user scoped to just that bucket.
- [ ] Secrets in `secrets/*.txt` (chmod 600) + `.env`; **never committed** (rule 1, 4).
- [ ] `STORAGE_BACKEND=s3` (never `mock`/`local` on a real box) (CLOUD.md gotcha).
- [ ] Billing budget alert set.

## Stack-specific gotchas

- **Two DB passwords.** RDS master (DDL) ≠ `aadyon_app` (app). Mixing them up = the
  app can't log in, or migrations run as the wrong role.
- **SSL.** No `sslmode` in code → set `PGSSLMODE=require` (or relax `rds.force_ssl`),
  else connections are refused by a default PG16 param group.
- **`migrate` reads `DB_HOST`/`DB_PORT`/`DB_SSLMODE`** now — set them in `.env` and the
  stock service targets RDS (Step 6). Use the manual form only to keep admin/app
  passwords distinct.
- **S3 needs explicit keys** — `get_s3_client()` returns `None` on empty creds and does
  not use the instance role. Provide IAM-user keys, or make the one-line code change to
  fall back to the default chain.
- **Connection limits.** Pool is `maxconn=10` per process; api+briefing+agency ≈ 30
  connections. db.t4g.micro caps ~ a few hundred — fine for one replica; add PgBouncer
  before scaling out (CLOUD.md gotcha).
```

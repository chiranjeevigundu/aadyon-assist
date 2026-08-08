# Cloud storage: real AWS ⇄ local emulator, by config alone

Aadyon's file storage is **not bound to any one cloud**. The same code path
(`code/api/app/services/storage.py`) talks to:

- **real AWS S3**,
- a **local cloud emulator** — Floci, LocalStack, or MinIO,
- or any other **S3-compatible** store (Cloudflare R2, GCS S3-interop, …).

Which one is live is decided **entirely by configuration**. Migrating between them is
an `.env` edit and a restart — never a code change. This is the "any cloud, no lock-in"
contract; keep it that way (see [Rules for contributors](#rules-for-contributors)).

---

## The two profiles

Set `STORAGE_BACKEND=s3`, then pick one profile. These are the *only* lines that differ.

### Profile A — local emulator (Floci / LocalStack / MinIO)

```dotenv
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=http://host.docker.internal:4566   # the emulator on the host
S3_BUCKET_NAME=aadyon-assist
S3_REGION=us-east-1
# S3_FORCE_PATH_STYLE=auto        # auto -> path-style (correct for emulators)
# S3_AUTO_CREATE_BUCKET=true      # bucket is created on startup if missing
```
Credentials: put `test` in both `secrets/s3_access_key.txt` and `secrets/s3_secret_key.txt`.

### Profile B — real AWS S3

```dotenv
STORAGE_BACKEND=s3
# S3_ENDPOINT_URL is UNSET  <- this is what targets real AWS
S3_BUCKET_NAME=my-real-bucket
S3_REGION=us-east-1                # the bucket's ACTUAL region
# S3_FORCE_PATH_STYLE=auto         # auto -> virtual-host (correct for AWS)
# S3_AUTO_CREATE_BUCKET=false      # recommended: pre-provision via IaC on AWS
```
Credentials: real IAM access key / secret in `secrets/s3_*.txt` — **or** leave those
files empty and let the app use an **IAM instance/task role** (the default AWS
credential chain). Either works with no code change.

> The single switch between the two worlds is **`S3_ENDPOINT_URL`**: set it → you're on
> the emulator; unset it → you're on real AWS.

---

## What each knob does

| Env var | Default | Purpose |
|---|---|---|
| `STORAGE_BACKEND` | `local` | `local` \| `s3` \| `mock`. Must be `s3` to use any of the below. |
| `S3_ENDPOINT_URL` | *(empty)* | Emulator URL. **Empty = real AWS.** |
| `S3_BUCKET_NAME` | `aadyon-assist` | Bucket objects live in. |
| `S3_REGION` | `us-east-1` | SigV4 region + create-bucket location. Also honors `AWS_REGION` / `AWS_DEFAULT_REGION`. On AWS, must match the bucket. |
| `S3_FORCE_PATH_STYLE` | `auto` | `auto` = path-style when an endpoint is set (emulators), virtual-host otherwise (AWS). Force with `true`/`false`. |
| `S3_AUTO_CREATE_BUCKET` | `true` | Create the bucket on startup if missing (idempotent). Set `false` on AWS to keep `CreateBucket` out of the app's role. |

Credentials come from `secrets/s3_access_key.txt` / `secrets/s3_secret_key.txt` (or the
`S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` env fallbacks). If none are set **and** no
endpoint is configured, storage falls back to local disk rather than guessing.

---

## Migrating an existing deployment

1. Edit `.env` — swap Profile A ⇄ Profile B (and update `secrets/s3_*.txt`).
2. Recreate the services so they pick up the new env:
   ```bash
   docker compose up -d --force-recreate api briefing agency
   ```
3. Ensure the target bucket exists (startup does this automatically; to do it on demand):
   ```bash
   just storage-init
   ```
4. Verify a round-trip:
   ```bash
   docker compose exec api python -c "import io; from app.services import storage; storage.upload_fileobj(io.BytesIO(b'ok'),'healthcheck/ping.txt','text/plain'); b=io.BytesIO(); storage.download_fileobj('healthcheck/ping.txt', b); print(b.getvalue())"
   ```

**Note:** switching the *backend* re-points where *new* uploads go; it does not copy
existing objects. To carry data across, mirror the old bucket into the new one
(`aws s3 sync`, `rclone`, or the emulator's CLI) before cutting over.

---

## Rules for contributors

To keep aadyon cloud-agnostic, storage code must stay vendor-neutral:

- **No hardcoded endpoints, regions, buckets, or credentials.** Everything reads from
  `core/config.py`. A literal `s3.amazonaws.com` or `4566` in application code is a bug.
- **Talk to storage only through `app.services.storage`.** Don't call `boto3` directly
  from routers/services — that's how vendor assumptions leak in.
- **No AWS-only S3 features** (e.g. S3-specific ACL semantics, SSE-KMS) without an
  emulator-friendly fallback — they break the local dev loop.
- New knobs get a row in the table above and a line in `.env.example`.

See also [CLOUD.md](CLOUD.md) for the full move to a managed platform (Postgres, secrets,
scaling), of which object storage is one part.

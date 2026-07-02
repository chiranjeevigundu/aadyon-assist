# Aadyon Assist task runner — https://github.com/casey/just
# Install: `winget install Casey.Just` (Windows) · `brew install just` (macOS) · apt/dnf (Linux)
# List recipes: `just --list`

set shell := ["bash", "-cu"]

# Start the full stack (build if needed)
up:
    docker compose up -d --build

# Stop the stack (data volumes are kept)
down:
    docker compose down

# Tail logs for one service, e.g. `just logs api`
logs service:
    docker compose logs -f {{service}}

# Rebuild images without starting
build:
    docker compose build

# Apply pending DB migrations (yoyo ledger decides what runs)
migrate:
    docker compose run --rm migrate

# Create a new timestamped SQL migration, e.g. `just new-migration add_widget_table`
new-migration name:
    docker compose run --rm --no-deps migrate \
      'yoyo new --config /srv/db/yoyo.ini --sql -m "{{name}}"'

# One-time baseline for an EXISTING database: record all current migrations as
# applied WITHOUT executing them. Run a backup first (`just backup-now`).
migrate-baseline:
    docker compose run --rm migrate \
      'yoyo mark --batch --database "postgresql://${POSTGRES_USER}:$(cat /run/secrets/db_password)@db:5432/${POSTGRES_DB}" /srv/db/migrations'

# Apply your local (gitignored) personal seed SQL, e.g. code/db/seed/99_seed_local.sql
seed:
    for f in code/db/seed/*.sql; do \
      [ -e "$f" ] || { echo "no seed files in code/db/seed/"; exit 0; }; \
      echo "applying $f"; \
      docker compose exec -T db psql -U "${POSTGRES_USER:-aadyon}" -d "${POSTGRES_DB:-aadyon_assist}" < "$f"; \
    done

# Import entities from artifacts/inbox.json (whitelisted columns, deduped)
import:
    docker compose exec api python -m app.jobs.import_entities

# Run the unit test suite (DB-free)
test:
    pytest

# Lint: ruff (rules in pyproject.toml) + dashboard inline-JS syntax check
lint:
    ruff check .
    node -e ' \
      const fs=require("fs"), vm=require("vm"); \
      for (const f of fs.readdirSync("code/dashboard")) { \
        if (!f.endsWith(".html")) continue; \
        const h=fs.readFileSync("code/dashboard/"+f,"utf8"); \
        for (const m of h.matchAll(/<script>([\s\S]*?)<\/script>/g)) new vm.Script(m[1]); \
        console.log("ok:", f); \
      } \
      const a="code/dashboard/assets"; \
      for (const f of fs.readdirSync(a)) if (f.endsWith(".js")) { new vm.Script(fs.readFileSync(a+"/"+f,"utf8")); console.log("ok:", f); }'

# Live-API parity check against a running stack (ops tool; CI uses Schemathesis)
verify base="http://localhost:8000" token="":
    python scripts/verify.py --base {{base}} {{ if token != "" { "--token " + token } else { "" } }}

# Trigger an immediate DB backup (the backup service also runs daily)
backup-now:
    docker compose exec backup /backup.sh

# Restore a dump into the running DB, e.g. `just restore data/exports/daily/x.sql.gz`
restore file:
    gunzip -c {{file}} | docker compose exec -T db psql -U "${POSTGRES_USER:-aadyon}" -d "${POSTGRES_DB:-aadyon_assist}"

# Start the Expo dev server for the iPhone app
mobile:
    cd mobile && npx expo start

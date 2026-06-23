#!/usr/bin/env bash
# Create a collision-proof, timestamp-named DB migration.
#
# Parallel agents must NOT use sequential numbers (NN_name.sql) — two agents
# will both grab the same number and collide on merge. Timestamped names sort
# correctly (after 09_*, before 99_seed_local) and never clash.
#
# Usage: scripts/new-migration.sh add_widget_table
set -euo pipefail

name="${1:?usage: scripts/new-migration.sh <snake_case_name>}"
ts="$(date +%Y%m%d%H%M)"
f="code/db/init/${ts}_${name}.sql"

if [ -e "$f" ]; then
  echo "refusing to overwrite existing $f" >&2
  exit 1
fi

cat > "$f" <<SQL
-- ${ts}_${name}
-- Migrations auto-run only on first boot of an empty DB volume. On an existing
-- database (e.g. the Mini-A) apply manually:
--   docker compose exec -T db psql -U aadyon -d aadyon_assist < ${f}

SQL

echo "created $f"

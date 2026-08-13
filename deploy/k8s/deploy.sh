#!/usr/bin/env bash
# Thin shim: load this product's settings, then run the shared deployer.
#
# The deployer lives in the floci-lab repository, checked out as a sibling of this
# one. It is not vendored or submoduled: the Dockerfile build context here is `code/`,
# so a repo-root submodule would not even be visible to the build, and submodules
# break `pip install -r` besides.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export REPO_ROOT="$(cd "$HERE/../.." && pwd)"
export MANIFEST_DIR="$HERE"

# shellcheck source=/dev/null
set -a; . "$HERE/deploy.env"; set +a

FLOCI_LAB="${FLOCI_LAB:-$REPO_ROOT/../floci-lab}"
DEPLOYER="$FLOCI_LAB/bin/deploy-k8s.sh"
[ -x "$DEPLOYER" ] || [ -f "$DEPLOYER" ] || {
  echo "error: shared deployer not found at $DEPLOYER" >&2
  echo "       clone it beside this repo:" >&2
  echo "         git clone https://github.com/chiranjeevigundu/floci-lab $(cd "$REPO_ROOT/.." && pwd)/floci-lab" >&2
  echo "       or set FLOCI_LAB to where it lives." >&2
  exit 1
}
exec bash "$DEPLOYER" "$@"

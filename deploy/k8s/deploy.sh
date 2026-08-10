#!/usr/bin/env bash
# Deploy aadyon-assist into a local Kubernetes cluster provisioned by Floci.
#
#   ./deploy/k8s/deploy.sh              # create cluster if needed, build, deploy
#   CLUSTER=mydev ./deploy/k8s/deploy.sh
#
# Idempotent: safe to re-run. Re-running rebuilds the image and rolls the pods.
# See README.md in this directory for prerequisites and troubleshooting.
set -euo pipefail

CLUSTER="${CLUSTER:-aadyon}"
NAMESPACE="${NAMESPACE:-aadyon}"
FLOCI_ENDPOINT="${FLOCI_ENDPOINT:-http://localhost:4566}"
REGISTRY_HOST="${REGISTRY_HOST:-localhost:5100}"
# The registry name k3s resolves through Floci's injected mirror (see registries.yaml
# inside the k3s container). Pushing to REGISTRY_HOST lands in the same store.
IMAGE_REPO="${IMAGE_REPO:-000000000000.dkr.ecr.us-east-1.localhost:5100/aadyon-assist-api}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
IMAGE="$IMAGE_REPO:$IMAGE_TAG"
WEB_PORT="${WEB_PORT:-8000}"
NODE_PORT=30080
PROXY_NAME="aadyon-web"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"

step() { printf '\n\033[36m==>\033[0m %s\n' "$1"; }
die()  { printf '\033[31merror:\033[0m %s\n' "$1" >&2; exit 1; }

# Docker on Windows/Git-Bash mangles container paths; disable that for exec/cp.
export MSYS_NO_PATHCONV=1

# kubectl is a native binary on Windows even under Git-Bash, so KUBECONFIG needs
# Windows-style paths joined by ';' rather than POSIX paths joined by ':'.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) KPATH_SEP=';'; to_native() { cygpath -w "$1"; } ;;
  *)                    KPATH_SEP=':'; to_native() { printf '%s' "$1"; } ;;
esac

# --------------------------------------------------------------- prerequisites
step "Checking prerequisites"
for bin in docker kubectl aws; do
  command -v "$bin" >/dev/null 2>&1 || die "$bin is required but not on PATH"
done
docker info >/dev/null 2>&1 || die "Docker is not running"
curl -sf "$FLOCI_ENDPOINT" >/dev/null 2>&1 \
  || die "Floci is not reachable at $FLOCI_ENDPOINT — start it first (see README)"
echo "ok: docker, kubectl, aws, floci"

export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"

# ------------------------------------------------------------------- cluster
step "Ensuring EKS cluster '$CLUSTER' exists"
if aws --endpoint-url "$FLOCI_ENDPOINT" eks describe-cluster --name "$CLUSTER" >/dev/null 2>&1; then
  echo "cluster already exists"
else
  aws --endpoint-url "$FLOCI_ENDPOINT" eks create-cluster \
    --name "$CLUSTER" \
    --role-arn arn:aws:iam::000000000000:role/eks \
    --resources-vpc-config subnetIds=subnet-default-c >/dev/null
  echo "created — waiting for ACTIVE..."
fi
for _ in $(seq 1 40); do
  status="$(aws --endpoint-url "$FLOCI_ENDPOINT" eks describe-cluster --name "$CLUSTER" \
            --query 'cluster.status' --output text 2>/dev/null || echo PENDING)"
  [ "$status" = "ACTIVE" ] && break
  sleep 3
done
[ "${status:-}" = "ACTIVE" ] || die "cluster did not become ACTIVE (last status: ${status:-unknown})"
echo "cluster ACTIVE"

K3S_CONTAINER="floci-eks-$CLUSTER"
docker inspect "$K3S_CONTAINER" >/dev/null 2>&1 \
  || die "expected k3s container '$K3S_CONTAINER' not found"

# ---------------------------------------------------------------- kubeconfig
step "Writing kubeconfig (context: floci-$CLUSTER)"
# The API port Floci published for this cluster; not fixed across clusters.
API_PORT="$(docker port "$K3S_CONTAINER" 6443/tcp | head -1 | sed 's/.*://')"
[ -n "$API_PORT" ] || die "could not determine the k3s API port"
KUBE_DIR="${HOME}/.kube"; mkdir -p "$KUBE_DIR"
TMP_KCFG="$(mktemp)"
docker exec "$K3S_CONTAINER" cat /etc/rancher/k3s/k3s.yaml \
  | tr -d '\r' \
  | sed "s#https://127.0.0.1:6443#https://127.0.0.1:${API_PORT}#" \
  | sed "s/\bdefault\b/floci-$CLUSTER/g" > "$TMP_KCFG"
if [ -f "$KUBE_DIR/config" ]; then
  cp "$KUBE_DIR/config" "$KUBE_DIR/config.bak.$(date +%Y%m%d%H%M%S)"
  KUBECONFIG="$(to_native "$KUBE_DIR/config")$KPATH_SEP$(to_native "$TMP_KCFG")" \
    kubectl config view --flatten > "$KUBE_DIR/config.new"
  mv "$KUBE_DIR/config.new" "$KUBE_DIR/config"
else
  cp "$TMP_KCFG" "$KUBE_DIR/config"
fi
rm -f "$TMP_KCFG"
kubectl config use-context "floci-$CLUSTER" >/dev/null
kubectl config set-context "floci-$CLUSTER" --namespace="$NAMESPACE" >/dev/null
kubectl get nodes >/dev/null || die "cannot reach the cluster with the generated kubeconfig"
echo "kubeconfig merged into $KUBE_DIR/config (previous config backed up)"

# ------------------------------------------------------------- build + push
step "Building and pushing the application image"
# host paths must be native for docker (MSYS_NO_PATHCONV above protects container paths)
docker build -q -t aadyon-assist-api:latest \
  -f "$(to_native "$REPO_ROOT/code/api/Dockerfile")" \
  "$(to_native "$REPO_ROOT/code")" >/dev/null
docker tag aadyon-assist-api:latest "$REGISTRY_HOST/aadyon-assist-api:$IMAGE_TAG"
aws --endpoint-url "$FLOCI_ENDPOINT" ecr create-repository \
  --repository-name aadyon-assist-api >/dev/null 2>&1 || true
docker push -q "$REGISTRY_HOST/aadyon-assist-api:$IMAGE_TAG" >/dev/null
echo "pushed $REGISTRY_HOST/aadyon-assist-api:$IMAGE_TAG"

# ------------------------------------------------ namespace, secrets, config
step "Applying namespace, secrets and configuration"
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

# Secrets are generated once and then left alone — re-running must not rotate the
# DB password out from under an existing volume, or invalidate everyone's sessions.
if kubectl -n "$NAMESPACE" get secret aadyon-secrets >/dev/null 2>&1; then
  echo "secrets already present — leaving them untouched"
else
  gen() { python -c "import secrets;print(secrets.token_urlsafe($1))"; }
  kubectl -n "$NAMESPACE" create secret generic aadyon-secrets \
    --from-literal=db_password="$(gen 18)" \
    --from-literal=jwt_secret="$(gen 48)" \
    --from-literal=s3_access_key="${S3_ACCESS_KEY:-test}" \
    --from-literal=s3_secret_key="${S3_SECRET_KEY:-test}" >/dev/null
  echo "generated aadyon-secrets"
fi

# Pods cannot resolve Docker container names (k3s runs its own DNS), so the S3
# emulator is addressed by its IP on the shared Docker network. Discover it rather
# than hardcoding: it changes per machine and per `docker compose up`.
FLOCI_CONTAINER="$(docker ps --filter ancestor=floci/floci --format '{{.Names}}' | head -1)"
[ -n "$FLOCI_CONTAINER" ] \
  || FLOCI_CONTAINER="$(docker ps --format '{{.Names}}\t{{.Image}}' | grep -i 'floci/floci' | head -1 | cut -f1)"
[ -n "$FLOCI_CONTAINER" ] || die "could not find the running Floci container"
FLOCI_IP="$(docker inspect "$FLOCI_CONTAINER" \
  --format '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' | awk '{print $1}')"
[ -n "$FLOCI_IP" ] || die "could not determine the Floci container IP"
S3_URL="${S3_ENDPOINT_URL:-http://$FLOCI_IP:4566}"
kubectl -n "$NAMESPACE" create configmap aadyon-env \
  --from-literal=S3_ENDPOINT_URL="$S3_URL" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null
echo "S3 endpoint for pods: $S3_URL  (from container $FLOCI_CONTAINER)"

# -------------------------------------------------------------- manifests
step "Applying workloads"
# The migrate Job's spec is immutable; replace it so re-runs pick up changes.
kubectl -n "$NAMESPACE" delete job migrate --ignore-not-found >/dev/null
sed "s#__IMAGE__#$IMAGE#g" "$HERE/aadyon.yaml" | kubectl apply -f - >/dev/null
# Same tag every time, so force pods onto the freshly pushed layers.
kubectl -n "$NAMESPACE" patch deploy api \
  -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"deployedAt\":\"$(date +%s)\"}}}}}" >/dev/null
kubectl -n "$NAMESPACE" patch deploy briefing \
  -p "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"deployedAt\":\"$(date +%s)\"}}}}}" >/dev/null
kubectl -n "$NAMESPACE" rollout status deploy/api --timeout=180s
kubectl -n "$NAMESPACE" rollout status deploy/briefing --timeout=120s

# ------------------------------------------------------------------- ingress
step "Exposing the app on http://localhost:$WEB_PORT"
# Floci publishes only the cluster's API port, so the NodePort is not reachable from
# the host. A tiny socat container bridges the two; it restarts with Docker, unlike
# `kubectl port-forward`, which dies with its shell.
docker rm -f "$PROXY_NAME" >/dev/null 2>&1 || true
NETWORK="$(docker inspect "$K3S_CONTAINER" \
  --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' | awk '{print $NF}')"
docker run -d --name "$PROXY_NAME" \
  --network "$NETWORK" \
  --restart unless-stopped \
  -p "$WEB_PORT:$WEB_PORT" \
  alpine/socat "tcp-listen:$WEB_PORT,fork,reuseaddr" \
  "tcp-connect:$K3S_CONTAINER:$NODE_PORT" >/dev/null
sleep 3

# -------------------------------------------------------------------- verify
step "Verifying"
for _ in $(seq 1 20); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://localhost:$WEB_PORT/api/health" || true)"
  [ "$code" = "200" ] && break
  sleep 3
done
[ "${code:-}" = "200" ] || die "app did not become reachable on http://localhost:$WEB_PORT (last status: ${code:-none})"

kubectl -n "$NAMESPACE" get pods
printf '\n\033[32mReady:\033[0m http://localhost:%s  — sign up to create your account.\n' "$WEB_PORT"
printf 'kubectl is set to context floci-%s (namespace %s).\n' "$CLUSTER" "$NAMESPACE"

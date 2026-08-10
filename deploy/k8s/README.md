# Running Aadyon Assist on Kubernetes

An alternative to the Docker Compose deployment: the same app image, running as real
Kubernetes workloads. Developed against a **local k3s cluster provisioned through
[Floci](https://github.com/floci-io/floci-ui)'s EKS emulation**, which makes it a
realistic dry-run of deploying to EKS without an AWS bill.

Compose is still the simplest way to run this app — see the
[root README](../../README.md). Use this if you want to exercise the Kubernetes path.

---

## What gets deployed

| Workload | Kind | Role |
|---|---|---|
| `api` | Deployment | REST API + serves the dashboards |
| `briefing` | Deployment | Daily digest worker |
| `postgres` | StatefulSet + PVC (2Gi) | pgvector database, in-cluster |
| `migrate` | Job | Applies the schema, then exits |

Object storage is **not** in the cluster: pods talk to whatever `S3_ENDPOINT_URL` the
`aadyon-env` ConfigMap carries — a local S3 emulator by default, or leave it empty to
use real AWS S3 (see [cloud-storage.md](../../docs/cloud-storage.md)).

## Prerequisites

- **Docker** running
- **kubectl**
- **aws** CLI (used to drive Floci's EKS API — no real AWS account needed)
- **Floci** running with the S3/EKS emulator on `:4566`

Floci must be able to start sibling containers (that is how it creates the k3s
cluster). Its container needs the Docker socket mounted:

```yaml
# docker-compose.override.yml in your floci checkout
services:
  floci:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

Without it, cluster creation fails with
`Floci could not reach the container runtime (java.net.SocketException: No such file or directory)`.

## Deploy

```bash
./deploy/k8s/deploy.sh
```

That is the whole thing. The script is idempotent — re-run it to ship a code change.
It will:

1. create the EKS cluster (or reuse it) and wait for `ACTIVE`
2. merge a kubeconfig into `~/.kube/config` as context `floci-aadyon` (backing up any existing config)
3. build the app image and push it to Floci's ECR registry mirror
4. generate `aadyon-secrets` **once** — re-runs never rotate them, so an existing database keeps working
5. discover the S3 emulator's IP and write it into the `aadyon-env` ConfigMap
6. apply the manifests and wait for the rollout
7. start a `socat` proxy so the app is reachable on `http://localhost:8000`

Then open **http://localhost:8000** and sign up.

### Options

| Variable | Default | Purpose |
|---|---|---|
| `CLUSTER` | `aadyon` | EKS cluster name |
| `NAMESPACE` | `aadyon` | Kubernetes namespace |
| `WEB_PORT` | `8000` | Host port the app is published on |
| `S3_ENDPOINT_URL` | auto-discovered | Override the storage endpoint (leave empty for real AWS) |
| `FLOCI_ENDPOINT` | `http://localhost:4566` | Where Floci's API lives |

## Why the socat proxy

Floci publishes only the cluster's Kubernetes **API** port. A `NodePort` is reachable
on the node — which here *is* the k3s container — but nothing maps it to the host.
Rather than recreate Floci's container with extra port mappings (fighting the tool that
manages it), a one-line `socat` container bridges `localhost:8000` to NodePort `30080`.
It carries `--restart unless-stopped`, so it survives reboots; `kubectl port-forward`
would not.

## Two things worth knowing

**Secrets are not in git.** The script generates them into a Kubernetes Secret on first
deploy. To supply your own, create the secret before running:

```bash
kubectl -n aadyon create secret generic aadyon-secrets \
  --from-literal=db_password='...' \
  --from-literal=jwt_secret='...' \
  --from-literal=s3_access_key='...' \
  --from-literal=s3_secret_key='...'
```

**Secrets mount at `/etc/aadyon/secrets`, not `/run/secrets`.** Mounting them at
`/run/secrets` (the Docker convention this app also supports) makes that path read-only
and blocks kubelet's own serviceaccount mount, so *every pod fails to start* with
`RunContainerError`. The manifests point the app's `*_FILE` settings at
`/etc/aadyon/secrets` instead.

## Operating it

```bash
kubectl get pods                      # context/namespace are already set
kubectl logs -f deploy/api
kubectl exec -it postgres-0 -- psql -U aadyon -d aadyon_assist

./deploy/k8s/deploy.sh                # ship a code change
```

### Teardown

```bash
docker rm -f aadyon-web                                                   # the proxy
aws --endpoint-url http://localhost:4566 eks delete-cluster --name aadyon # cluster + data
```

Deleting the cluster destroys the Postgres volume with it. Back up first if the data
matters: `kubectl exec postgres-0 -- pg_dump -U aadyon aadyon_assist > backup.sql`.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `could not find the running Floci container` | Floci is not running, or its image is not `floci/floci` |
| Cluster never reaches `ACTIVE` | Docker socket is not mounted into Floci (see Prerequisites) |
| Pods `ImagePullBackOff` | The registry mirror is unreachable; check `docker ps` for `floci-ecr-registry` |
| Pods `RunContainerError` | Usually a volume mounted over a path kubelet needs — see the `/run/secrets` note above |
| `http://localhost:8000` refused | The `aadyon-web` proxy is not running, or another process holds the port |

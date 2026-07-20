# AWS free-tier provisioning

One-shot scripts to stand up (and tear down) a personal Aadyon Assist deployment on
AWS: **EC2 t3.micro + RDS Postgres 16 db.t3.micro + S3**, us-east-1, default VPC.
They wrap the runbook in [`../../docs/AWS_EC2_DEPLOY.md`](../../docs/AWS_EC2_DEPLOY.md);
read [`../../docs/HOSTING.md`](../../docs/HOSTING.md) for the provider-agnostic picture.

Run them **in AWS CloudShell** (already authenticated as you — the icon is in the
console's bottom bar) or any terminal with `aws` configured for your account. These
scripts contain **no secrets** — the DB password is generated at runtime and printed
once; save it.

## Provision

```bash
# 1) get YOUR public IP (run on your own machine, not CloudShell) and set it in CloudShell:
export MY_IP_CIDR="1.2.3.4/32"          # your.ip/32 — locks SSH to you
# 2) run it
bash provision-free-tier.sh
```

It prints the EC2 IP, RDS endpoint, DB password, and S3 keys, then the exact
follow-up commands to run on the box (clone, `.env`, secrets, extensions, `just
migrate`, `docker compose up`). Download the generated `aadyon-key.pem`
(CloudShell: **Actions ▸ Download file**) to SSH in.

**Cost:** ~$0 on a new account's Free Tier (750 h/mo t3.micro EC2 + db.t3.micro RDS,
30 GB EBS, 20 GB RDS, 5 GB S3). Outside Free Tier ≈ $45/mo. Set a Billing budget alert.

**Security defaults:** RDS is private (5432 only from the EC2 security group); SSH is
open only to `MY_IP_CIDR`; the API port is **not** exposed — reach it via SSH tunnel
(`ssh -L 8000:localhost:8000 …`) or install Tailscale on the box.

## Tear down (back to $0)

```bash
bash teardown.sh
```

Terminates the EC2 instance, deletes the RDS instance (no final snapshot), empties +
deletes the S3 bucket, removes the IAM user, security groups, and key pair. Re-runnable.
Confirm 0 across Instances/Volumes/RDS/S3 in the console afterward.

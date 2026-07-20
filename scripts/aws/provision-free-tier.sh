#!/usr/bin/env bash
# Provision a FREE-TIER Aadyon Assist stack on AWS, us-east-1, in the DEFAULT VPC:
#   EC2 t3.micro (Docker pre-installed) + RDS Postgres 16 db.t3.micro (private) + S3.
#
# Run in AWS CloudShell (already authenticated) or any shell with `aws` configured
# for your account. Costs ~$0 on a new account's Free Tier (750h/mo t3.micro EC2 +
# db.t3.micro RDS, 30GB EBS, 20GB RDS, 5GB S3); ~$45/mo outside it. Tear it all down
# with teardown.sh. Nothing here is committed with secrets — the DB password is
# generated at runtime and printed once.
#
# Usage:
#   export MY_IP_CIDR="$(curl -s https://checkip.amazonaws.com)/32"   # on YOUR machine
#   bash provision-free-tier.sh
set -euo pipefail

### ---- CONFIG ---------------------------------------------------------------
export AWS_DEFAULT_REGION=us-east-1
PROJECT=aadyon
INSTANCE_TYPE=t3.micro          # free tier
DB_CLASS=db.t3.micro            # free tier
# SSH source. Must be YOUR public IP (CloudShell's IP is not where you SSH from).
if [ -z "${MY_IP_CIDR:-}" ]; then
  echo "ERROR: set MY_IP_CIDR to your SSH source first. On YOUR machine run:"
  echo '  export MY_IP_CIDR="$(curl -s https://checkip.amazonaws.com)/32"'
  echo "then re-run this script (export it here in CloudShell)."
  exit 1
fi
DB_PASSWORD="${DB_PASSWORD:-$(openssl rand -base64 18 | tr -d '/+=')}"   # RDS master + app role
KEY_NAME=${PROJECT}-key
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
BUCKET=${PROJECT}-uploads-${ACCOUNT}
### --------------------------------------------------------------------------

echo "Account=$ACCOUNT  Region=$AWS_DEFAULT_REGION  SSH-from=$MY_IP_CIDR  Bucket=$BUCKET"

# --- Default VPC + two subnets (RDS subnet group needs >=2 AZs) --------------
VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
mapfile -t SUBNETS < <(aws ec2 describe-subnets --filters Name=vpc-id,Values=$VPC_ID \
  --query 'Subnets[].SubnetId' --output text | tr '\t' '\n')
echo "VPC=$VPC_ID  subnets=${SUBNETS[*]}"

# --- Security groups --------------------------------------------------------
EC2_SG=$(aws ec2 create-security-group --group-name ${PROJECT}-ec2-sg \
  --description "aadyon ec2" --vpc-id $VPC_ID --query GroupId --output text 2>/dev/null \
  || aws ec2 describe-security-groups --filters Name=group-name,Values=${PROJECT}-ec2-sg \
       --query 'SecurityGroups[0].GroupId' --output text)
RDS_SG=$(aws ec2 create-security-group --group-name ${PROJECT}-rds-sg \
  --description "aadyon rds" --vpc-id $VPC_ID --query GroupId --output text 2>/dev/null \
  || aws ec2 describe-security-groups --filters Name=group-name,Values=${PROJECT}-rds-sg \
       --query 'SecurityGroups[0].GroupId' --output text)
# SSH to EC2 from your IP only; Postgres to RDS only from the EC2 SG (never public).
aws ec2 authorize-security-group-ingress --group-id $EC2_SG --protocol tcp --port 22 \
  --cidr $MY_IP_CIDR 2>/dev/null || true
aws ec2 authorize-security-group-ingress --group-id $RDS_SG --protocol tcp --port 5432 \
  --source-group $EC2_SG 2>/dev/null || true

# --- Key pair (saved locally; download from CloudShell: Actions > Download file) ---
if ! aws ec2 describe-key-pairs --key-names $KEY_NAME >/dev/null 2>&1; then
  aws ec2 create-key-pair --key-name $KEY_NAME --query KeyMaterial --output text > ${KEY_NAME}.pem
  chmod 600 ${KEY_NAME}.pem
  echo ">> Saved ${KEY_NAME}.pem — DOWNLOAD IT NOW (CloudShell: Actions > Download file)."
fi

# --- S3 bucket (private) + scoped IAM user ----------------------------------
aws s3api create-bucket --bucket $BUCKET 2>/dev/null || true     # us-east-1: no LocationConstraint
aws s3api put-public-access-block --bucket $BUCKET \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws iam create-user --user-name ${PROJECT}-s3 2>/dev/null || true
aws iam put-user-policy --user-name ${PROJECT}-s3 --policy-name ${PROJECT}-s3 --policy-document \
  "{\"Version\":\"2012-10-17\",\"Statement\":[
     {\"Effect\":\"Allow\",\"Action\":[\"s3:GetObject\",\"s3:PutObject\",\"s3:DeleteObject\"],\"Resource\":\"arn:aws:s3:::$BUCKET/*\"},
     {\"Effect\":\"Allow\",\"Action\":\"s3:ListBucket\",\"Resource\":\"arn:aws:s3:::$BUCKET\"}]}"
read -r S3_AK S3_SK < <(aws iam create-access-key --user-name ${PROJECT}-s3 \
  --query 'AccessKey.[AccessKeyId,SecretAccessKey]' --output text)

# --- RDS Postgres 16 (private, single-AZ, encrypted) ------------------------
aws rds create-db-subnet-group --db-subnet-group-name ${PROJECT}-subnets \
  --db-subnet-group-description aadyon --subnet-ids "${SUBNETS[@]}" 2>/dev/null || true
aws rds create-db-instance \
  --db-instance-identifier ${PROJECT}-pg \
  --engine postgres --engine-version 16 \
  --db-instance-class $DB_CLASS \
  --allocated-storage 20 --storage-type gp2 --storage-encrypted \
  --master-username aadyon --master-user-password "$DB_PASSWORD" \
  --db-name aadyon_assist \
  --vpc-security-group-ids $RDS_SG \
  --db-subnet-group-name ${PROJECT}-subnets \
  --no-publicly-accessible --backup-retention-period 7 --no-multi-az \
  2>/dev/null || echo "(RDS ${PROJECT}-pg already exists — skipping create)"

# --- EC2 t3.micro (Amazon Linux 2023) with docker/git/compose bootstrapped --
AMI=$(aws ssm get-parameters \
  --names /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
  --query 'Parameters[0].Value' --output text)
cat > /tmp/aadyon-userdata.sh <<'UD'
#!/bin/bash
dnf update -y
dnf install -y docker git
systemctl enable --now docker
usermod -aG docker ec2-user
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
UD
EC2_ID=$(aws ec2 run-instances --image-id $AMI --instance-type $INSTANCE_TYPE \
  --key-name $KEY_NAME --security-group-ids $EC2_SG --subnet-id "${SUBNETS[0]}" \
  --associate-public-ip-address \
  --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=30,VolumeType=gp3}' \
  --user-data file:///tmp/aadyon-userdata.sh \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=aadyon-assist}]' \
  --query 'Instances[0].InstanceId' --output text)
echo "Launching EC2 $EC2_ID ..."; aws ec2 wait instance-running --instance-ids $EC2_ID
EC2_IP=$(aws ec2 describe-instances --instance-ids $EC2_ID \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

echo "Waiting for RDS to become available (5-10 min) ..."
aws rds wait db-instance-available --db-instance-identifier ${PROJECT}-pg
RDS_ENDPOINT=$(aws rds describe-db-instances --db-instance-identifier ${PROJECT}-pg \
  --query 'DBInstances[0].Endpoint.Address' --output text)

cat <<OUT

============================================================
 PROVISIONED (free-tier). SAVE THIS — the S3 secret shows once.
------------------------------------------------------------
 EC2          : $EC2_ID   public IP: $EC2_IP
 SSH          : ssh -i ${KEY_NAME}.pem ec2-user@$EC2_IP
 RDS endpoint : $RDS_ENDPOINT
 DB password  : $DB_PASSWORD    (RDS master + aadyon_app app role)
 S3 bucket    : $BUCKET
 S3 access key: $S3_AK
 S3 secret key: $S3_SK
============================================================

 NEXT — on the EC2 box (give user-data ~2 min to finish installing docker):

   ssh -i ${KEY_NAME}.pem ec2-user@$EC2_IP
   git clone https://github.com/chiranjeevigundu/aadyon-assist.git && cd aadyon-assist
   cp .env.production.example .env
   #  edit .env:  DB_HOST=$RDS_ENDPOINT   DB_SSLMODE=require
   #     POSTGRES_USER=aadyon  DB_USER=aadyon_app  POSTGRES_DB=aadyon_assist
   #     STORAGE_BACKEND=s3  S3_BUCKET_NAME=$BUCKET  AWS_REGION=us-east-1
   #     OPENROUTER_API_KEY=sk-or-...   INVITE_REQUIRED=false
   mkdir -p secrets
   printf '%s' '$DB_PASSWORD' > secrets/db_password.txt
   python3 -c "import secrets;print(secrets.token_urlsafe(48))" > secrets/jwt_secret.txt
   printf '%s' '$S3_AK' > secrets/s3_access_key.txt
   printf '%s' '$S3_SK' > secrets/s3_secret_key.txt
   printf '' > secrets/resend_api_key.txt && chmod 600 secrets/*.txt
   # extensions once, then migrate + run:
   docker run --rm postgres:16 psql \\
     "postgresql://aadyon:$DB_PASSWORD@$RDS_ENDPOINT:5432/aadyon_assist?sslmode=require" \\
     -c 'CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pgcrypto;'
   just migrate
   docker compose up -d --build --no-deps api briefing agency
   curl -s localhost:8000/api/health          # => {"status":"ok","db":"up"}

 The API is NOT exposed publicly (only SSH from your IP is open). To reach it,
 SSH-tunnel:  ssh -i ${KEY_NAME}.pem -L 8000:localhost:8000 ec2-user@$EC2_IP
 or install Tailscale on the box (recommended). Tear down: bash teardown.sh
OUT

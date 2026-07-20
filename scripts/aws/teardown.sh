#!/usr/bin/env bash
# Tear down everything provision-free-tier.sh created, in dependency order, so the
# account returns to $0. Safe to re-run (each step tolerates "already gone").
# Run in AWS CloudShell / a shell with `aws` configured.
set -uo pipefail
export AWS_DEFAULT_REGION=us-east-1
PROJECT=aadyon
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
BUCKET=${PROJECT}-uploads-${ACCOUNT}

echo "Tearing down project '$PROJECT' in $AWS_DEFAULT_REGION (account $ACCOUNT)…"

# EC2 instances tagged aadyon-assist
IDS=$(aws ec2 describe-instances \
  --filters Name=tag:Name,Values=aadyon-assist Name=instance-state-name,Values=pending,running,stopping,stopped \
  --query 'Reservations[].Instances[].InstanceId' --output text)
if [ -n "$IDS" ]; then
  echo "Terminating EC2: $IDS"; aws ec2 terminate-instances --instance-ids $IDS >/dev/null
  aws ec2 wait instance-terminated --instance-ids $IDS
fi

# RDS (skip final snapshot for a throwaway; drop --skip-final-snapshot to keep one)
if aws rds describe-db-instances --db-instance-identifier ${PROJECT}-pg >/dev/null 2>&1; then
  echo "Deleting RDS ${PROJECT}-pg…"
  aws rds delete-db-instance --db-instance-identifier ${PROJECT}-pg \
    --skip-final-snapshot --delete-automated-backups >/dev/null
  aws rds wait db-instance-deleted --db-instance-identifier ${PROJECT}-pg
fi
aws rds delete-db-subnet-group --db-subnet-group-name ${PROJECT}-subnets 2>/dev/null || true

# S3 bucket (empty first)
if aws s3api head-bucket --bucket $BUCKET 2>/dev/null; then
  echo "Emptying + deleting bucket $BUCKET…"
  aws s3 rm s3://$BUCKET --recursive >/dev/null 2>&1 || true
  aws s3api delete-bucket --bucket $BUCKET || true
fi

# IAM user (delete keys + inline policy first)
if aws iam get-user --user-name ${PROJECT}-s3 >/dev/null 2>&1; then
  for k in $(aws iam list-access-keys --user-name ${PROJECT}-s3 --query 'AccessKeyMetadata[].AccessKeyId' --output text); do
    aws iam delete-access-key --user-name ${PROJECT}-s3 --access-key-id $k
  done
  aws iam delete-user-policy --user-name ${PROJECT}-s3 --policy-name ${PROJECT}-s3 2>/dev/null || true
  aws iam delete-user --user-name ${PROJECT}-s3
fi

# Security groups (RDS first — EC2 SG is referenced by the RDS SG rule) + key pair
aws ec2 delete-security-group --group-name ${PROJECT}-rds-sg 2>/dev/null || true
aws ec2 delete-security-group --group-name ${PROJECT}-ec2-sg 2>/dev/null || true
aws ec2 delete-key-pair --key-name ${PROJECT}-key 2>/dev/null || true

echo "Teardown complete. Confirm 0 across Instances/Volumes/RDS/S3 in the console."

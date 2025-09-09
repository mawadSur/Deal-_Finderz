# Deal Finder Infra — AWS CDK (Python)

Pure Python AWS CDK implementation mirroring the Terraform stack: VPC + subnets + NAT, Security Groups, S3, ALB, ECS Fargate, RDS Postgres, and ElastiCache Redis.

Note: Enabling PostGIS requires running `CREATE EXTENSION postgis;` against the DB after deploy (CDK example omitted for brevity). This can be automated with a Lambda-backed Custom Resource if desired.

## Prerequisites
- AWS credentials configured (e.g., `aws configure`)
- Python 3.9+
- AWS CDK v2 CLI (`npm i -g aws-cdk`)
- Docker installed (for bundling the PostGIS Lambda dependencies)

## Setup
```powershell
# From repo root
cd cdk
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -r requirements.txt

# Bootstrap once per account/region (if not already)
cdk bootstrap

# Edit cdk.json context or override via --context flags
# Important: set a real image and secure DB password
```

## Deploy
```powershell
# Uses context values in cdk/cdk.json by default
cd cdk
cdk deploy \
  -c app_image=123456789012.dkr.ecr.us-east-1.amazonaws.com/deal-finder:latest \
  -c db_password=REPLACE_ME_SECURELY
```

## Quick Deploy Script (Windows PowerShell)
- Ensures Docker is running, then deploys from the `cdk/` dir.
- Pass any CDK context or flags after the script path.

```powershell
.\u005cscripts\cdk-deploy.ps1 -c app_image=123456789012.dkr.ecr.us-east-1.amazonaws.com/deal-finder:latest -c db_password=REPLACE_ME_SECURELY
```

## Context keys (mirrors variables.tf)
- name, env, account_suffix, region, vpc_cidr
- app_image, app_port, health_check_path, task_cpu, task_memory, desired_count
- pg_version, pg_instance_class, db_name, db_username, db_password
- redis_version, redis_node_type

## Outputs
- alb_dns_name, service_url_http, rds_endpoint, redis_primary, s3_raw_bucket_name

## Notes
- VPC uses 2 AZs and 1 NAT (cost-optimized). Adjust in `deal_finder_stack.py` if needed.
- ECS task role gets S3 access to the raw bucket only.
- PostGIS automation: a Lambda-backed custom resource runs `CREATE EXTENSION IF NOT EXISTS postgis;` using pg8000 within the VPC. CDK bundles the dependency with Docker.

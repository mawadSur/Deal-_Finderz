# Deal Finder — Python Guide

This README focuses on the Python parts of the project:

- AWS CDK (Python) stack that provisions VPC, ALB, ECS Fargate, RDS Postgres, ElastiCache Redis, and an S3 bucket.
- A small Lambda (Python) used to enable PostGIS and run optional SQL migrations against the RDS database.

If you prefer a high‑level infra overview, see `README.MD`. For a CDK‑centric quick start, see `README_CDK.md`.

## Prerequisites
- Python 3.9+
- AWS CLI with credentials configured (`aws configure`)
- Node.js + AWS CDK v2 CLI (`npm i -g aws-cdk`)
- Docker (required to bundle Lambda dependencies during synth/deploy)

## Project Layout (Python)
```
cdk/
  app.py                     # CDK entrypoint; reads context from cdk.json or -c flags
  cdk.json                   # Default context values (image, db settings, etc.)
  deal_finder_stack.py       # Main infrastructure stack
  lambda/postgis/index.py    # Lambda to enable PostGIS + run SQL migrations
  lambda/postgis/sql/        # Optional SQL files (applied in sorted order)
scripts/
  cdk-deploy.ps1             # Convenience script for Windows PowerShell
```

## Setup
```powershell
# From repo root
cd cdk
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -r requirements.txt

# (First time per account/region)
cdk bootstrap
```

## Configure
You can set values in `cdk/cdk.json` or override at deploy time with `-c key=value`.

Important keys (defaults in `cdk.json`):

- name, env, account_suffix, region, vpc_cidr
- app_image, app_port, health_check_path, task_cpu, task_memory, desired_count
- pg_version, pg_instance_class, db_name, db_username, db_password
- redis_version, redis_node_type

Minimum you must change before a real deploy:

- app_image: ECR image URI for your application
- db_password: A secure password (do not commit secrets)

## Deploy
```powershell
cd cdk
cdk deploy \
  -c app_image=123456789012.dkr.ecr.us-east-1.amazonaws.com/deal-finder:latest \
  -c db_password=REPLACE_ME_SECURELY
```

Outputs include ALB DNS, RDS endpoint, Redis primary, and S3 bucket name.

## PostGIS Lambda and Migrations
The stack includes a Lambda (in `cdk/lambda/postgis/`) that can:

- Ensure `CREATE EXTENSION IF NOT EXISTS postgis;` is run on the RDS database.
- Optionally run SQL files in `lambda/postgis/sql/` in sorted order, tracking applied files in a `schema_migrations` table.

Environment variables expected by the Lambda (provided by the stack):

- DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

To add migrations, place `NNN_description.sql` files under `cdk/lambda/postgis/sql/`. Each file is split on semicolons and applied once.

## Local Iteration
- Validate changes: `cdk synth`, `cdk diff`
- Update dependencies: edit `cdk/requirements.txt`, then `pip install -r requirements.txt`
- If Docker isn’t running, bundling for the Lambda may fail; ensure Docker is up before synth/deploy.

## Cleanup
```powershell
cd cdk
cdk destroy
```

## Troubleshooting
- Missing credentials: ensure `aws sts get-caller-identity` works.
- Bundling errors: start Docker and retry `cdk synth` / `cdk deploy`.
- Health checks failing: confirm `health_check_path` matches your app and the container exposes `app_port`.

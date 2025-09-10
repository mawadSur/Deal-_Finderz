# Deal Finder Infra (AWS)

Infrastructure for the Deal Finder app on AWS. Two implementation options:

- Terraform modules/files for classic IaC.
- AWS CDK (Python) stack mirroring the same architecture.

Components provisioned: VPC + subnets + NAT, Security Groups, S3 (raw dumps), ALB, ECS Fargate Service, RDS PostgreSQL, PostGIS enablement, and ElastiCache Redis.

---

## Option A — Terraform

### Files
- providers.tf — Terraform + providers
- variables.tf — Input variables
- networking.tf — VPC, subnets, routes, NAT
- security_groups.tf — SGs for ALB/ECS/RDS/Redis
- s3.tf — Versioned, encrypted raw-dumps bucket
- alb.tf — ALB, target group, listener
- iam.tf — ECS task roles & S3 policy
- ecs.tf — ECS cluster/task/service + logs
- rds.tf — RDS PostgreSQL (Multi-AZ)
- postgis.tf — PostGIS extension enablement
- redis.tf — ElastiCache Redis replication group
- outputs.tf — Useful endpoints

### Usage
```bash
terraform init
terraform apply \
  -var 'account_suffix=abc123' \
  -var 'app_image=123456789012.dkr.ecr.us-east-1.amazonaws.com/deal-finder:latest' \
  -var 'db_username=appuser' \
  -var 'db_password=REPLACE_ME_SECURELY'
```

---

## Option B — AWS CDK (Python)

Pure Python AWS CDK implementation mirroring the Terraform stack.

### Prerequisites
- Python 3.9+
- AWS CLI with credentials configured (`aws configure`)
- Node.js + AWS CDK v2 CLI (`npm i -g aws-cdk`)
- Docker (for bundling Lambda dependencies)

### Project Layout
- `cdk/app.py`: CDK entrypoint (reads context from `cdk/cdk.json` or `-c` flags)
- `cdk/deal_finder_stack.py`: Main infrastructure stack
- `cdk/cdk.json`: Default context values (image, DB, Redis, etc.)
- `cdk/lambda/postgis/index.py`: Lambda to enable PostGIS + run optional SQL migrations
- `cdk/lambda/postgis/sql/`: Optional SQL files (applied in sorted order)
- `scripts/cdk-deploy.ps1`: Convenience deploy script (Windows PowerShell)

### Setup
```powershell
# From repo root
cd cdk
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -r requirements.txt

# First time per account/region
cdk bootstrap
```

### Configure
Set values in `cdk/cdk.json` or override at deploy time with `-c key=value`.

Important keys: `name`, `env`, `account_suffix`, `region`, `vpc_cidr`, `app_image`, `app_port`, `health_check_path`, `task_cpu`, `task_memory`, `desired_count`, `pg_version`, `pg_instance_class`, `db_name`, `db_username`, `db_password`, `redis_version`, `redis_node_type`.

Minimum required changes before a real deploy:
- `app_image`: ECR image URI for your application
- `db_password`: Secure password (do not commit secrets)

### Deploy
```powershell
cd cdk
cdk deploy \
  -c app_image=123456789012.dkr.ecr.us-east-1.amazonaws.com/deal-finder:latest \
  -c db_password=REPLACE_ME_SECURELY
```

Outputs include ALB DNS, RDS endpoint, Redis primary, and S3 bucket name.

### PostGIS Lambda and Migrations
- Ensures `CREATE EXTENSION IF NOT EXISTS postgis;` is run on RDS.
- Optionally runs SQL files from `cdk/lambda/postgis/sql/` in sorted order, tracking applied files in `schema_migrations`.
- Env provided by the stack: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`.

### Local Iteration
- Validate: `cdk synth`, `cdk diff`
- Dependencies: edit `cdk/requirements.txt`, then `pip install -r requirements.txt`
- Ensure Docker is running before synth/deploy

### Cleanup
```powershell
cd cdk
cdk destroy
```

### Troubleshooting
- Credentials: `aws sts get-caller-identity` should succeed
- Bundling errors: start Docker and retry `cdk synth` / `cdk deploy`
- Health checks: ensure `health_check_path` matches your app and container exposes `app_port`


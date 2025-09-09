# Deal Finder Infra (AWS + Terraform)

## Files
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

## Usage
```bash
terraform init
terraform apply \
  -var 'account_suffix=abc123' \
  -var 'app_image=123456789012.dkr.ecr.us-east-1.amazonaws.com/deal-finder:latest' \
  -var 'db_username=appuser' \
  -var 'db_password=REPLACE_ME_SECURELY'

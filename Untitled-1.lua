# =====================================================================
# root/main.tf  —  AWS real estate "deal finder" infra (ECS + RDS + S3 + Redis)
# =====================================================================

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    postgresql = {
      source  = "cyrilgdn/postgresql"
      version = "~> 1.22"
    }
  }
}

provider "aws" {
  region = var.region
}

# --------------------------
# Networking (VPC & Subnets)
# --------------------------
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = { Name = "${var.name}-vpc" }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.name}-igw" }
}

# 2 public + 2 private subnets across AZs
resource "aws_subnet" "public" {
  for_each                = toset(slice(data.aws_availability_zones.available.names, 0, 2))
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, index(data.aws_availability_zones.available.names, each.key))
  availability_zone       = each.key
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.name}-public-${each.key}" }
}

resource "aws_subnet" "private" {
  for_each          = toset(slice(data.aws_availability_zones.available.names, 0, 2))
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, 8 + index(data.aws_availability_zones.available.names, each.key))
  availability_zone = each.key
  tags              = { Name = "${var.name}-private-${each.key}" }
}

data "aws_availability_zones" "available" {}

resource "aws_eip" "nat" {
  domain = "vpc"
}

resource "aws_nat_gateway" "nat" {
  allocation_id = aws_eip.nat.id
  subnet_id     = values(aws_subnet.public)[0].id
  tags          = { Name = "${var.name}-nat" }
  depends_on    = [aws_internet_gateway.igw]
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
  tags = { Name = "${var.name}-public-rt" }
}

resource "aws_route_table_association" "public_assoc" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat.id
  }
  tags = { Name = "${var.name}-private-rt" }
}

resource "aws_route_table_association" "private_assoc" {
  for_each       = aws_subnet.private
  subnet_id      = each.value.id
  route_table_id = aws_route_table.private.id
}

# --------------------------
# S3 bucket for raw data
# --------------------------
resource "aws_s3_bucket" "raw" {
  bucket = "${var.name}-raw-${var.env}-${var.account_suffix}"
  force_destroy = false
  tags = { Purpose = "raw-dumps" }
}

resource "aws_s3_bucket_versioning" "raw" {
  bucket = aws_s3_bucket.raw.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket = aws_s3_bucket.raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --------------------------
# Security Groups
# --------------------------
resource "aws_security_group" "alb" {
  name   = "${var.name}-alb-sg"
  vpc_id = aws_vpc.main.id
  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress { from_port = 0 to_port = 0 protocol = "-1" cidr_blocks = ["0.0.0.0/0"] }
}

resource "aws_security_group" "ecs_tasks" {
  name   = "${var.name}-ecs-sg"
  vpc_id = aws_vpc.main.id
  ingress {
    description     = "ALB to ECS"
    from_port       = var.app_port
    to_port         = var.app_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress { from_port = 0 to_port = 0 protocol = "-1" cidr_blocks = ["0.0.0.0/0"] }
}

resource "aws_security_group" "rds" {
  name   = "${var.name}-rds-sg"
  vpc_id = aws_vpc.main.id
  ingress {
    description     = "ECS to Postgres"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }
  egress { from_port = 0 to_port = 0 protocol = "-1" cidr_blocks = ["0.0.0.0/0"] }
}

resource "aws_security_group" "redis" {
  name   = "${var.name}-redis-sg"
  vpc_id = aws_vpc.main.id
  ingress {
    description     = "ECS to Redis"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }
  egress { from_port = 0 to_port = 0 protocol = "-1" cidr_blocks = ["0.0.0.0/0"] }
}

# --------------------------
# ALB for ECS Service
# --------------------------
resource "aws_lb" "app" {
  name               = "${var.name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [for s in aws_subnet.public : s.id]
}

resource "aws_lb_target_group" "app" {
  name     = "${var.name}-tg"
  port     = var.app_port
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id
  target_type = "ip"
  health_check {
    path                = var.health_check_path
    matcher             = "200-399"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# --------------------------
# IAM (ECS execution + task)
# --------------------------
data "aws_iam_policy_document" "assume_task_exec" {
  statement {
    actions = ["sts:AssumeRole"]
    principals { type = "Service" identifiers = ["ecs-tasks.amazonaws.com"] }
  }
}

resource "aws_iam_role" "ecs_task_execution" {
  name               = "${var.name}-ecsTaskExecutionRole"
  assume_role_policy = data.aws_iam_policy_document.assume_task_exec.json
}

resource "aws_iam_role_policy_attachment" "ecs_exec_attach" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Task role (app permissions, e.g. S3 read/write)
resource "aws_iam_role" "ecs_task" {
  name               = "${var.name}-ecsTaskRole"
  assume_role_policy = data.aws_iam_policy_document.assume_task_exec.json
}

data "aws_iam_policy_document" "app_policy" {
  statement {
    sid     = "S3AccessRawBucket"
    actions = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
    resources = [
      aws_s3_bucket.raw.arn,
      "${aws_s3_bucket.raw.arn}/*"
    ]
  }
}

resource "aws_iam_policy" "app" {
  name   = "${var.name}-app-policy"
  policy = data.aws_iam_policy_document.app_policy.json
}

resource "aws_iam_role_policy_attachment" "app_attach" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = aws_iam_policy.app.arn
}

# --------------------------
# ECS (Fargate) Cluster & Service
# --------------------------
resource "aws_ecs_cluster" "this" {
  name = "${var.name}-cluster"
}

resource "aws_ecs_task_definition" "app" {
  family                   = "${var.name}-td"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = tostring(var.task_cpu)
  memory                   = tostring(var.task_memory)
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "app"
      image     = var.app_image
      essential = true
      portMappings = [{ containerPort = var.app_port, protocol = "tcp" }]
      environment = [
        { name = "REDIS_URL", value = "redis://${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379" },
        { name = "DATABASE_URL", value = "postgresql://${var.db_username}:${var.db_password}@${aws_db_instance.pg.address}:5432/${var.db_name}" },
        { name = "S3_RAW_BUCKET", value = aws_s3_bucket.raw.bucket }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = "/ecs/${var.name}"
          awslogs-region        = var.region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${var.name}"
  retention_in_days = 14
}

resource "aws_ecs_service" "app" {
  name            = "${var.name}-svc"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = [for s in aws_subnet.private : s.id]
    security_groups = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = var.app_port
  }

  lifecycle { ignore_changes = [task_definition] }
  depends_on = [aws_lb_listener.http]
}

# --------------------------
# RDS PostgreSQL (+ PostGIS)
# --------------------------
resource "aws_db_subnet_group" "pg" {
  name       = "${var.name}-pg-subnets"
  subnet_ids = [for s in aws_subnet.private : s.id]
}

resource "aws_db_instance" "pg" {
  identifier              = "${var.name}-pg"
  engine                  = "postgres"
  engine_version          = var.pg_version
  instance_class          = var.pg_instance_class
  allocated_storage       = 50
  max_allocated_storage   = 200
  db_name                 = var.db_name
  username                = var.db_username
  password                = var.db_password
  db_subnet_group_name    = aws_db_subnet_group.pg.name
  vpc_security_group_ids  = [aws_security_group.rds.id]
  storage_encrypted       = true
  backup_retention_period = 7
  deletion_protection     = true
  multi_az                = true
  publicly_accessible     = false
  skip_final_snapshot     = false
  performance_insights_enabled = true
}

# Create PostGIS extension using the PostgreSQL provider once DB is up.
provider "postgresql" {
  host            = aws_db_instance.pg.address
  port            = 5432
  database        = var.db_name
  username        = var.db_username
  password        = var.db_password
  sslmode         = "require"
  connect_timeout = 15
}

resource "postgresql_extension" "postgis" {
  name = "postgis"
  depends_on = [aws_db_instance.pg]
}

# --------------------------
# ElastiCache Redis (cluster mode disabled, 1 primary + 1 replica)
# --------------------------
resource "aws_elasticache_subnet_group" "redis" {
  name       = "${var.name}-redis-subnets"
  subnet_ids = [for s in aws_subnet.private : s.id]
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id          = "${var.name}-redis"
  description                   = "Redis for ${var.name}"
  engine                        = "redis"
  engine_version                = var.redis_version
  node_type                     = var.redis_node_type
  automatic_failover_enabled    = true
  multi_az_enabled              = true
  number_cache_clusters         = 2
  subnet_group_name             = aws_elasticache_subnet_group.redis.name
  security_group_ids            = [aws_security_group.redis.id]
  at_rest_encryption_enabled    = true
  transit_encryption_enabled    = true
  parameter_group_name          = "default.redis7"
}

# --------------------------
# Outputs
# --------------------------
output "alb_dns_name"       { value = aws_lb.app.dns_name }
output "service_url_http"   { value = "http://${aws_lb.app.dns_name}" }
output "rds_endpoint"       { value = aws_db_instance.pg.address }
output "redis_primary"      { value = aws_elasticache_replication_group.redis.primary_endpoint_address }
output "s3_raw_bucket_name" { value = aws_s3_bucket.raw.bucket }

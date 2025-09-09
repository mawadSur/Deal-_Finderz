resource "aws_security_group" "alb" {
  name   = "${var.name}-alb-sg"
  vpc_id = aws_vpc.main.id
  ingress { description = "HTTP" from_port = 80 to_port = 80 protocol = "tcp" cidr_blocks = ["0.0.0.0/0"] }
  egress  { from_port = 0 to_port = 0 protocol = "-1" cidr_blocks = ["0.0.0.0/0"] }
}

resource "aws_security_group" "ecs_tasks" {
  name   = "${var.name}-ecs-sg"
  vpc_id = aws_vpc.main.id
  ingress { description = "ALB to ECS" from_port = var.app_port to_port = var.app_port protocol = "tcp" security_groups = [aws_security_group.alb.id] }
  egress  { from_port = 0 to_port = 0 protocol = "-1" cidr_blocks = ["0.0.0.0/0"] }
}

resource "aws_security_group" "rds" {
  name   = "${var.name}-rds-sg"
  vpc_id = aws_vpc.main.id
  ingress { description = "ECS to Postgres" from_port = 5432 to_port = 5432 protocol = "tcp" security_groups = [aws_security_group.ecs_tasks.id] }
  egress  { from_port = 0 to_port = 0 protocol = "-1" cidr_blocks = ["0.0.0.0/0"] }
}

resource "aws_security_group" "redis" {
  name   = "${var.name}-redis-sg"
  vpc_id = aws_vpc.main.id
  ingress { description = "ECS to Redis" from_port = 6379 to_port = 6379 protocol = "tcp" security_groups = [aws_security_group.ecs_tasks.id] }
  egress  { from_port = 0 to_port = 0 protocol = "-1" cidr_blocks = ["0.0.0.0/0"] }
}

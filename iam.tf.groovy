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

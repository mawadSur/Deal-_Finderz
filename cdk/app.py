#!/usr/bin/env python3
import os
from aws_cdk import App, Environment
from deal_finder_stack import DealFinderStack


app = App()

ctx = app.node.try_get_context

stack = DealFinderStack(
    app,
    "DealFinderStack",
    env=Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", ctx("region") or "us-east-1"),
    ),
    name=ctx("name") or "deal-finder",
    env_name=ctx("env") or "prod",
    account_suffix=ctx("account_suffix") or "abc123",
    vpc_cidr=ctx("vpc_cidr") or "10.0.0.0/16",
    app_image=ctx("app_image") or "REPLACE_WITH_IMAGE",
    app_port=int(ctx("app_port") or 8080),
    health_check_path=ctx("health_check_path") or "/health",
    task_cpu=int(ctx("task_cpu") or 512),
    task_memory=int(ctx("task_memory") or 1024),
    desired_count=int(ctx("desired_count") or 2),
    pg_version=ctx("pg_version") or "16.3",
    pg_instance_class=ctx("pg_instance_class") or "t3.medium",
    db_name=ctx("db_name") or "deals",
    db_username=ctx("db_username") or "appuser",
    db_password=ctx("db_password") or "REPLACE_ME_SECURELY",
    redis_version=ctx("redis_version") or "7.1",
    redis_node_type=ctx("redis_node_type") or "cache.t3.small",
)

app.synth()


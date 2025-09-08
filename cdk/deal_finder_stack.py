from typing import Optional

from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    SecretValue,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_s3 as s3,
    aws_elasticloadbalancingv2 as elbv2,
    aws_ecs as ecs,
    aws_logs as logs,
    aws_rds as rds,
    aws_elasticache as elasticache,
)
from constructs import Construct


class DealFinderStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        name: str,
        env_name: str,
        account_suffix: str,
        vpc_cidr: str,
        app_image: str,
        app_port: int,
        health_check_path: str,
        task_cpu: int,
        task_memory: int,
        desired_count: int,
        pg_version: str,
        pg_instance_class: str,
        db_name: str,
        db_username: str,
        db_password: str,
        redis_version: str,
        redis_node_type: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --------------------------
        # Networking (VPC with 2 AZs, 1 NAT)
        # --------------------------
        vpc = ec2.Vpc(
            self,
            "Vpc",
            ip_addresses=ec2.IpAddresses.cidr(vpc_cidr),
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=20),
                ec2.SubnetConfiguration(name="private", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, cidr_mask=20),
            ],
        )

        # --------------------------
        # Security Groups
        # --------------------------
        sg_alb = ec2.SecurityGroup(self, "AlbSg", vpc=vpc, allow_all_outbound=True, security_group_name=f"{name}-alb-sg")
        sg_alb.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP")

        sg_ecs = ec2.SecurityGroup(self, "EcsSg", vpc=vpc, allow_all_outbound=True, security_group_name=f"{name}-ecs-sg")
        sg_ecs.add_ingress_rule(sg_alb, ec2.Port.tcp(app_port), "ALB to ECS")

        sg_rds = ec2.SecurityGroup(self, "RdsSg", vpc=vpc, allow_all_outbound=True, security_group_name=f"{name}-rds-sg")
        sg_rds.add_ingress_rule(sg_ecs, ec2.Port.tcp(5432), "ECS to Postgres")

        sg_redis = ec2.SecurityGroup(self, "RedisSg", vpc=vpc, allow_all_outbound=True, security_group_name=f"{name}-redis-sg")
        sg_redis.add_ingress_rule(sg_ecs, ec2.Port.tcp(6379), "ECS to Redis")

        # --------------------------
        # S3 Bucket (raw dumps)
        # --------------------------
        bucket = s3.Bucket(
            self,
            "RawBucket",
            bucket_name=f"{name}-raw-{env_name}-{account_suffix}",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
        )
        bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="HttpsOnly",
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["s3:*"],
                resources=[bucket.bucket_arn, f"{bucket.bucket_arn}/*"],
                conditions={"Bool": {"aws:SecureTransport": "false"}},
            )
        )

        # --------------------------
        # ALB + Listener + TargetGroup
        # --------------------------
        alb = elbv2.ApplicationLoadBalancer(
            self,
            "Alb",
            vpc=vpc,
            internet_facing=True,
            security_group=sg_alb,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            load_balancer_name=f"{name}-alb",
        )
        listener = alb.add_listener("Http", port=80, open=True)

        # --------------------------
        # ECS Cluster + Task + Service
        # --------------------------
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc, cluster_name=f"{name}-cluster")

        log_group = logs.LogGroup(self, "EcsLogs", log_group_name=f"/ecs/{name}", retention=logs.RetentionDays.TWO_WEEKS)
        log_driver = ecs.LogDrivers.aws_logs(stream_prefix="ecs", log_group=log_group)

        task_def = ecs.FargateTaskDefinition(
            self,
            "TaskDef",
            cpu=task_cpu,
            memory_limit_mib=task_memory,
        )
        # S3 access policy for app
        task_def.add_to_task_role_policy(
            iam.PolicyStatement(
                actions=["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
                resources=[bucket.bucket_arn, f"{bucket.bucket_arn}/*"],
            )
        )

        container = task_def.add_container(
            "app",
            image=ecs.ContainerImage.from_registry(app_image),
            logging=log_driver,
            environment={
                # Values wired after defining RDS/Redis below using .add_environment
            },
        )
        container.add_port_mappings(ecs.PortMapping(container_port=app_port, protocol=ecs.Protocol.TCP))

        service = ecs.FargateService(
            self,
            "Service",
            cluster=cluster,
            task_definition=task_def,
            desired_count=desired_count,
            assign_public_ip=False,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[sg_ecs],
            service_name=f"{name}-svc",
        )

        target_group = elbv2.ApplicationTargetGroup(
            self,
            "AppTg",
            vpc=vpc,
            port=app_port,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                path=health_check_path,
                healthy_http_codes="200-399",
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                healthy_threshold_count=2,
                unhealthy_threshold_count=2,
            ),
        )
        service.attach_to_application_target_group(target_group)
        listener.add_target_groups("Default", target_groups=[target_group])

        # --------------------------
        # RDS PostgreSQL (Multi-AZ)
        # --------------------------
        db = rds.DatabaseInstance(
            self,
            "Pg",
            engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.of(pg_version)),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.of(pg_instance_class.split(".")[0].upper()), ec2.InstanceSize.of(pg_instance_class.split(".")[1].upper())) if "." in pg_instance_class else ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MEDIUM),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[sg_rds],
            multi_az=True,
            allocated_storage=50,
            max_allocated_storage=200,
            publicly_accessible=False,
            deletion_protection=True,
            storage_encrypted=True,
            backup_retention=Duration.days(7),
            database_name=db_name,
            credentials=rds.Credentials.from_password(db_username, SecretValue.unsafe_plain_text(db_password)),
            instance_identifier=f"{name}-pg",
        )

        # Note: Enabling PostGIS requires connecting to the DB and running
        # CREATE EXTENSION postgis; You can implement a Lambda-backed Custom
        # Resource to run this after deploy, or do it via migration tooling.

        # --------------------------
        # ElastiCache Redis
        # --------------------------
        redis_subnet = elasticache.CfnSubnetGroup(
            self,
            "RedisSubnets",
            description=f"Redis for {name}",
            subnet_ids=[s.subnet_id for s in vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS).subnets],
            cache_subnet_group_name=f"{name}-redis-subnets",
        )

        redis = elasticache.CfnReplicationGroup(
            self,
            "Redis",
            replication_group_id=f"{name}-redis",
            engine="redis",
            engine_version=redis_version,
            cache_node_type=redis_node_type,
            num_cache_clusters=2,
            automatic_failover_enabled=True,
            multi_az_enabled=True,
            cache_subnet_group_name=redis_subnet.cache_subnet_group_name,
            security_group_ids=[sg_redis.security_group_id],
            at_rest_encryption_enabled=True,
            transit_encryption_enabled=True,
        )
        redis.add_dependency(redis_subnet)

        # Now that DB and Redis exist, wire container env
        container.add_environment("S3_RAW_BUCKET", bucket.bucket_name)
        container.add_environment("REDIS_URL", f"redis://{redis.attr_primary_end_point_address}:6379")
        container.add_environment(
            "DATABASE_URL", f"postgresql://{db_username}:{db_password}@{db.instance_endpoint.hostname}:5432/{db_name}"
        )

        # --------------------------
        # Outputs
        # --------------------------
        CfnOutput(self, "alb_dns_name", value=alb.load_balancer_dns_name)
        CfnOutput(self, "service_url_http", value=f"http://{alb.load_balancer_dns_name}")
        CfnOutput(self, "rds_endpoint", value=db.instance_endpoint.hostname)
        CfnOutput(self, "redis_primary", value=redis.attr_primary_end_point_address)
        CfnOutput(self, "s3_raw_bucket_name", value=bucket.bucket_name)


from aws_cdk import (
    Stack, Duration, CfnOutput, RemovalPolicy,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecr_assets as ecr_assets,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_s3 as s3,
)
from constructs import Construct
from pathlib import Path


class GridShiftStack(Stack):
    """Small deployable AWS execution plane for GridShift."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        root = Path(__file__).resolve().parents[1]

        # A dedicated small VPC avoids reliance on default-VPC existence.
        # Public subnets and no inbound rules avoid NAT costs for this demo.
        vpc = ec2.Vpc(self, "Vpc", max_azs=2, nat_gateways=0,
                      subnet_configuration=[ec2.SubnetConfiguration(
                          name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24
                      )])
        security_group = ec2.SecurityGroup(self, "WorkerSecurityGroup", vpc=vpc,
                                           allow_all_outbound=True,
                                           description="Outbound-only GridShift worker")
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc)
        log_group = logs.LogGroup(self, "WorkerLogs", log_group_name="/gridshift/worker",
                                  retention=logs.RetentionDays.ONE_WEEK,
                                  removal_policy=RemovalPolicy.DESTROY)
        image = ecr_assets.DockerImageAsset(self, "WorkerImage", directory=str(root / "worker"))
        task = ecs.FargateTaskDefinition(self, "WorkerTask", cpu=256, memory_limit_mib=512)
        task.add_container("worker", image=ecs.ContainerImage.from_docker_image_asset(image),
                           logging=ecs.LogDrivers.aws_logs(stream_prefix="job", log_group=log_group),
                           environment={"JOB_ID": "unset"})
        # Worker writes results to stdout/CloudWatch; optional S3 bucket for experiment artifacts.
        bucket = s3.Bucket(self, "Artifacts", block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                           enforce_ssl=True, removal_policy=RemovalPolicy.RETAIN)

        dispatcher = lambda_.Function(self, "Dispatcher", runtime=lambda_.Runtime.PYTHON_3_12,
                                      handler="handler.handler",
                                      code=lambda_.Code.from_asset(str(root / "dispatch_lambda")),
                                      timeout=Duration.seconds(30),
                                      environment={
                                          "CLUSTER_ARN": cluster.cluster_arn,
                                          "TASK_DEFINITION_ARN": task.task_definition_arn,
                                          "SUBNET_IDS": ",".join(s.subnet_id for s in vpc.public_subnets),
                                          "SECURITY_GROUP_ID": security_group.security_group_id,
                                          "CONTAINER_NAME": "worker",
                                      })
        dispatcher.add_to_role_policy(iam.PolicyStatement(
            actions=["ecs:RunTask"], resources=[task.task_definition_arn],
            conditions={"ArnEquals": {"ecs:cluster": cluster.cluster_arn}}))
        dispatcher.add_to_role_policy(iam.PolicyStatement(
            actions=["iam:PassRole"],
            resources=[task.execution_role.role_arn, task.task_role.role_arn]))

        # Scheduler assumes this role to invoke the dispatcher.
        schedule_role = iam.Role(self, "SchedulerInvokeRole",
                                 assumed_by=iam.ServicePrincipal("scheduler.amazonaws.com"))
        schedule_role.add_to_policy(iam.PolicyStatement(
            actions=["lambda:InvokeFunction"], resources=[dispatcher.function_arn]))

        CfnOutput(self, "DispatcherArn", value=dispatcher.function_arn)
        CfnOutput(self, "SchedulerRoleArn", value=schedule_role.role_arn)
        CfnOutput(self, "ClusterArn", value=cluster.cluster_arn)
        CfnOutput(self, "TaskDefinitionArn", value=task.task_definition_arn)
        CfnOutput(self, "ArtifactsBucket", value=bucket.bucket_name)
        CfnOutput(self, "WorkerLogGroup", value=log_group.log_group_name)

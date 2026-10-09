"""EventBridge Scheduler -> Lambda -> ECS RunTask.

No arbitrary image/command inputs accepted. The task definition is preapproved.
"""
import hashlib
import json
import os
import re
import boto3

JOB_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def dispatch(event, ecs_client, environ):
    job_id = event.get("job_id")
    if not isinstance(job_id, str) or not JOB_ID_PATTERN.fullmatch(job_id):
        raise ValueError("Invalid job_id")
    # Stable token deduplicates retry attempts within ECS idempotency retention window.
    token = hashlib.sha256(f"gridshift:{job_id}".encode()).hexdigest()[:64]
    result = ecs_client.run_task(
        cluster=environ["CLUSTER_ARN"],
        taskDefinition=environ["TASK_DEFINITION_ARN"],
        launchType="FARGATE",
        count=1,
        clientToken=token,
        networkConfiguration={"awsvpcConfiguration": {
            "subnets": environ["SUBNET_IDS"].split(","),
            "securityGroups": [environ["SECURITY_GROUP_ID"]],
            "assignPublicIp": "ENABLED",
        }},
        overrides={"containerOverrides": [{
            "name": environ.get("CONTAINER_NAME", "worker"),
            "environment": [{"name": "JOB_ID", "value": job_id}],
        }]},
    )
    if result.get("failures"):
        raise RuntimeError(f"ECS RunTask failures: {json.dumps(result['failures'])}")
    tasks = result.get("tasks", [])
    if not tasks:
        raise RuntimeError("ECS returned no task")
    return {"job_id": job_id, "task_arn": tasks[0]["taskArn"]}


def handler(event, context):
    return dispatch(event, boto3.client("ecs"), os.environ)

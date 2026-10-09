"""Read execution status when the backend has a task ARN."""
import boto3


def get_task_status(cluster_arn: str, task_arn: str, ecs_client=None) -> dict:
    ecs_client = ecs_client or boto3.client("ecs")
    response = ecs_client.describe_tasks(cluster=cluster_arn, tasks=[task_arn])
    tasks = response.get("tasks", [])
    if not tasks:
        return {"task_arn": task_arn, "status": "NOT_FOUND"}
    task = tasks[0]
    return {"task_arn": task_arn, "status": task.get("lastStatus", "UNKNOWN"),
            "stop_code": task.get("stopCode"),
            "containers": [{"name": c.get("name"), "exit_code": c.get("exitCode")}
                           for c in task.get("containers", [])]}

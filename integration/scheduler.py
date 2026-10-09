"""Call from the teammate's backend after optimization.

Credentials are resolved through the standard AWS SDK credential chain.
"""
import json
import os
import re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

JOB_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def schedule_job(job_id: str, run_at: datetime | str, *,
                 dispatcher_arn: str | None = None,
                 scheduler_role_arn: str | None = None,
                 scheduler_client=None) -> dict:
    """Create a one-time UTC schedule; run_at must include a timezone.

    Returns the AWS schedule ARN and normalized planned timestamp.
    Requires scheduler:CreateSchedule and iam:PassRole for the scheduler role.
    """
    if not JOB_ID_PATTERN.fullmatch(job_id) or len(job_id) > 54:
        raise ValueError("job_id must be 1-54 alphanumeric, hyphen, underscore chars")
    if isinstance(run_at, str):
        run_at = datetime.fromisoformat(run_at.replace("Z", "+00:00"))
    if not isinstance(run_at, datetime) or run_at.tzinfo is None or run_at.utcoffset() is None:
        raise ValueError("run_at must be a timezone-aware datetime")
    utc = run_at.astimezone(timezone.utc)
    if utc <= datetime.now(timezone.utc) + timedelta(minutes=2):
        raise ValueError("run_at must be more than 2 minutes in the future")
    dispatcher_arn = dispatcher_arn or os.environ.get("GRIDSHIFT_DISPATCHER_ARN")
    scheduler_role_arn = scheduler_role_arn or os.environ.get("GRIDSHIFT_SCHEDULER_ROLE_ARN")
    if not dispatcher_arn or not scheduler_role_arn:
        raise ValueError("Dispatcher and scheduler role ARNs are required")
    if scheduler_client is None:
        import boto3
        scheduler_client = boto3.client("scheduler")
    # AWS Scheduler one-time expressions have minute precision.
    schedule_time = utc.replace(second=0, microsecond=0)
    response = scheduler_client.create_schedule(
        Name=f"gridshift-{job_id}",
        ScheduleExpression=f"at({schedule_time.strftime('%Y-%m-%dT%H:%M:%S')})",
        ScheduleExpressionTimezone="UTC",
        FlexibleTimeWindow={"Mode": "OFF"},
        ActionAfterCompletion="DELETE",
        State="ENABLED",
        Target={"Arn": dispatcher_arn, "RoleArn": scheduler_role_arn,
                "Input": json.dumps({"job_id": job_id})},
        Description="GridShift optimized one-time job dispatch",
    )
    return {"job_id": job_id, "schedule_arn": response["ScheduleArn"],
            "scheduled_at": schedule_time.isoformat()}

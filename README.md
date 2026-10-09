# GridShift AWS execution module

Standalone infrastructure and runtime integration for GridShift. The model/backend/dashboard live in the team's main repository.

## What it does

- Python AWS CDK provisions a small VPC, ECS Fargate cluster/task, CDK-managed ECR image asset, dispatcher Lambda, EventBridge Scheduler invoke role, CloudWatch log group, and S3 artifacts bucket.
- `integration.schedule_job(job_id, run_at)` creates a one-time EventBridge schedule.
- Scheduler invokes Lambda, which starts a real CPU batch job in ECS Fargate.
- Worker emits JSON start/completion records to CloudWatch.

## Prerequisites

AWS account with permission to deploy CloudFormation, IAM, EC2/VPC, ECS, ECR, Lambda, EventBridge Scheduler, CloudWatch Logs, and S3; working AWS CLI credentials; Node 20+; CDK CLI; Docker Desktop running; Python 3.12 recommended.

**Current account blocker:** An AWS Organizations SCP explicitly denies ECS API operations in the user's current AWS Free Plan account. IAM changes, CDK, and CloudShell cannot bypass this. Deployment requires an authorized AWS account. No live deployment has been verified.

## Local validation (PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -q

docker build -t gridshift-worker ./worker
docker run --rm -e JOB_ID=local-test gridshift-worker
```

## Deploy in an authorized AWS account

```powershell
aws sts get-caller-identity
$env:CDK_DEFAULT_REGION = "ap-south-1"
cdk bootstrap aws://ACCOUNT_ID/ap-south-1
cdk synth
cdk deploy --outputs-file outputs.json
```

Replace `ACCOUNT_ID` with the account being deployed to. CDK DockerImageAsset builds the worker and publishes the image to the CDK bootstrap ECR repository; no manual ECR push is needed.

Copy `DispatcherArn` and `SchedulerRoleArn` from the CDK stack outputs into your backend configuration. Do not commit credentials or private `.env` files.

## Integration with the optimizer/backend

```python
from datetime import datetime, timedelta, timezone
from integration.scheduler import schedule_job

result = schedule_job(
    "job_001",
    datetime.now(timezone.utc) + timedelta(minutes=10),
    dispatcher_arn="<DispatcherArn from CDK output>",
    scheduler_role_arn="<SchedulerRoleArn from CDK output>",
)
print(result)
```

The calling IAM identity must have `scheduler:CreateSchedule` and `iam:PassRole` restricted to the scheduler invoke role. This role is assumed by EventBridge Scheduler and can invoke only the dispatcher Lambda.

**Schedule time caveat:** EventBridge Scheduler has minute-level precision and delivery can be delayed. Fargate container startup adds further latency. Do not promise exact-second launches or strict deadlines without slack.

**Status caveat:** `schedule_job` returns the schedule ARN, not the ECS task ARN. Lambda logs the dispatch result automatically, but the minimal module does not persist a mapping from job ID to task ARN. For the demo, verify tasks through ECS/CloudWatch. To support a backend job-status API, add a durable task-ARN handoff (e.g. S3 or DynamoDB) and then call `integration.status.get_task_status`.

**Idempotency caveat:** ECS `clientToken` deduplicates retries within AWS's retention window. It does not guarantee exactly-once execution across all failures, nor does this MVP reconcile missing launches.

**Security/cost:** Worker uses a public subnet with a public IP, outbound-only security group, and no inbound ports. This is a hackathon trade-off to avoid NAT Gateway charges, not a production design. CDK bootstrap and container image assets may incur costs. Set a budget and clean up after the demo. S3 bucket is retained by design; delete it separately if no longer needed.

## Cleanup

```powershell
cdk destroy
```

CloudFormation removal leaves the S3 artifacts bucket retained. Check for EventBridge schedules, ECS tasks, and bootstrap assets before considering the account clean. Scheduler one-time schedules use `ActionAfterCompletion=DELETE`.

## Module contract

Input: unique `job_id` (alphanumeric, `_`, `-`, up to 54 chars) and timezone-aware `run_at` at least 2 minutes in the future.
Output: `job_id`, AWS `schedule_arn`, normalized UTC `scheduled_at`.

Modeling grid-demand savings and selecting execution times are **not** part of this AWS module. AWS deployment demonstrates execution, not physical grid-demand or carbon reduction.

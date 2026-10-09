import pytest
from dispatch_lambda.handler import dispatch

ENV = {"CLUSTER_ARN":"cluster", "TASK_DEFINITION_ARN":"task", "SUBNET_IDS":"subnet-1,subnet-2",
       "SECURITY_GROUP_ID":"sg-1", "CONTAINER_NAME":"worker"}

class FakeEcs:
    def __init__(self): self.kwargs = None
    def run_task(self, **kwargs):
        self.kwargs = kwargs
        return {"tasks":[{"taskArn":"arn:task:123"}],"failures":[]}

def test_dispatch():
    ecs = FakeEcs()
    result = dispatch({"job_id":"job_1"}, ecs, ENV)
    assert result["task_arn"] == "arn:task:123"
    assert ecs.kwargs["launchType"] == "FARGATE"
    assert ecs.kwargs["overrides"]["containerOverrides"][0]["environment"][0]["value"] == "job_1"

def test_reject_untrusted_job_id():
    with pytest.raises(ValueError): dispatch({"job_id":"../../foo"}, FakeEcs(), ENV)

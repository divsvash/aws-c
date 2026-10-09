from datetime import datetime, timedelta, timezone
import pytest
from integration.scheduler import schedule_job

class FakeScheduler:
    def __init__(self): self.kwargs = None
    def create_schedule(self, **kwargs):
        self.kwargs = kwargs
        return {"ScheduleArn": "arn:aws:scheduler:ap-south-1:111122223333:schedule/default/gridshift-job_1"}

def test_create_schedule():
    client = FakeScheduler()
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    result = schedule_job("job_1", future, dispatcher_arn="arn:lambda",
                          scheduler_role_arn="arn:role", scheduler_client=client)
    assert result["job_id"] == "job_1"
    assert client.kwargs["Target"]["Arn"] == "arn:lambda"
    assert client.kwargs["FlexibleTimeWindow"]["Mode"] == "OFF"
    assert client.kwargs["ActionAfterCompletion"] == "DELETE"

def test_reject_naive_time():
    with pytest.raises(ValueError): schedule_job("job_1", datetime.now())

def test_reject_bad_job_id():
    with pytest.raises(ValueError): schedule_job("../bad", datetime.now(timezone.utc))

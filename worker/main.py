"""Real, bounded CPU batch workload; replace with approved job types later."""
import json
import os
import time
from datetime import datetime, timezone


def emit(event, **details):
    print(json.dumps({"event": event, "at": datetime.now(timezone.utc).isoformat(), **details}), flush=True)


def main():
    job_id = os.environ.get("JOB_ID", "manual-test")
    emit("job_started", job_id=job_id)
    start = time.monotonic()
    result = sum(i * i for i in range(2_000_000))
    emit("job_completed", job_id=job_id, result=result,
         duration_seconds=round(time.monotonic() - start, 3))


if __name__ == "__main__":
    main()

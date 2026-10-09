import uuid

from .registry import job

# Temporary calling boundary (spec D5 "Staging"): until M4 the only production task is this
# probe, called only by the M0c tests. Its id points at their test-only jobs_probe table.


@job(name="jobs.noop", queue="default", ids={"probe_id": "jobs_probe"})
def noop(probe_id: uuid.UUID) -> None:
    pass

# Fixture for `semgrep --test semgrep/` (rule jobs-no-direct-defer).
from jobs.enqueue import enqueue_in_tx
from jobs.tasks import noop


def banned(probe_id, other):
    # ruleid: jobs-no-direct-defer
    noop.defer(probe_id=probe_id)
    # ruleid: jobs-no-direct-defer
    noop.defer_async(probe_id=probe_id)
    # ruleid: jobs-no-direct-defer
    noop.batch_defer({"probe_id": probe_id}, {"probe_id": other})
    # ruleid: jobs-no-direct-defer
    noop.batch_defer_async({"probe_id": probe_id})
    # ruleid: jobs-no-direct-defer
    noop.configure(queue="default").defer(probe_id=probe_id)
    # ruleid: jobs-no-direct-defer
    noop.configure(lock="x").defer_async(probe_id=probe_id)


def allowed(probe_id):
    # ok: jobs-no-direct-defer
    enqueue_in_tx(noop, probe_id=probe_id)

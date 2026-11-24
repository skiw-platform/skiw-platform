# The index on security_event.agency_id (plan row M4r-1c): the RLS predicate's own-agency branch
# and the FK of 0024 use it (tenancy test_row_level_live [A5]). The table is written on every login
# attempt, so it is built CONCURRENTLY, outside a transaction (atomic = False), with no write lock.

from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("accounts", "0022_security_event_agency"),
    ]

    operations = [
        AddIndexConcurrently(
            model_name="securityevent",
            index=models.Index(fields=["agency_id"], name="security_event_agency_id"),
        ),
    ]

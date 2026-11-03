"""The closed list of global tables (spec §4.1 "Global tables … the complete list"; plan M4c-6a).
Every other table is the tenant root `agency` or tenant-owned and must meet spec §4.2; the schema
check (M4c-6b) and `test_queue_grants.py` read this list. Names are schema-qualified.

Some listed tables do not exist yet (`role`, `currency`, `form_template`, `bridge_session`,
`django_content_type`, the waffle tables and the approval key in `guard`), so a listed table that is
missing is not a failure; an existing table that is not listed is. The waffle names are those of
django-waffle's three models; the PR that installs it (M5) checks them against its migrations.
"""

PROCRASTINATE_TABLES = frozenset(
    {
        "procrastinate_jobs",
        "procrastinate_events",
        "procrastinate_periodic_defers",
        "procrastinate_workers",
    }
)
WAFFLE_TABLES = frozenset({"waffle_flag", "waffle_switch", "waffle_sample"})
GUARD_KEY_TABLES = frozenset({"tenant_mac_key", "approval_mac_key", "lookup_decoy_key"})

GLOBAL_TABLES = frozenset(
    {
        *(
            f"public.{name}"
            for name in (
                "role",
                "currency",
                "form_template",
                "django_session",
                "bridge_session",
                "auth_throttle",
                "security_event",
                "django_migrations",
                "django_content_type",
                *PROCRASTINATE_TABLES,
                *WAFFLE_TABLES,
            )
        ),
        *(f"guard.{name}" for name in GUARD_KEY_TABLES),
    }
)
ROOT_TABLE = "public.agency"

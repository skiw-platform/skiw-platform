from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"

    def ready(self) -> None:
        # One Argon2 hash per process, before any request: the first unknown-email login would
        # otherwise also make the dummy hash and take longer than a known one (plan Risk 2).
        from accounts.auth import passwords

        passwords.warm()

        # The starting-role seed runs in the agency seed transaction (slice spec Decision 5).
        from accounts.access.seed import seed_starting_roles
        from tenancy.seed import add_agency_step

        add_agency_step(seed_starting_roles)

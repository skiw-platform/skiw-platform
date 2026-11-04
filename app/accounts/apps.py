from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"

    def ready(self) -> None:
        # One Argon2 hash per process, before any request: the first unknown-email login would
        # otherwise also make the dummy hash and take longer than a known one (plan Risk 2).
        from accounts.auth import passwords

        passwords.warm()

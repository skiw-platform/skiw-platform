"""The H4 secret inventory (spec §8.4 H4): every file in /etc/skiw/secrets, who reads it, its owner.

Readers are the Compose services that mount the file (infra/host/compose.yml); the owner is the uid
those services run as. A file no service mounts is read on the host by root only. The Compose
config test checks readers and uids against compose.yml.
Open (plan §0 G11): the staging-check mechanism adds one name; it is not fixed yet, so not listed.
"""

from dataclasses import dataclass
from enum import Enum


class Kind(Enum):
    APP_KEY = "app key"  # minted by `bootstrap-secrets init`, escrowed, restored verbatim
    DB_PASSWORD = "db password"  # noqa: S105 - a label. Set by bootstrap-db (M1e), never escrowed
    OWNER_SUPPLIED = "owner supplied"  # placed by the owner (runbook); never minted or escrowed


APP_UID = 10001  # compose.yml: web, worker, migrate
BACKUP_UID = 10003  # compose.yml: backup
DB_UID = 999  # compose.yml: db (postgres)
ROOT_UID = 0

WEB_WORKER = ("web", "worker")
WITH_MIGRATE = ("web", "worker", "migrate")


@dataclass(frozen=True)
class Secret:
    name: str
    kind: Kind
    readers: tuple[str, ...]
    uid: int


INVENTORY: tuple[Secret, ...] = (
    Secret("django_secret_key", Kind.APP_KEY, WITH_MIGRATE, APP_UID),
    Secret("tenant_token_key", Kind.APP_KEY, WITH_MIGRATE, APP_UID),
    Secret("approval_mac_key", Kind.APP_KEY, WITH_MIGRATE, APP_UID),
    Secret("lookup_decoy_key", Kind.APP_KEY, ("migrate",), APP_UID),
    Secret("tenant_source_key", Kind.APP_KEY, WEB_WORKER, APP_UID),
    Secret("login_blob_key", Kind.APP_KEY, WEB_WORKER, APP_UID),
    Secret("audit_mac_key", Kind.APP_KEY, WEB_WORKER, APP_UID),
    Secret("field_kek", Kind.APP_KEY, WEB_WORKER, APP_UID),
    Secret("blind_index_key", Kind.APP_KEY, WEB_WORKER, APP_UID),
    Secret("crm_jar_kek", Kind.APP_KEY, WEB_WORKER, APP_UID),
    Secret("skiw_app_password", Kind.DB_PASSWORD, WEB_WORKER, APP_UID),
    Secret("skiw_migrator_password", Kind.DB_PASSWORD, ("migrate",), APP_UID),
    Secret("skiw_backup_password", Kind.DB_PASSWORD, ("backup",), BACKUP_UID),
    Secret("postgres_password", Kind.DB_PASSWORD, ("db",), DB_UID),
    Secret("skiw_readonly_password", Kind.DB_PASSWORD, (), ROOT_UID),  # socket only (M1e)
    Secret("ghcr_read_token", Kind.OWNER_SUPPLIED, (), ROOT_UID),  # skiw-deploy, as root (M1g)
)
APP_KEYS = tuple(secret.name for secret in INVENTORY if secret.kind is Kind.APP_KEY)
OWNER = {secret.name: secret.uid for secret in INVENTORY}

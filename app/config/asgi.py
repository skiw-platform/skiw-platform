import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()

# Imported after Django is set up. Refuse to serve without a valid tenant_source_key (sessions are
# MAC-verified, plan M2c), login_blob_key (login blobs, plan M3b) or tenant_token_key (with_agency()
# mints under it, plan M4c-4b), the passkey RP ID and origin (plan M3g), or against unapplied
# migrations (spec D16).
from django.conf import settings  # noqa: E402

from accounts.source_key import require_key  # noqa: E402
from jobs.startup import require_migrated  # noqa: E402
from tenancy.binding import require_token_key  # noqa: E402

require_key()
settings.SKIW_LOGIN_BLOB_KEYS()
require_token_key()
settings.SKIW_WEBAUTHN()
require_migrated()

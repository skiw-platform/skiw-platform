import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()

# Imported after Django is set up. Refuse to serve without a valid tenant_source_key (sessions are
# MAC-verified, plan M2c) or against unapplied migrations (spec D16).
from accounts.source_key import require_key  # noqa: E402
from jobs.startup import require_migrated  # noqa: E402

require_key()
require_migrated()

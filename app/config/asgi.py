import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()

# Imported after Django is set up. Refuse to serve against unapplied migrations (spec D16).
from jobs.startup import require_migrated  # noqa: E402

require_migrated()

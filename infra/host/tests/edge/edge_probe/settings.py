"""TEST ONLY: mounted into `web` by `make host-test-live`; not in the app image, never on a host."""

from config.settings import *  # noqa: F403

ROOT_URLCONF = "edge_probe.urls"

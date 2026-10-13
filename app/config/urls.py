from django.urls import path

from health.views import healthz
from jobs.views import readyz
from shell.views import asset, shell

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("readyz", readyz, name="readyz"),
    path("assets/<path:path>", asset, name="asset"),
    path("", shell, name="shell"),
]

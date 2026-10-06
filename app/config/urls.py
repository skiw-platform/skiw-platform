from django.urls import path

from health.views import healthz
from shell.views import asset, shell

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("assets/<path:path>", asset, name="asset"),
    path("", shell, name="shell"),
]

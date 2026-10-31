from config.routes import route
from health.views import healthz
from jobs.views import readyz
from shell.views import asset, shell

urlpatterns = [
    route("healthz", healthz, name="healthz", methods=("GET",), auth="cookie"),
    route("readyz", readyz, name="readyz", methods=("GET",), auth="cookie"),
    route("assets/<path:path>", asset, name="asset", methods=("GET",), auth="cookie"),
    route("", shell, name="shell", methods=("GET",), auth="cookie"),
]

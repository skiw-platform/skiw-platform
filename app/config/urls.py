from accounts.views import (
    enrol_factor_begin,
    enrol_factor_confirm,
    enrol_password,
    login_password,
    login_second_factor,
    logout,
    password,
    stepup,
)
from config.routes import route
from health.views import healthz
from jobs.views import readyz
from shell.views import asset, shell

urlpatterns = [
    route("healthz", healthz, name="healthz", methods=("GET",), auth="cookie"),
    route("readyz", readyz, name="readyz", methods=("GET",), auth="cookie"),
    route("assets/<path:path>", asset, name="asset", methods=("GET",), auth="cookie"),
    route("api/auth/login", login_password, name="auth-login", methods=("POST",), auth="cookie"),
    route(
        "api/auth/second-factor",
        login_second_factor,
        name="auth-second-factor",
        methods=("POST",),
        auth="cookie",
    ),
    route("api/auth/enrol", enrol_password, name="auth-enrol", methods=("POST",), auth="cookie"),
    route(
        "api/auth/enrol/totp",
        enrol_factor_begin,
        name="auth-enrol-totp",
        methods=("POST",),
        auth="cookie",
    ),
    route(
        "api/auth/enrol/totp/confirm",
        enrol_factor_confirm,
        name="auth-enrol-totp-confirm",
        methods=("POST",),
        auth="cookie",
    ),
    route("api/auth/stepup", stepup, name="auth-stepup", methods=("POST",), auth="cookie"),
    route("api/auth/logout", logout, name="auth-logout", methods=("POST",), auth="cookie"),
    route("api/auth/password", password, name="auth-password", methods=("POST",), auth="cookie"),
    route("", shell, name="shell", methods=("GET",), auth="cookie"),
]

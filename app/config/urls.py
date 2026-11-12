from accounts.views import (
    enrol_factor_begin,
    enrol_factor_confirm,
    enrol_password,
    factor_list,
    factor_totp_begin,
    factor_totp_confirm,
    factor_totp_remove,
    login_password,
    login_second_factor,
    logout,
    password,
    recovery_regenerate,
    session_state,
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
    route("api/auth/session", session_state, name="auth-session", methods=("GET",), auth="cookie"),
    route("api/auth/stepup", stepup, name="auth-stepup", methods=("POST",), auth="cookie"),
    route("api/auth/logout", logout, name="auth-logout", methods=("POST",), auth="cookie"),
    route("api/auth/password", password, name="auth-password", methods=("POST",), auth="cookie"),
    route("api/auth/factors", factor_list, name="auth-factors", methods=("GET",), auth="cookie"),
    route(
        "api/auth/factors/totp",
        factor_totp_begin,
        name="auth-factor-totp",
        methods=("POST",),
        auth="cookie",
    ),
    route(
        "api/auth/factors/totp/confirm",
        factor_totp_confirm,
        name="auth-factor-totp-confirm",
        methods=("POST",),
        auth="cookie",
    ),
    route(
        "api/auth/factors/totp/remove",
        factor_totp_remove,
        name="auth-factor-totp-remove",
        methods=("POST",),
        auth="cookie",
    ),
    route(
        "api/auth/factors/recovery",
        recovery_regenerate,
        name="auth-recovery-regenerate",
        methods=("POST",),
        auth="cookie",
    ),
    route("", shell, name="shell", methods=("GET",), auth="cookie"),
    route("enrol", shell, name="shell-enrol", methods=("GET",), auth="cookie"),  # invite links
]

"""The bounded host-config values every settings import needs, for tests that start a subprocess
with a clean environment: session lifetime (spec D6, §8.1; M2b) and the interim auth values
(owner Q6 (a), plan M3b). The same values as .env.example (app/tests/test_env_wiring.py)."""

SESSION = {"SKIW_SESSION_ABSOLUTE_H": "12", "SKIW_SESSION_IDLE_MIN": "30"}
AUTH = {
    "SKIW_ARGON2_MEMORY_KIB": "65536",
    "SKIW_ARGON2_TIME_COST": "3",
    "SKIW_ARGON2_PARALLELISM": "1",
    "SKIW_AUTH_FAILS_PER_ACCOUNT": "5",
    "SKIW_AUTH_FAILS_PER_IP": "20",
    "SKIW_AUTH_WINDOW_MIN": "15",
    "SKIW_AUTH_LOCK_AFTER": "10",
    "SKIW_AUTH_LOCK_MIN": "30",
    "SKIW_STEPUP_MAX_AGE_MIN": "5",
    "SKIW_TOTP_SKEW_STEPS": "1",
    "SKIW_LOGIN_PENDING_MIN": "5",
    "SKIW_ENROL_LINK_MIN": "30",
}
REQUIRED = {**SESSION, **AUTH}
# (low, high) for each auth value, as app/config/settings.py reads them (builder values [A]).
AUTH_BOUNDS = {
    "SKIW_ARGON2_MEMORY_KIB": (19_456, 131_072),
    "SKIW_ARGON2_TIME_COST": (2, 10),
    "SKIW_ARGON2_PARALLELISM": (1, 8),
    "SKIW_AUTH_FAILS_PER_ACCOUNT": (3, 20),
    "SKIW_AUTH_FAILS_PER_IP": (5, 200),
    "SKIW_AUTH_WINDOW_MIN": (1, 1440),
    "SKIW_AUTH_LOCK_AFTER": (3, 50),
    "SKIW_AUTH_LOCK_MIN": (1, 1440),
    "SKIW_STEPUP_MAX_AGE_MIN": (1, 15),
    "SKIW_TOTP_SKEW_STEPS": (0, 2),
    "SKIW_LOGIN_PENDING_MIN": (1, 15),
    "SKIW_ENROL_LINK_MIN": (5, 1440),
}

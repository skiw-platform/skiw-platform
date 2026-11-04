# Fixture for `semgrep --test semgrep/` (rule start-new-lifetime-login-only).


async def banned(request):
    # ruleid: start-new-lifetime-login-only
    request.session.start_new_lifetime()
    # ruleid: start-new-lifetime-login-only
    await request.session.astart_new_lifetime()
    # ruleid: start-new-lifetime-login-only
    getattr(request.session, "start_new_lifetime")()  # noqa: B009 (the evasion under test)
    # ruleid: start-new-lifetime-login-only
    renew = request.session.start_new_lifetime
    renew()
    # ruleid: start-new-lifetime-login-only
    arenew = request.session.astart_new_lifetime
    await arenew()


def allowed(request, user):
    # ok: start-new-lifetime-login-only
    request.session.cycle_key()
    # ok: start-new-lifetime-login-only
    note = "only login() calls start_new_lifetime"
    return note

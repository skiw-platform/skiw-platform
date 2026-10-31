# Fixture for `semgrep --test semgrep/` (rule no-csrf-exempt).
from django.test import Client
from django.views.decorators import csrf
from django.views.decorators.csrf import csrf_exempt


# ruleid: no-csrf-exempt
@csrf_exempt
def a(request):
    return None


# ruleid: no-csrf-exempt
b = csrf.csrf_exempt(a)


def bypass(request, view, SessionAuth):
    # ruleid: no-csrf-exempt
    view.csrf_exempt = True
    # ruleid: no-csrf-exempt
    setattr(view, "csrf_exempt", True)  # noqa: B010 (the rule must catch this spelling)
    # ruleid: no-csrf-exempt
    vars(view).update(csrf_exempt=True)
    # ruleid: no-csrf-exempt
    request.csrf_processing_done = True
    # ruleid: no-csrf-exempt
    request._dont_enforce_csrf_checks = True
    # ruleid: no-csrf-exempt
    request._ninja_csrf_exempt = True
    # ruleid: no-csrf-exempt
    return SessionAuth(csrf=False)


def allowed(view):
    # ok: no-csrf-exempt
    client = Client(enforce_csrf_checks=True)
    # ok: no-csrf-exempt
    vars(view).update(skiw_methods=frozenset({"GET"}), skiw_auth="cookie")
    return client

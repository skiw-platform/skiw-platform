from django.http import HttpRequest, HttpResponse

from jobs.startup import database_ready


# Lives in jobs, beside the startup gate it shares, because jobs is on the TEN-10 list of modules
# that may query the database directly and health must not import jobs (import-linter).
def readyz(request: HttpRequest) -> HttpResponse:
    if database_ready():
        return HttpResponse("ok", content_type="text/plain")
    return HttpResponse("not ready", status=503, content_type="text/plain")

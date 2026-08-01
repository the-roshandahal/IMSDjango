from django.http import HttpResponseServerError
from django.shortcuts import render
from django.template.loader import get_template


def error_400(request, exception=None):
    return render(request, "errors/400.html", status=400)


def error_403(request, exception=None):
    return render(request, "errors/403.html", status=403)


def error_404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    """No RequestContext here on purpose -- if the DB itself is why we're
    here, running context processors (which query notifications etc. for
    an authenticated user) could throw a second exception while trying to
    render the page explaining the first one. Same reasoning as Django's
    own default server_error view."""
    template = get_template("errors/500.html")
    return HttpResponseServerError(template.render({}))

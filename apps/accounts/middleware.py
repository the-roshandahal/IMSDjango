import time

from django.conf import settings
from django.contrib.auth import logout


class InactivityTimeoutMiddleware:
    """Configurable sliding session timeout (SRS Section 5.1). Django's
    SESSION_COOKIE_AGE is an absolute lifetime; this enforces inactivity-based
    expiry on top of it."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            last_activity = request.session.get("last_activity")
            timeout = settings.SESSION_INACTIVITY_TIMEOUT_SECONDS
            now = time.time()
            if last_activity is not None and (now - last_activity) > timeout:
                logout(request)
            else:
                request.session["last_activity"] = now
        return self.get_response(request)

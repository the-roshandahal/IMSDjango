from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class LockoutAwareBackend(ModelBackend):
    """Wraps the stock ModelBackend so account lockout applies to EVERY
    caller of Django's authenticate() -- not just the app's own login page.
    Without this, /admin/ (which authenticates through the stock
    AdminAuthenticationForm) bypassed lockout entirely, since the lockout
    bookkeeping used to live only in apps.accounts.services.check_credentials,
    a function only the app's own LoginPageView ever called. Looks up by
    username OR email since that's what the app's own login form accepts."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        UserModel = get_user_model()
        try:
            user = UserModel._default_manager.get(Q(username__iexact=username) | Q(email__iexact=username))
        except (UserModel.DoesNotExist, UserModel.MultipleObjectsReturned):
            return None

        if user.is_locked:
            return None

        authenticated = super().authenticate(request, username=user.username, password=password, **kwargs)
        if authenticated is None:
            user.register_failed_login()
            return None

        user.reset_lockout()
        return authenticated

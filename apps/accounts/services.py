"""
Deactivation-blocking hook registry (SRS Section 5.1 / Gap #10): user
deactivation must first confirm no assigned equipment/vehicles/open requests
are left dangling. Those modules don't exist yet, so `accounts` exposes a
registration point; future apps call `register_reassignment_check()` from
their AppConfig.ready() and this module needs zero changes when they land.
"""
from collections.abc import Callable

from django.contrib.auth import authenticate, get_user_model
from django.db.models import Q

_reassignment_checks: list[Callable[["User"], list[str]]] = []  # noqa: F821


def register_reassignment_check(fn: Callable[["User"], list[str]]) -> None:  # noqa: F821
    _reassignment_checks.append(fn)


def check_pending_assets(user) -> list[str]:
    """Returns human-readable blockers preventing deactivation. Empty = safe."""
    blockers: list[str] = []
    for check in _reassignment_checks:
        blockers.extend(check(user))
    return blockers


class LoginResult:
    OK = "ok"
    INVALID_CREDENTIALS = "invalid_credentials"
    LOCKED = "locked"
    INACTIVE = "inactive"
    REQUIRES_2FA = "requires_2fa"


def check_credentials(identifier: str, password: str, request=None):
    """Looks up by email OR username, applies lockout, and authenticates.
    Returns (user_or_none, LoginResult code). Increments the failed-attempt
    counter on wrong password (never on lockout/inactive, to avoid extending
    a lockout window on repeated hammering of an already-locked account)."""
    User = get_user_model()
    try:
        user = User.objects.get(Q(email__iexact=identifier) | Q(username__iexact=identifier))
    except User.DoesNotExist:
        return None, LoginResult.INVALID_CREDENTIALS

    if not user.is_active:
        return None, LoginResult.INACTIVE

    if user.is_locked:
        return None, LoginResult.LOCKED

    authenticated = authenticate(request, username=user.username, password=password)
    if authenticated is None:
        user.register_failed_login()
        return None, LoginResult.LOCKED if user.is_locked else LoginResult.INVALID_CREDENTIALS

    user.reset_lockout()

    if user.is_2fa_enabled:
        return user, LoginResult.REQUIRES_2FA
    return user, LoginResult.OK

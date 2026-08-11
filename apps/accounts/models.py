import datetime
import hashlib
import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    """`MANAGEMENT` was removed -- with a single warehouse and one person
    running it, a separate oversight role added nothing that WH_SUPERVISOR
    doesn't already cover, so its capabilities were folded in there.
    `WH_STAFF` stays defined but unused for now -- ready for whenever a
    second warehouse person is hired."""

    ADMIN = "admin", "Administrator"
    WH_SUPERVISOR = "wh_supervisor", "Warehouse Supervisor"
    STATION_SUPERVISOR = "station_supervisor", "Station Supervisor"
    DEEPCLEAN_SUPERVISOR = "deepclean_supervisor", "Deep Clean Supervisor"
    WH_STAFF = "wh_staff", "Warehouse Staff"
    STATION_STAFF = "station_staff", "Station Cleaning Staff"


class User(AbstractUser):
    """SRS Section 5.1 / 1.3. `is_active` (inherited) is the actual login
    gate; `deactivated_at`/`deactivation_reason` are the audit trail for why.
    """

    role = models.CharField(max_length=32, choices=Role.choices, blank=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=32, blank=True)

    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    is_2fa_enabled = models.BooleanField(default=False)

    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivation_reason = models.TextField(blank=True)
    deactivated_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    password_changed_at = models.DateTimeField(null=True, blank=True)

    REQUIRED_FIELDS = ["email"]

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())

    def register_failed_login(self):
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= settings.ACCOUNT_LOCKOUT_THRESHOLD:
            self.locked_until = timezone.now() + timezone.timedelta(
                minutes=settings.ACCOUNT_LOCKOUT_COOLDOWN_MINUTES
            )
        self.save(update_fields=["failed_login_attempts", "locked_until"])

    def reset_lockout(self):
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save(update_fields=["failed_login_attempts", "locked_until"])

    def is_password_expired(self) -> bool:
        if not self.password_changed_at:
            return False
        max_age = timezone.timedelta(days=settings.PASSWORD_MAX_AGE_DAYS)
        return timezone.now() > self.password_changed_at + max_age


class SiteAssignment(models.Model):
    """A user's scope: which specific warehouses/stations they may act on.
    Extended with a `project` FK via an additive migration once the deep
    clean projects module lands — no rework of this model needed.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="site_assignments")
    warehouse = models.ForeignKey(
        "warehouses.Warehouse", null=True, blank=True, on_delete=models.CASCADE, related_name="site_assignments"
    )
    station = models.ForeignKey(
        "warehouses.Station", null=True, blank=True, on_delete=models.CASCADE, related_name="site_assignments"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(warehouse__isnull=False) | models.Q(station__isnull=False),
                name="siteassignment_at_least_one_site",
            )
        ]

    def __str__(self):
        site = self.warehouse or self.station
        return f"{self.user} -> {site}"


class UserCapabilityOverride(models.Model):
    """A per-user exception to their role's default capabilities -- grants
    something the role doesn't normally have, or revokes something it does.
    An explicit override always wins over the role default. `expires_at`
    left blank means it applies until someone removes it by hand; set it
    for "give them this for two weeks" and it just stops applying itself
    once the date passes (checked lazily in has_capability(), no cron
    needed to "turn it off").
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="capability_overrides")
    capability = models.CharField(max_length=64)
    granted = models.BooleanField(help_text="Checked = grant this capability. Unchecked = revoke it, even if the role normally has it.")
    reason = models.CharField(max_length=255, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "capability"], name="uniq_user_capability_override")
        ]
        ordering = ["capability"]

    def __str__(self):
        state = "grant" if self.granted else "revoke"
        return f"{self.user}: {state} {self.capability}"

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at <= timezone.now())


class PasswordResetToken(models.Model):
    """Explicit, time-limited, single-use reset tokens (SRS: 30 minutes).
    Only a hash of the token is stored; the raw token is emailed once and
    never persisted.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reset_tokens")
    token_hash = models.CharField(max_length=128, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    @staticmethod
    def _hash(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    @classmethod
    def issue(cls, user):
        raw_token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timezone.timedelta(minutes=settings.PASSWORD_RESET_TOKEN_TTL_MINUTES)
        token = cls.objects.create(user=user, token_hash=cls._hash(raw_token), expires_at=expires_at)
        return token, raw_token

    @classmethod
    def verify(cls, raw_token: str):
        try:
            token = cls.objects.get(token_hash=cls._hash(raw_token), used_at__isnull=True)
        except cls.DoesNotExist:
            return None
        if token.expires_at < timezone.now():
            return None
        return token

    def mark_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])


class RequestRateLimit(models.Model):
    """Per-IP request counter for auth-adjacent endpoints not otherwise
    covered by DRF's throttle classes (plain Django views: /login/,
    /login/2fa/) -- per-account lockout alone doesn't stop someone cycling
    through many different usernames, and shared cPanel hosting has no
    OS-level rate limiting available (no root, no fail2ban/WAF), so this has
    to live at the application layer. DB-backed rather than Django's cache
    framework specifically so it stays correct if the app ever runs as more
    than one worker process -- a per-process in-memory counter would let an
    attacker multiply their effective rate by the process count."""

    ip_address = models.GenericIPAddressField()
    scope = models.CharField(max_length=32)
    window_start = models.DateTimeField()
    count = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["ip_address", "scope", "window_start"], name="uniq_rate_limit_window")
        ]
        indexes = [models.Index(fields=["window_start"])]

    @classmethod
    def hit(cls, *, ip_address, scope, limit, window_seconds=60) -> bool:
        """Records one request for (ip_address, scope) in the current fixed
        window and returns whether it's still under `limit`. Old windows are
        never read again after they end, so a periodic cleanup (e.g. a cron
        `RequestRateLimit.objects.filter(window_start__lt=...).delete()`)
        is just housekeeping, not correctness-critical."""
        now = timezone.now()
        epoch = int(now.timestamp())
        window_start = timezone.datetime.fromtimestamp(
            epoch - (epoch % window_seconds), tz=datetime.timezone.utc
        )
        obj, created = cls.objects.get_or_create(
            ip_address=ip_address, scope=scope, window_start=window_start, defaults={"count": 1},
        )
        if not created:
            cls.objects.filter(pk=obj.pk).update(count=models.F("count") + 1)
            obj.refresh_from_db(fields=["count"])
        return obj.count <= limit

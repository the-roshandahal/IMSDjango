import hashlib
import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    ADMIN = "admin", "Administrator"
    WH_SUPERVISOR = "wh_supervisor", "Warehouse Supervisor"
    STATION_SUPERVISOR = "station_supervisor", "Station Supervisor"
    DEEPCLEAN_SUPERVISOR = "deepclean_supervisor", "Deep Clean Supervisor"
    WH_STAFF = "wh_staff", "Warehouse Staff"
    STATION_STAFF = "station_staff", "Station Cleaning Staff"
    MANAGEMENT = "management", "Management"


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

import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def _generate_invite_token() -> str:
    return secrets.token_urlsafe(32)


class Employee(models.Model):
    """Company workforce directory -- deliberately separate from `accounts.User`:
    most cleaning staff never log into the system, they're just people whose
    details/compliance (RIW card) and daily work need tracking. A supervisor
    quick-adds name/email/phone; the rest is filled by the employee themself
    via a tokenized self-service link (no login required), and can be
    revisited any time to keep RIW expiry current.
    """

    RIW_EXPIRY_WARNING_DAYS = 30

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=32, blank=True)
    position = models.CharField(max_length=100, blank=True, help_text="e.g. Station Cleaner, Team Leader")
    date_started = models.DateField(null=True, blank=True)

    # Self-service fields -- filled by the employee via the onboarding link.
    dob = models.DateField("Date of birth", null=True, blank=True)
    address = models.TextField(blank=True)
    riw_number = models.CharField("RIW number", max_length=64, blank=True)
    riw_expiry_date = models.DateField("RIW card expiry", null=True, blank=True)
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=32, blank=True)
    emergency_contact_relationship = models.CharField(max_length=80, blank=True)

    notes = models.TextField(blank=True, help_text="Internal notes -- not visible to the employee.")
    is_active = models.BooleanField(default=True)

    invite_token = models.CharField(max_length=64, unique=True, default=_generate_invite_token, editable=False)
    invited_at = models.DateTimeField(null=True, blank=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    profile_completed_at = models.DateTimeField(null=True, blank=True)

    # Most cleaning staff still never need this -- only set when a supervisor
    # explicitly grants clock-in access (see attendance app). Deliberately
    # optional: keeps the directory/self-service onboarding flow above
    # untouched for everyone who doesn't need a login.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="employee_profile"
    )

    # For the shared NFC kiosk: tap the tag, pick your name, enter this PIN --
    # no username/password typing on a shared device. Hashed the same way a
    # password is; blank means kiosk PIN login isn't set up for this employee.
    kiosk_pin_hash = models.CharField(max_length=128, blank=True, editable=False)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def profile_complete(self) -> bool:
        return self.profile_completed_at is not None

    @property
    def has_kiosk_pin(self) -> bool:
        return bool(self.kiosk_pin_hash)

    @property
    def riw_is_expired(self) -> bool:
        return bool(self.riw_expiry_date and self.riw_expiry_date <= timezone.now().date())

    @property
    def riw_is_expiring_soon(self) -> bool:
        if not self.riw_expiry_date or self.riw_is_expired:
            return False
        return (self.riw_expiry_date - timezone.now().date()).days <= self.RIW_EXPIRY_WARNING_DAYS

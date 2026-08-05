import secrets

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.employees.models import Employee, _generate_invite_token


class EmployeeLoginError(Exception):
    """Raised when a login can't be created for an employee (e.g. one already exists)."""


class PinLoginResult:
    OK = "ok"
    INVALID_PIN = "invalid_pin"
    LOCKED = "locked"
    INACTIVE = "inactive"
    NO_PIN_SET = "no_pin_set"


def onboarding_url(request, employee: Employee) -> str:
    from django.urls import reverse

    path = reverse("employees_web:onboard", args=[employee.invite_token])
    return request.build_absolute_uri(path)


def create_employee(*, first_name, last_name, email, phone, created_by, position="", send_invite=True, request=None):
    employee = Employee.objects.create(
        first_name=first_name, last_name=last_name, email=email, phone=phone, position=position,
        created_by=created_by,
    )
    if send_invite and request is not None:
        send_invite_email(employee, request, sent_by=created_by)
    return employee


def send_invite_email(employee: Employee, request, *, sent_by) -> bool:
    """Best-effort email; the caller (view) always has the raw link available
    from onboarding_url() to share manually (SMS/WhatsApp) regardless of
    whether the email actually lands -- most crew won't check inboxes often."""
    employee.invited_at = timezone.now()
    employee.invited_by = sent_by
    employee.save(update_fields=["invited_at", "invited_by"])

    link = onboarding_url(request, employee)
    subject = "Cleantech1 -- complete your employee details"
    message = (
        f"Hi {employee.first_name},\n\n"
        f"Please complete your employee details (date of birth, RIW number and expiry, "
        f"emergency contact) using the link below. It only takes a couple of minutes, "
        f"and you can come back to this same link any time to update your details "
        f"(e.g. after your RIW card is renewed):\n\n{link}\n\nThanks,\nCleantech1"
    )
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [employee.email], fail_silently=False)
        return True
    except Exception:
        return False


def complete_onboarding(*, employee: Employee, dob, address, riw_number, riw_expiry_date,
                         emergency_contact_name, emergency_contact_phone, emergency_contact_relationship):
    employee.dob = dob
    employee.address = address
    employee.riw_number = riw_number
    employee.riw_expiry_date = riw_expiry_date
    employee.emergency_contact_name = emergency_contact_name
    employee.emergency_contact_phone = emergency_contact_phone
    employee.emergency_contact_relationship = emergency_contact_relationship
    if not employee.profile_completed_at:
        employee.profile_completed_at = timezone.now()
    employee.save()
    return employee


def deactivate(employee: Employee):
    employee.is_active = False
    employee.save(update_fields=["is_active"])


def reactivate(employee: Employee):
    employee.is_active = True
    employee.save(update_fields=["is_active"])


def regenerate_invite_token(employee: Employee):
    employee.invite_token = _generate_invite_token()
    employee.save(update_fields=["invite_token"])
    return employee


def create_employee_login(*, employee: Employee, role="station_staff"):
    """One-click "give this employee clock-in access" -- creates a real
    User (reusing the login/password/change-password system already built,
    not a separate auth mechanism) and links it. Returns the temp password
    so the supervisor can pass it on; the employee can change it via the
    existing self-service change-password page."""
    from apps.accounts.models import User

    if employee.user_id:
        raise EmployeeLoginError(f"{employee.full_name} already has a login ({employee.user.username}).")

    if User.objects.filter(email=employee.email).exists():
        raise EmployeeLoginError(
            f"A user account already exists with the email {employee.email} -- link it manually via Django admin, "
            f"or update the employee's email first."
        )

    username = employee.email
    if User.objects.filter(username=username).exists():
        username = f"{employee.email}.{employee.pk}"

    temp_password = secrets.token_urlsafe(9)
    user = User.objects.create_user(
        username=username, email=employee.email, first_name=employee.first_name, last_name=employee.last_name,
        role=role, password=temp_password,
    )
    employee.user = user
    employee.save(update_fields=["user"])
    return user, temp_password


def set_kiosk_pin(*, employee: Employee, pin=None):
    """Generates (or accepts) a 4-digit PIN for kiosk login and hashes it,
    the same way a password is hashed -- the raw PIN is never stored.
    Returns the raw PIN once so the supervisor can pass it on."""
    from django.contrib.auth.hashers import make_password

    if not employee.user_id:
        raise EmployeeLoginError(f"{employee.full_name} needs a login before a kiosk PIN can be set.")

    if pin is None:
        pin = f"{secrets.randbelow(10000):04d}"
    employee.kiosk_pin_hash = make_password(pin)
    employee.save(update_fields=["kiosk_pin_hash"])
    return pin


def verify_kiosk_pin(*, employee: Employee, pin: str) -> str:
    """Same lockout protection as a real password login, reusing the
    linked User's failed_login_attempts/locked_until -- one shared
    lockout regardless of whether a password or a PIN is being guessed.
    Returns a PinLoginResult code, mirroring accounts.services.LoginResult."""
    from django.contrib.auth.hashers import check_password

    if not employee.is_active or not employee.user_id or not employee.user.is_active:
        return PinLoginResult.INACTIVE
    if not employee.has_kiosk_pin:
        return PinLoginResult.NO_PIN_SET
    if employee.user.is_locked:
        return PinLoginResult.LOCKED

    if check_password(pin, employee.kiosk_pin_hash):
        employee.user.reset_lockout()
        return PinLoginResult.OK

    employee.user.register_failed_login()
    return PinLoginResult.LOCKED if employee.user.is_locked else PinLoginResult.INVALID_PIN

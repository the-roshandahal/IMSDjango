from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.employees.models import Employee, _generate_invite_token


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

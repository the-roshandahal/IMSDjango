from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone

from apps.notifications.models import Notification


def notify(*, recipient, type, title, message="", link="", dedupe_key="", dedupe_hours=24):
    """Creates an in-app notification and best-effort emails it. If
    dedupe_key is given, skips creating a new one when an identical
    (recipient, dedupe_key) notification already exists within the last
    dedupe_hours -- keeps a persistently-low stock level or a daily
    periodic check from spamming the same alert over and over."""
    if dedupe_key:
        cutoff = timezone.now() - timedelta(hours=dedupe_hours)
        if Notification.objects.filter(recipient=recipient, dedupe_key=dedupe_key, created_at__gte=cutoff).exists():
            return None

    notification = Notification.objects.create(
        recipient=recipient, type=type, title=title, message=message, link=link, dedupe_key=dedupe_key,
    )
    _send_email(recipient, title, message)
    return notification


def notify_users(users, **kwargs):
    return [n for n in (notify(recipient=u, **kwargs) for u in users) if n is not None]


def _send_email(user, subject, message):
    if not user.email:
        return
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
    except Exception:
        pass  # best-effort -- a broken SMTP config must never break the triggering transaction


def warehouse_recipients(warehouse_id):
    """wh_supervisors assigned to this warehouse, plus admin who sees
    everything regardless of SiteAssignment (wh_supervisor already does
    too via SITE_SCOPE_EXEMPT_ROLES, but role__in below covers any
    wh_supervisor account even without a formal SiteAssignment row)."""
    from apps.accounts.models import Role, SiteAssignment, User

    assigned_ids = SiteAssignment.objects.filter(warehouse_id=warehouse_id, user__role=Role.WH_SUPERVISOR).values_list(
        "user_id", flat=True
    )
    return User.objects.filter(
        Q(id__in=assigned_ids) | Q(role__in=[Role.ADMIN, Role.WH_SUPERVISOR])
    ).filter(is_active=True).distinct()


def station_recipients(station_id):
    from apps.accounts.models import Role, SiteAssignment, User

    assigned_ids = SiteAssignment.objects.filter(station_id=station_id, user__role=Role.STATION_SUPERVISOR).values_list(
        "user_id", flat=True
    )
    return User.objects.filter(
        Q(id__in=assigned_ids) | Q(role__in=[Role.ADMIN, Role.WH_SUPERVISOR])
    ).filter(is_active=True).distinct()


def vehicle_recipients(vehicle_id):
    """The vehicle's own driver (if any), plus fleet managers -- vehicles
    have no SiteAssignment, so scope comes from Vehicle.assigned_driver
    directly instead."""
    from apps.accounts.models import Role, User
    from apps.vehicles.models import Vehicle

    driver_id = Vehicle.objects.filter(pk=vehicle_id).values_list("assigned_driver_id", flat=True).first()
    return User.objects.filter(
        Q(id=driver_id) | Q(role__in=[Role.ADMIN, Role.WH_SUPERVISOR])
    ).filter(is_active=True).distinct()


def admins_and_supervisors():
    from apps.accounts.models import Role, User

    return User.objects.filter(role__in=[Role.ADMIN, Role.WH_SUPERVISOR], is_active=True)


def notify_low_stock(product, quantity, reorder_point, *, warehouse=None, station=None, vehicle=None):
    from django.urls import reverse

    if sum(bool(site) for site in (warehouse, station, vehicle)) != 1:
        raise ValueError("Pass exactly one of warehouse, station, or vehicle.")
    site = warehouse or station or vehicle
    site_name = site.name if (warehouse or station) else site.registration
    if warehouse:
        recipients, dedupe_site = warehouse_recipients(warehouse.pk), f"warehouse:{warehouse.pk}"
    elif station:
        recipients, dedupe_site = station_recipients(station.pk), f"station:{station.pk}"
    else:
        recipients, dedupe_site = vehicle_recipients(vehicle.pk), f"vehicle:{vehicle.pk}"

    title = f"Low stock: {product.name} at {site_name}"
    message = f"{product.name} at {site_name} is at {quantity} (reorder point {reorder_point})."
    link = reverse("catalogue_web:product-detail", args=[product.pk])
    notify_users(
        recipients, type="low_stock", title=title, message=message, link=link,
        dedupe_key=f"low_stock:{product.pk}:{dedupe_site}",
    )

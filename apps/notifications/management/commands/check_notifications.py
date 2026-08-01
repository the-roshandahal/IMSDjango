"""Periodic notification sweep (SRS Section 5.13) for alerts that aren't
tied to a single write -- something becomes true because time passed
(a due date arrives), not because a user took an action. Event-driven
alerts (low stock, PO fully received) fire immediately from their own
service calls instead; this command only covers the date-crossing ones.

No task scheduler (Celery, etc.) exists in this project yet, so this
runs via an external scheduler (cron / Windows Task Scheduler) --
`python manage.py check_notifications`, once a day is enough given the
24h notification dedupe window.
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone


class Command(BaseCommand):
    help = "Sweeps for maintenance/expiry/overdue-request/overdue-PO alerts and creates notifications."

    def handle(self, *args, **options):
        today = timezone.now().date()
        counts = {
            "equipment": self._check_equipment(today),
            "test_tags": self._check_test_tags(today),
            "vehicles": self._check_vehicles(today),
            "expiring_stock": self._check_expiring_stock(today),
            "outstanding_requests": self._check_outstanding_requests(),
            "overdue_pos": self._check_overdue_pos(today),
            "overdue_stocktakes": self._check_overdue_stocktakes(today),
        }
        for label, count in counts.items():
            self.stdout.write(f"{label}: {count} notification(s)")

    def _check_equipment(self, today):
        from django.db.models import Q

        from apps.equipment.models import Equipment
        from apps.notifications.services import admins_and_supervisors, notify_users

        qs = Equipment.objects.filter(
            Q(next_maintenance_due__lte=today) | Q(next_test_due__lte=today) | Q(last_test_result="fail")
        ).exclude(status="written_off")
        sent = 0
        for equipment in qs:
            n = notify_users(
                admins_and_supervisors(), type="maintenance_due", title=f"Equipment due: {equipment.asset_id}",
                message=f"{equipment.name} ({equipment.asset_id}) needs maintenance or a safety test.",
                link=reverse("equipment_web:detail", args=[equipment.pk]),
                dedupe_key=f"maintenance_due:equipment:{equipment.pk}:{today.isoformat()}",
            )
            sent += len(n)
        return sent

    def _check_test_tags(self, today):
        from datetime import timedelta

        from apps.equipment.models import TestTag
        from apps.notifications.services import admins_and_supervisors, notify_users, station_recipients, warehouse_recipients

        horizon = today + timedelta(days=TestTag.EXPIRY_WARNING_DAYS)
        qs = TestTag.objects.filter(expiry_date__lte=horizon).select_related("warehouse", "station")
        sent = 0
        for tag in qs:
            label = "expired" if tag.expiry_date < today else f"expires {tag.expiry_date}"
            if tag.warehouse_id:
                recipients = {u.id: u for u in warehouse_recipients(tag.warehouse_id)}
            elif tag.station_id:
                recipients = {u.id: u for u in station_recipients(tag.station_id)}
            else:
                recipients = {u.id: u for u in admins_and_supervisors()}
            n = notify_users(
                recipients.values(), type="maintenance_due", title=f"Test tag {label}: {tag.name}",
                message=f"{tag.name} at {tag.warehouse or tag.station or 'unassigned location'}, {label}.",
                link=reverse("equipment_web:test-tag-list"),
                dedupe_key=f"test_tag:{tag.pk}:{today.isoformat()}",
            )
            sent += len(n)
        return sent

    def _check_vehicles(self, today):
        from django.db.models import Q

        from apps.notifications.services import admins_and_supervisors, notify_users
        from apps.vehicles.models import Vehicle

        qs = Vehicle.objects.filter(
            Q(service_due_date__lte=today) | Q(insurance_expiry__lte=today)
        ).exclude(status="written_off")
        sent = 0
        for vehicle in qs:
            n = notify_users(
                admins_and_supervisors(), type="vehicle_compliance", title=f"Vehicle compliance: {vehicle.registration}",
                message=f"{vehicle.registration} has a service or insurance date that has passed.",
                link=reverse("vehicles_web:detail", args=[vehicle.pk]),
                dedupe_key=f"vehicle_compliance:vehicle:{vehicle.pk}:{today.isoformat()}",
            )
            sent += len(n)
        return sent

    def _check_expiring_stock(self, today, days_ahead=7):
        from apps.reports.services import inventory_expiry
        from apps.notifications.services import notify_users, warehouse_recipients

        sent = 0
        for row in inventory_expiry(days_ahead=days_ahead):
            batch = row["batch"]
            label = "expired" if row["is_expired"] else f"expires in {row['days_until_expiry']}d"
            n = notify_users(
                warehouse_recipients(batch.warehouse_id), type="expiry",
                title=f"{batch.product.name} ({batch.batch_number}) {label}",
                message=f"{row['on_hand']} on hand at {batch.warehouse.name}, expiry {batch.expiry_date}.",
                link=reverse("catalogue_web:product-detail", args=[batch.product_id]),
                dedupe_key=f"expiry:batch:{batch.pk}:{today.isoformat()}",
            )
            sent += len(n)
        return sent

    def _check_outstanding_requests(self, warn_after_hours=48, escalate_after_hours=96):
        from apps.notifications.services import admins_and_supervisors, notify_users, warehouse_recipients
        from apps.requests.models import StockRequest, StockRequestStatus

        cutoff_warn = timezone.now() - timedelta(hours=warn_after_hours)
        cutoff_escalate = timezone.now() - timedelta(hours=escalate_after_hours)
        qs = StockRequest.objects.filter(
            status=StockRequestStatus.PENDING, requested_at__lte=cutoff_warn
        ).select_related("station", "warehouse")
        sent = 0
        for req in qs:
            link = reverse("stock_requests_web:detail", args=[req.pk])
            n = notify_users(
                warehouse_recipients(req.warehouse_id), type="request_outstanding",
                title=f"Request #{req.pk} still pending", message=f"{req.station.name} -> {req.warehouse.name}, requested {req.requested_at:%d %b}.",
                link=link, dedupe_key=f"request_outstanding:request:{req.pk}:{date.today().isoformat()}",
            )
            sent += len(n)
            if req.requested_at <= cutoff_escalate:
                n2 = notify_users(
                    admins_and_supervisors(), type="request_outstanding", title=f"Escalation: request #{req.pk} unactioned",
                    message=f"Pending since {req.requested_at:%d %b}, over {escalate_after_hours}h with no action.",
                    link=link, dedupe_key=f"request_escalated:request:{req.pk}:{date.today().isoformat()}",
                )
                sent += len(n2)
        return sent

    def _check_overdue_stocktakes(self, today, overdue_after_days=7):
        """Nags whoever's assigned to a station if its weekly stock count
        (SRS-adjacent -- done every Sunday in practice) is more than a week
        stale, or has never been done."""
        from apps.inventory.models import Stocktake
        from apps.notifications.services import notify_users, station_recipients
        from apps.warehouses.models import Station

        cutoff = today - timedelta(days=overdue_after_days)
        sent = 0
        for station in Station.objects.filter(is_active=True):
            last = (
                Stocktake.objects.filter(station=station, status="completed")
                .order_by("-completed_at").first()
            )
            if last and last.completed_at.date() > cutoff:
                continue
            when = f"last done {last.completed_at.date()}" if last else "never done"
            n = notify_users(
                station_recipients(station.id), type="stocktake_overdue",
                title=f"Weekly stock count due: {station.name}",
                message=f"{station.name} hasn't had a stock count in over {overdue_after_days} days ({when}).",
                link=reverse("inventory_web:stocktake-list"),
                dedupe_key=f"stocktake_overdue:station:{station.pk}:{today.isoformat()}",
            )
            sent += len(n)
        return sent

    def _check_overdue_pos(self, today):
        from apps.notifications.services import notify_users, warehouse_recipients
        from apps.purchasing.models import POStatus, PurchaseOrder

        qs = PurchaseOrder.objects.filter(
            status__in=[POStatus.SENT, POStatus.PARTIALLY_RECEIVED], expected_date__lt=today,
        ).select_related("supplier", "created_by")
        sent = 0
        for po in qs:
            recipients = {u.id: u for u in warehouse_recipients(po.warehouse_id)}
            recipients[po.created_by_id] = po.created_by
            n = notify_users(
                recipients.values(), type="po_status", title=f"{po.reference} overdue",
                message=f"Expected {po.expected_date} from {po.supplier.name}, not yet fully received.",
                link=reverse("purchasing_web:detail", args=[po.pk]),
                dedupe_key=f"po_overdue:po:{po.pk}:{today.isoformat()}",
            )
            sent += len(n)
        return sent

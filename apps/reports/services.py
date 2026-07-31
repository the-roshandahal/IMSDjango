"""Read-only aggregation queries for the Reports module (SRS Section 5.12).
On-screen only this pass -- no PDF/Excel export, no scheduled email
delivery (both need libraries/a task scheduler this project doesn't have
yet). Every function returns plain lists/dicts of already-computed values
so templates never do arithmetic.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.catalogue.models import Batch, Product
from apps.equipment.models import Equipment, EquipmentLog
from apps.inventory.models import InventoryTransaction, StockLevel, TransactionType
from apps.projects.models import DeepCleanProject, ProjectStatus
from apps.purchasing.models import POStatus, PurchaseOrder, PurchaseOrderLine
from apps.vehicles.models import Vehicle, VehicleCostLog


def estimate_unit_cost(product_id) -> Decimal | None:
    """No canonical 'cost price' field exists on Product -- suppliers each
    have their own price (apps.suppliers.SupplierProduct) and actual paid
    prices vary PO to PO. Best available estimate, in priority order:
    1) unit price on the most recently *received* PurchaseOrderLine,
    2) the preferred (or cheapest) SupplierProduct price,
    3) None if neither exists yet -- callers must handle that.
    """
    last_line = (
        PurchaseOrderLine.objects.filter(product_id=product_id, quantity_received__gt=0)
        .order_by("-purchase_order__received_at", "-purchase_order__created_at")
        .first()
    )
    if last_line:
        return last_line.unit_price

    from apps.suppliers.models import SupplierProduct

    sp = (
        SupplierProduct.objects.filter(product_id=product_id)
        .order_by("-is_preferred", "unit_price")
        .first()
    )
    return sp.unit_price if sp else None


# ---------------------------------------------------------------- Inventory

def inventory_on_hand(warehouse_ids=None):
    qs = Product.objects.filter(is_archived=False).annotate(
        warehouse_qty=Sum("stock_levels__quantity", filter=Q(stock_levels__warehouse__isnull=False, **(
            {"stock_levels__warehouse_id__in": warehouse_ids} if warehouse_ids is not None else {}
        ))),
        station_qty=Sum("stock_levels__quantity", filter=Q(stock_levels__station__isnull=False)),
        project_qty=Sum("stock_levels__quantity", filter=Q(stock_levels__project__isnull=False)),
    ).order_by("name")
    rows = []
    for p in qs:
        warehouse_qty = p.warehouse_qty or Decimal("0")
        station_qty = p.station_qty or Decimal("0")
        project_qty = p.project_qty or Decimal("0")
        total = warehouse_qty + station_qty + project_qty
        rows.append({
            "product": p, "warehouse_qty": warehouse_qty, "station_qty": station_qty,
            "project_qty": project_qty, "total_qty": total,
            "is_low": total <= p.reorder_point,
        })
    return rows


def inventory_value(warehouse_ids=None):
    rows = inventory_on_hand(warehouse_ids)
    out = []
    grand_total = Decimal("0")
    priced_count = 0
    for row in rows:
        if row["total_qty"] <= 0:
            continue
        cost = estimate_unit_cost(row["product"].id)
        value = (cost * row["total_qty"]) if cost is not None else None
        if value is not None:
            grand_total += value
            priced_count += 1
        out.append({**row, "unit_cost": cost, "value": value})
    return {"rows": out, "grand_total": grand_total, "priced_count": priced_count, "total_count": len(out)}


AGE_BUCKETS = [(0, 30, "0-30 days"), (31, 60, "31-60 days"), (61, 90, "61-90 days"), (91, None, "90+ days")]


def inventory_ageing(warehouse_ids=None):
    today = timezone.now().date()
    qs = Batch.objects.select_related("product", "warehouse").annotate(
        on_hand=Sum("stock_levels__quantity")
    ).filter(on_hand__gt=0)
    if warehouse_ids is not None:
        qs = qs.filter(warehouse_id__in=warehouse_ids)
    buckets = {label: {"batches": [], "total_qty": Decimal("0")} for _, _, label in AGE_BUCKETS}
    for batch in qs:
        age_days = (today - batch.received_at.date()).days
        for lo, hi, label in AGE_BUCKETS:
            if age_days >= lo and (hi is None or age_days <= hi):
                buckets[label]["batches"].append({"batch": batch, "age_days": age_days, "on_hand": batch.on_hand})
                buckets[label]["total_qty"] += batch.on_hand
                break
    return buckets


def inventory_expiry(days_ahead=30, warehouse_ids=None):
    today = timezone.now().date()
    horizon = today + timedelta(days=days_ahead)
    qs = Batch.objects.select_related("product", "warehouse").annotate(
        on_hand=Sum("stock_levels__quantity")
    ).filter(on_hand__gt=0, expiry_date__isnull=False, expiry_date__lte=horizon).order_by("expiry_date")
    if warehouse_ids is not None:
        qs = qs.filter(warehouse_id__in=warehouse_ids)
    rows = []
    for batch in qs:
        rows.append({
            "batch": batch, "on_hand": batch.on_hand,
            "is_expired": batch.expiry_date < today,
            "days_until_expiry": (batch.expiry_date - today).days,
        })
    return rows


# -------------------------------------------------------------- Consumption

def consumption_report(date_from, date_to, warehouse_ids=None, station_ids=None, project_ids=None):
    """'Consumption' = stock issued out to a station/project, or recorded
    directly as station usage -- a dispatch is counted even if some of it
    sits unused on a shelf; that's the practical proxy this system can
    measure without a separate 'used' event."""
    qs = InventoryTransaction.objects.filter(
        type__in=[TransactionType.STOCK_OUT, TransactionType.STATION_USAGE],
        timestamp__date__gte=date_from, timestamp__date__lte=date_to,
    ).filter(Q(station__isnull=False) | Q(project__isnull=False))
    if warehouse_ids is not None:
        qs = qs.filter(source_warehouse_id__in=warehouse_ids)
    if station_ids is not None:
        qs = qs.filter(station_id__in=station_ids)
    if project_ids is not None:
        qs = qs.filter(project_id__in=project_ids)

    by_station = (
        qs.filter(station__isnull=False).values("station__name").annotate(total=Sum("quantity"), lines=Count("id"))
        .order_by("-total")
    )
    by_project = (
        qs.filter(project__isnull=False).values("project__reference", "project__name")
        .annotate(total=Sum("quantity"), lines=Count("id")).order_by("-total")
    )
    by_product = (
        qs.values("product__name").annotate(total=Sum("quantity"), lines=Count("id")).order_by("-total")[:25]
    )
    return {"by_station": by_station, "by_project": by_project, "by_product": by_product}


# --------------------------------------------------------------- Equipment

def equipment_report(date_from, date_to):
    status_breakdown = Equipment.objects.values("status").annotate(count=Count("id")).order_by("-count")
    maintenance_events = (
        EquipmentLog.objects.filter(
            action__in=["maintenance_start", "maintenance_end"],
            timestamp__date__gte=date_from, timestamp__date__lte=date_to,
        ).select_related("equipment").order_by("-timestamp")
    )
    assignment_events = (
        EquipmentLog.objects.filter(
            action="assigned", timestamp__date__gte=date_from, timestamp__date__lte=date_to,
        ).values("equipment__asset_id", "equipment__name").annotate(times_assigned=Count("id")).order_by("-times_assigned")
    )
    return {
        "status_breakdown": status_breakdown, "maintenance_events": maintenance_events,
        "assignment_events": assignment_events,
    }


# ---------------------------------------------------------------- Projects

def project_report(status=None, project_ids=None):
    qs = DeepCleanProject.objects.select_related("station", "supervisor")
    if status:
        qs = qs.filter(status=status)
    if project_ids is not None:
        qs = qs.filter(pk__in=project_ids)

    rows = []
    for project in qs.order_by("-start_date"):
        chemical_cost = Decimal("0")
        for sl in StockLevel.objects.filter(project=project).select_related("product"):
            cost = estimate_unit_cost(sl.product_id)
            if cost is not None:
                chemical_cost += cost * sl.quantity
        vehicle_cost = VehicleCostLog.objects.filter(project=project).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        if project.status == ProjectStatus.COMPLETED:
            timeline = "on time" if (not project.end_date or (project.closed_at and project.closed_at.date() <= project.end_date)) else "late"
        elif project.end_date and timezone.now().date() > project.end_date:
            timeline = "overdue"
        else:
            timeline = "in progress"

        from apps.projects.services import outstanding_assets
        rows.append({
            "project": project, "chemical_cost": chemical_cost, "vehicle_cost": vehicle_cost,
            "total_cost": chemical_cost + vehicle_cost, "timeline": timeline,
            "outstanding": outstanding_assets(project) if project.status != ProjectStatus.COMPLETED else [],
        })
    return rows


# ------------------------------------------------------- Purchasing/Supplier

def purchasing_report(date_from, date_to, supplier_ids=None, warehouse_ids=None):
    qs = PurchaseOrder.objects.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)
    if supplier_ids is not None:
        qs = qs.filter(supplier_id__in=supplier_ids)
    if warehouse_ids is not None:
        qs = qs.filter(warehouse_id__in=warehouse_ids)
    qs = qs.select_related("supplier").prefetch_related("lines")

    spend_by_supplier = {}
    lead_times = {}
    on_time_counts = {}
    for po in qs:
        name = po.supplier.name
        spend_by_supplier.setdefault(name, Decimal("0"))
        spend_by_supplier[name] += po.total_value
        if po.received_at:
            lead_days = (po.received_at.date() - po.created_at.date()).days
            lead_times.setdefault(name, []).append(lead_days)
            if po.expected_date:
                on_time_counts.setdefault(name, {"on_time": 0, "total": 0})
                on_time_counts[name]["total"] += 1
                if po.received_at.date() <= po.expected_date:
                    on_time_counts[name]["on_time"] += 1

    rows = []
    for name, spend in sorted(spend_by_supplier.items(), key=lambda kv: -kv[1]):
        lts = lead_times.get(name, [])
        avg_lead = round(sum(lts) / len(lts), 1) if lts else None
        otc = on_time_counts.get(name)
        on_time_rate = round(100 * otc["on_time"] / otc["total"], 0) if otc and otc["total"] else None
        rows.append({"supplier": name, "spend": spend, "avg_lead_days": avg_lead, "on_time_rate": on_time_rate})

    status_counts = qs.values("status").annotate(count=Count("id")).order_by("-count")
    return {"rows": rows, "status_counts": status_counts}


# ------------------------------------------------------------------ Vehicles

def vehicle_report(date_from, date_to):
    cost_qs = VehicleCostLog.objects.filter(incurred_at__gte=date_from, incurred_at__lte=date_to)
    by_vehicle = (
        cost_qs.values("vehicle__registration").annotate(total=Sum("amount"), entries=Count("id")).order_by("-total")
    )
    by_type = cost_qs.values("cost_type").annotate(total=Sum("amount")).order_by("-total")

    compliance_issues = []
    for v in Vehicle.objects.all():
        if v.is_service_due or v.is_insurance_expired:
            compliance_issues.append({
                "vehicle": v, "service_due": v.is_service_due, "insurance_expired": v.is_insurance_expired,
            })
    return {"by_vehicle": by_vehicle, "by_type": by_type, "compliance_issues": compliance_issues}


# --------------------------------------------------------------- Audit / users

def audit_report(date_from, date_to):
    qs = AuditLog.objects.filter(timestamp__date__gte=date_from, timestamp__date__lte=date_to)
    by_actor = qs.exclude(actor__isnull=True).values("actor__username").annotate(count=Count("id")).order_by("-count")[:25]
    by_action = qs.values("action").annotate(count=Count("id")).order_by("-count")[:25]
    return {"total": qs.count(), "by_actor": by_actor, "by_action": by_action}

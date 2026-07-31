from django.db import transaction
from django.utils import timezone

from apps.inventory import services as inventory_services
from apps.inventory.exceptions import InsufficientStockError, StockLevelChangedError
from apps.requests.models import StockRequest, StockRequestLine, StockRequestStatus


class RequestNotApprovedError(Exception):
    """Stock cannot be dispatched against a request that has not been
    approved (SRS Section 5.4 business rule)."""


@transaction.atomic
def create_request(*, station_id, warehouse_id, requested_by, lines):
    """`lines` is a list of {"product_id": int, "quantity": Decimal}."""
    if not lines:
        raise ValueError("A stock request needs at least one line.")
    req = StockRequest.objects.create(station_id=station_id, warehouse_id=warehouse_id, requested_by=requested_by)
    StockRequestLine.objects.bulk_create(
        [
            StockRequestLine(request=req, product_id=line["product_id"], quantity_requested=line["quantity"])
            for line in lines
        ]
    )
    return req


@transaction.atomic
def approve_request(*, request_id, approved_by):
    updated = StockRequest.objects.filter(pk=request_id, status=StockRequestStatus.PENDING).update(
        status=StockRequestStatus.APPROVED, approved_by=approved_by, decided_at=timezone.now()
    )
    if updated == 0:
        raise ValueError("Request not found, or not pending.")
    return StockRequest.objects.get(pk=request_id)


@transaction.atomic
def reject_request(*, request_id, approved_by, reason):
    if not reason:
        raise ValueError("Rejection requires a reason.")
    updated = StockRequest.objects.filter(pk=request_id, status=StockRequestStatus.PENDING).update(
        status=StockRequestStatus.REJECTED, approved_by=approved_by, rejection_reason=reason, decided_at=timezone.now()
    )
    if updated == 0:
        raise ValueError("Request not found, or not pending.")
    return StockRequest.objects.get(pk=request_id)


@transaction.atomic
def dispatch_request(*, request_id, dispatched_by):
    """Issues stock for every not-yet-fully-dispatched line, station-bound,
    linked back to this request. Each line either dispatches in full or is
    skipped as a shortfall -- no partial-line dispatch -- so a line's
    quantity_dispatched is always either 0 or fully requested.
    """
    req = StockRequest.objects.select_related("station", "warehouse").get(pk=request_id)
    if req.status not in (StockRequestStatus.APPROVED, StockRequestStatus.PARTIALLY_FULFILLED):
        raise RequestNotApprovedError("Stock cannot be dispatched against a request that has not been approved.")

    any_shortfall = False
    for line in req.lines.all():
        remaining = line.quantity_requested - line.quantity_dispatched
        if remaining <= 0:
            continue
        try:
            inventory_services.stock_out(
                product_id=line.product_id, warehouse_id=req.warehouse_id, quantity=remaining,
                performed_by=dispatched_by, station_id=req.station_id, request_id=req.pk,
                reason_code="stock_request", comment=f"Dispatch for request #{req.pk}",
            )
        except (InsufficientStockError, StockLevelChangedError):
            any_shortfall = True
            continue
        line.quantity_dispatched = line.quantity_requested
        line.save(update_fields=["quantity_dispatched"])

    lines = list(req.lines.all())
    if all(line.quantity_dispatched >= line.quantity_requested for line in lines):
        req.status = StockRequestStatus.FULFILLED
    elif any(line.quantity_dispatched > 0 for line in lines):
        req.status = StockRequestStatus.PARTIALLY_FULFILLED
    else:
        req.status = StockRequestStatus.APPROVED
    req.save(update_fields=["status"])
    return req, any_shortfall

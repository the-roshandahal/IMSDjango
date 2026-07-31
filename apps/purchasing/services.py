from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.inventory import services as inventory_services
from apps.purchasing.models import POStatus, PurchaseOrder, PurchaseOrderLine


class LineChangedError(Exception):
    """Optimistic-concurrency retry signal, same shape as the inventory
    app's StockLevelChangedError -- the line was received against by
    another request between page load and submit."""


def provision_reference(po: PurchaseOrder) -> None:
    """Called once, right after creation (mirrors apps.catalogue.services
    .provision_codes) -- replaces the temporary placeholder with a real,
    human-readable, sequential reference."""
    po.reference = f"PO-{po.pk:05d}"
    po.save(update_fields=["reference"])


def create_purchase_order(*, supplier_id, warehouse_id, expected_date, notes, created_by, lines):
    """`lines` is a list of {"product_id": int, "quantity": Decimal, "unit_price": Decimal}."""
    if not lines:
        raise ValueError("A purchase order needs at least one line.")
    po = PurchaseOrder.objects.create(
        supplier_id=supplier_id, warehouse_id=warehouse_id, expected_date=expected_date, notes=notes,
        created_by=created_by,
    )
    provision_reference(po)
    PurchaseOrderLine.objects.bulk_create(
        [
            PurchaseOrderLine(
                purchase_order=po, product_id=line["product_id"], quantity_ordered=line["quantity"],
                unit_price=line["unit_price"],
            )
            for line in lines
        ]
    )
    return po


def send(*, po_id, performed_by):
    updated = PurchaseOrder.objects.filter(pk=po_id, status=POStatus.DRAFT).update(
        status=POStatus.SENT, sent_at=timezone.now()
    )
    if updated == 0:
        raise ValueError("Only a draft purchase order can be sent.")


def cancel(*, po_id, performed_by, reason):
    if not reason:
        raise ValueError("A cancellation reason is required.")
    updated = (
        PurchaseOrder.objects.filter(pk=po_id)
        .exclude(status__in=[POStatus.RECEIVED, POStatus.CANCELLED])
        .update(status=POStatus.CANCELLED, cancelled_at=timezone.now(), cancelled_by=performed_by, cancel_reason=reason)
    )
    if updated == 0:
        raise ValueError("This purchase order can no longer be cancelled.")


@transaction.atomic
def receive_line(*, line_id, quantity, performed_by):
    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise ValueError("quantity must be positive.")

    line = PurchaseOrderLine.objects.select_related("purchase_order", "product").get(pk=line_id)
    po = line.purchase_order
    if not po.is_open_for_receiving:
        raise ValueError("This purchase order is not open for receiving.")
    if quantity > line.quantity_remaining:
        raise ValueError(f"Cannot receive {quantity}; only {line.quantity_remaining} remaining on this line.")

    updated = PurchaseOrderLine.objects.filter(pk=line_id, quantity_received=line.quantity_received).update(
        quantity_received=F("quantity_received") + quantity
    )
    if updated == 0:
        raise LineChangedError("This line changed since the page loaded; please retry.")

    inventory_services.stock_in(
        product_id=line.product_id, warehouse_id=po.warehouse_id, quantity=quantity, performed_by=performed_by,
        reason_code="po_receipt", comment=f"Received against {po.reference}", purchase_order_id=po.pk,
    )
    _refresh_status(po.pk)


def _refresh_status(po_id):
    lines = list(PurchaseOrderLine.objects.filter(purchase_order_id=po_id))
    if all(line.is_fully_received for line in lines):
        new_status = POStatus.RECEIVED
        PurchaseOrder.objects.filter(pk=po_id).exclude(status=new_status).update(
            status=new_status, received_at=timezone.now()
        )
        return
    elif any(line.quantity_received > 0 for line in lines):
        new_status = POStatus.PARTIALLY_RECEIVED
    else:
        return
    PurchaseOrder.objects.filter(pk=po_id).exclude(status=new_status).update(status=new_status)

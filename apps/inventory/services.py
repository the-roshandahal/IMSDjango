"""
Concurrency-safe stock operations (SRS Section 5.4, Gap #1).

The whole concurrency guarantee comes from ONE pattern, used everywhere a
balance is decremented:

    updated = StockLevel.objects.filter(pk=X, quantity__gte=take).update(
        quantity=F("quantity") - take
    )
    if updated == 0:
        raise StockLevelChangedError(...)

This is an atomic conditional UPDATE: the WHERE clause is re-evaluated by
the database against the live row at write time, so two concurrent callers
racing for the last unit can never both succeed -- exactly one UPDATE
matches a row, the other matches zero rows and raises. This works
identically on SQLite and PostgreSQL and does NOT depend on
`select_for_update()` / row locks, which SQLite doesn't meaningfully
support. Every function below is wrapped in `transaction.atomic()` so a
multi-batch operation never partially commits.
"""
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F, Sum
from django.utils import timezone

from apps.catalogue.models import Batch, Product
from apps.catalogue.signals import low_stock_signal
from apps.inventory.exceptions import ApprovalRequiredError, InsufficientStockError, StockLevelChangedError
from apps.inventory.models import InventoryTransaction, StockLevel, Transfer, TransactionType
from apps.warehouses.models import Warehouse


def _get_or_create_stock_level(*, product, warehouse_id=None, station_id=None, batch=None) -> StockLevel:
    filters = dict(product=product, warehouse_id=warehouse_id, station_id=station_id, batch=batch)
    try:
        with transaction.atomic():
            level, _ = StockLevel.objects.get_or_create(defaults={"quantity": Decimal("0")}, **filters)
    except IntegrityError:
        level = StockLevel.objects.get(**filters)
    return level


def _fefo_plan(product: Product, warehouse: Warehouse, quantity: Decimal):
    """Greedy First-Expired-First-Out batch selection. This read is
    intentionally NOT locked -- it only decides which batches to *try*; the
    actual safety guarantee comes from the conditional UPDATE each batch
    goes through afterwards. A stale read here just means a slightly
    suboptimal (never unsafe) batch choice under real contention."""
    if not product.is_batch_tracked:
        # Cap the plan at the last-known balance so a request that's simply
        # too large (no batches, nothing to race against) is correctly
        # classified as InsufficientStockError rather than reaching the
        # conditional UPDATE and being misread as a concurrency conflict.
        level = StockLevel.objects.filter(product=product, warehouse=warehouse, station=None, batch=None).first()
        available = level.quantity if level else Decimal("0")
        return [(None, min(available, quantity))] if available > 0 else []

    plan = []
    remaining = quantity
    batches = Batch.objects.filter(product=product, warehouse=warehouse).order_by(
        F("expiry_date").asc(nulls_last=True)
    )
    levels_by_batch = {
        level.batch_id: level.quantity
        for level in StockLevel.objects.filter(product=product, warehouse=warehouse, station=None, batch__in=batches)
    }
    for batch in batches:
        if remaining <= 0:
            break
        available = levels_by_batch.get(batch.pk, Decimal("0"))
        if available <= 0:
            continue
        take = min(available, remaining)
        plan.append((batch, take))
        remaining -= take
    return plan


def _maybe_fire_low_stock(product: Product, warehouse: Warehouse):
    total = (
        StockLevel.objects.filter(product=product, warehouse=warehouse, station=None).aggregate(total=Sum("quantity"))[
            "total"
        ]
        or Decimal("0")
    )
    if total <= product.reorder_point:
        low_stock_signal.send(sender=Product, product=product, warehouse_id=warehouse.pk, quantity=total)


@transaction.atomic
def stock_in(*, product_id, warehouse_id, quantity, performed_by, batch_id=None, reason_code="", comment=""):
    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise ValueError("quantity must be positive.")

    product = Product.objects.get(pk=product_id)
    warehouse = Warehouse.objects.get(pk=warehouse_id)
    batch = Batch.objects.get(pk=batch_id) if batch_id else None

    level = _get_or_create_stock_level(product=product, warehouse_id=warehouse_id, batch=batch)
    StockLevel.objects.filter(pk=level.pk).update(quantity=F("quantity") + quantity)

    return InventoryTransaction.objects.create(
        type=TransactionType.STOCK_IN, product=product, batch=batch, quantity=quantity,
        dest_warehouse=warehouse, reason_code=reason_code, comment=comment, performed_by=performed_by,
    )


@transaction.atomic
def stock_out(
    *, product_id, warehouse_id, quantity, performed_by, station_id=None,
    reason_code="", comment="", batch_id=None, override_fefo=False,
):
    """Debits warehouse stock. If `station_id` is given, the same quantity
    is credited to that station's stock in the same atomic operation
    (issued-to-station); otherwise this is a write-off/consumption with no
    destination stock. Defaults to FEFO for batch-tracked products; passing
    `batch_id` requires `override_fefo=True` and should carry a
    `reason_code` (Supervisor override, SRS Section 5.4).
    """
    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise ValueError("quantity must be positive.")

    product = Product.objects.get(pk=product_id)
    warehouse = Warehouse.objects.get(pk=warehouse_id)

    if batch_id is not None:
        if not override_fefo:
            raise ValueError("Selecting a specific batch requires override_fefo=True (and a reason_code).")
        batch = Batch.objects.get(pk=batch_id, product_id=product_id, warehouse_id=warehouse_id)
        plan = [(batch, quantity)]
    else:
        plan = _fefo_plan(product, warehouse, quantity)

    if sum((take for _, take in plan), Decimal("0")) < quantity:
        raise InsufficientStockError(
            f"Insufficient stock for product {product_id} at warehouse {warehouse_id}: requested {quantity}."
        )

    consumed = []
    for batch, take_qty in plan:
        updated = StockLevel.objects.filter(
            product=product, warehouse=warehouse, station=None, batch=batch, quantity__gte=take_qty
        ).update(quantity=F("quantity") - take_qty)
        if updated == 0:
            raise StockLevelChangedError(
                f"Stock level for product {product_id} (batch {batch}) changed, please retry."
            )
        consumed.append((batch, take_qty))

    txns = []
    for batch, take_qty in consumed:
        txn = InventoryTransaction.objects.create(
            type=TransactionType.STOCK_OUT, product=product, batch=batch, quantity=take_qty,
            source_warehouse=warehouse, station_id=station_id, reason_code=reason_code,
            comment=comment, performed_by=performed_by,
        )
        txns.append(txn)

        if station_id is not None:
            station_level = _get_or_create_stock_level(product=product, station_id=station_id, batch=batch)
            StockLevel.objects.filter(pk=station_level.pk).update(quantity=F("quantity") + take_qty)

    _maybe_fire_low_stock(product, warehouse)
    return txns


@transaction.atomic
def transfer_initiate(
    *, product_id, quantity, source_warehouse_id, initiated_by,
    dest_warehouse_id=None, dest_station_id=None, batch_id=None, reason_code="", comment="",
):
    """Warehouse-to-warehouse (or warehouse-to-station) transfer, phase 1:
    debit the source immediately via the standard stock_out mechanism.
    Warehouse-to-warehouse transfers stay 'in_transit' until the receiving
    warehouse calls transfer_confirm_receipt (SRS Section 5.5). A transfer
    straight to a station completes immediately (mirrors stock_out's
    issued-to-station credit) since no external handoff confirmation is
    required for that case.
    """
    if not dest_warehouse_id and not dest_station_id:
        raise ValueError("A transfer needs a destination warehouse or station.")

    debit_txns = stock_out(
        product_id=product_id, warehouse_id=source_warehouse_id, quantity=quantity,
        performed_by=initiated_by, station_id=dest_station_id, reason_code=reason_code or "transfer",
        comment=comment, batch_id=batch_id, override_fefo=bool(batch_id),
    )
    debit_txn = debit_txns[0]  # single-batch transfers only for now; multi-batch = multiple Transfer rows later

    status = "completed" if dest_station_id else "in_transit"
    transfer = Transfer.objects.create(
        product_id=product_id, quantity=Decimal(str(quantity)), source_warehouse_id=source_warehouse_id,
        dest_warehouse_id=dest_warehouse_id, dest_station_id=dest_station_id,
        debit_txn=debit_txn, initiated_by=initiated_by, status=status,
        confirmed_at=timezone.now() if status == "completed" else None,
    )
    return transfer


@transaction.atomic
def transfer_confirm_receipt(*, transfer_id, confirmed_by):
    now = timezone.now()
    updated = Transfer.objects.filter(pk=transfer_id, status="in_transit").update(
        status="completed", confirmed_by=confirmed_by, confirmed_at=now
    )
    if updated == 0:
        raise ValueError("Transfer not found, or already confirmed/completed.")

    transfer = Transfer.objects.select_related("product", "dest_warehouse", "dest_station", "debit_txn").get(
        pk=transfer_id
    )

    level = _get_or_create_stock_level(
        product=transfer.product, warehouse_id=transfer.dest_warehouse_id,
        station_id=transfer.dest_station_id, batch=transfer.debit_txn.batch,
    )
    StockLevel.objects.filter(pk=level.pk).update(quantity=F("quantity") + transfer.quantity)

    credit_txn = InventoryTransaction.objects.create(
        type=TransactionType.TRANSFER_IN, product=transfer.product, batch=transfer.debit_txn.batch,
        quantity=transfer.quantity, dest_warehouse=transfer.dest_warehouse, station=transfer.dest_station,
        performed_by=confirmed_by, comment=f"Transfer #{transfer.pk} receipt confirmed",
    )
    transfer.credit_txn = credit_txn
    transfer.save(update_fields=["credit_txn"])
    return transfer


@transaction.atomic
def adjustment(*, product_id, warehouse_id, quantity_delta, performed_by, reason_code, comment="", batch_id=None):
    """`quantity_delta` may be positive or negative. `reason_code` is
    mandatory (SRS Section 5.4)."""
    if not reason_code:
        raise ValueError("Stock adjustments require a reason_code.")

    quantity_delta = Decimal(str(quantity_delta))
    product = Product.objects.get(pk=product_id)
    warehouse = Warehouse.objects.get(pk=warehouse_id)
    batch = Batch.objects.get(pk=batch_id) if batch_id else None

    if quantity_delta < 0:
        updated = StockLevel.objects.filter(
            product=product, warehouse=warehouse, station=None, batch=batch, quantity__gte=-quantity_delta
        ).update(quantity=F("quantity") + quantity_delta)
        if updated == 0:
            raise StockLevelChangedError("Stock level changed; please retry the adjustment.")
    else:
        level = _get_or_create_stock_level(product=product, warehouse_id=warehouse_id, batch=batch)
        StockLevel.objects.filter(pk=level.pk).update(quantity=F("quantity") + quantity_delta)

    txn = InventoryTransaction.objects.create(
        type=TransactionType.ADJUSTMENT, product=product, batch=batch, quantity=abs(quantity_delta),
        source_warehouse=warehouse if quantity_delta < 0 else None,
        dest_warehouse=warehouse if quantity_delta >= 0 else None,
        reason_code=reason_code, comment=comment, performed_by=performed_by,
    )
    if quantity_delta < 0:
        _maybe_fire_low_stock(product, warehouse)
    return txn


@transaction.atomic
def return_stock(
    *, product_id, warehouse_id, quantity, performed_by, station_id=None, reason_code="", comment="", batch_id=None
):
    """Returns from a station/project back to a warehouse."""
    quantity = Decimal(str(quantity))
    product = Product.objects.get(pk=product_id)
    warehouse = Warehouse.objects.get(pk=warehouse_id)
    batch = Batch.objects.get(pk=batch_id) if batch_id else None

    if station_id is not None:
        updated = StockLevel.objects.filter(
            product=product, station_id=station_id, warehouse=None, batch=batch, quantity__gte=quantity
        ).update(quantity=F("quantity") - quantity)
        if updated == 0:
            raise StockLevelChangedError("Station stock level changed; please retry the return.")

    level = _get_or_create_stock_level(product=product, warehouse_id=warehouse_id, batch=batch)
    StockLevel.objects.filter(pk=level.pk).update(quantity=F("quantity") + quantity)

    return InventoryTransaction.objects.create(
        type=TransactionType.RETURN, product=product, batch=batch, quantity=quantity,
        dest_warehouse=warehouse, station_id=station_id, reason_code=reason_code,
        comment=comment, performed_by=performed_by,
    )


def _write_off(
    *, product_id, warehouse_id, quantity, performed_by, txn_type,
    comment="", batch_id=None, approved_by=None, photo=None, reason_code="",
):
    quantity = Decimal(str(quantity))
    product = Product.objects.get(pk=product_id)
    warehouse = Warehouse.objects.get(pk=warehouse_id)
    batch = Batch.objects.get(pk=batch_id) if batch_id else None

    updated = StockLevel.objects.filter(
        product=product, warehouse=warehouse, station=None, batch=batch, quantity__gte=quantity
    ).update(quantity=F("quantity") - quantity)
    if updated == 0:
        raise StockLevelChangedError(f"Stock level changed; please retry recording this {txn_type}.")

    txn = InventoryTransaction.objects.create(
        type=txn_type, product=product, batch=batch, quantity=quantity, source_warehouse=warehouse,
        reason_code=reason_code, comment=comment, performed_by=performed_by, approved_by=approved_by, photo=photo,
    )
    _maybe_fire_low_stock(product, warehouse)
    return txn


@transaction.atomic
def record_damaged(*, product_id, warehouse_id, quantity, performed_by, comment="", batch_id=None, photo=None):
    return _write_off(
        product_id=product_id, warehouse_id=warehouse_id, quantity=quantity, performed_by=performed_by,
        txn_type=TransactionType.DAMAGED, comment=comment, batch_id=batch_id, photo=photo,
    )


@transaction.atomic
def record_lost(*, product_id, warehouse_id, quantity, performed_by, approved_by, comment="", batch_id=None):
    if approved_by is None:
        raise ApprovalRequiredError("Recording lost stock requires Supervisor sign-off.")
    return _write_off(
        product_id=product_id, warehouse_id=warehouse_id, quantity=quantity, performed_by=performed_by,
        txn_type=TransactionType.LOST, comment=comment, batch_id=batch_id, approved_by=approved_by,
    )


@transaction.atomic
def record_expired(*, product_id, warehouse_id, quantity, performed_by, batch_id, comment=""):
    return _write_off(
        product_id=product_id, warehouse_id=warehouse_id, quantity=quantity, performed_by=performed_by,
        txn_type=TransactionType.EXPIRED, comment=comment, batch_id=batch_id,
    )


@transaction.atomic
def reverse_transaction(*, transaction_id, performed_by, reason):
    """Corrections never edit history -- they post a new REVERSAL record
    with the inverse StockLevel effect (SRS Section 5.4)."""
    original = InventoryTransaction.objects.select_related("product", "batch", "source_warehouse", "dest_warehouse").get(
        pk=transaction_id
    )
    if original.type == TransactionType.REVERSAL:
        raise ValueError("Cannot reverse a reversal.")

    if original.source_warehouse_id and not original.dest_warehouse_id:
        # Original decreased stock at source_warehouse -> reversal increases it back.
        level = _get_or_create_stock_level(
            product=original.product, warehouse_id=original.source_warehouse_id, batch=original.batch
        )
        StockLevel.objects.filter(pk=level.pk).update(quantity=F("quantity") + original.quantity)
        reversal_source, reversal_dest = None, original.source_warehouse
    elif original.dest_warehouse_id:
        # Original increased stock at dest_warehouse -> reversal decreases it.
        updated = StockLevel.objects.filter(
            product=original.product, warehouse=original.dest_warehouse, station=None, batch=original.batch,
            quantity__gte=original.quantity,
        ).update(quantity=F("quantity") - original.quantity)
        if updated == 0:
            raise StockLevelChangedError("Cannot reverse: insufficient stock remains to reverse this increase.")
        reversal_source, reversal_dest = original.dest_warehouse, None
    else:
        raise ValueError("Cannot determine reversal direction for this transaction.")

    return InventoryTransaction.objects.create(
        type=TransactionType.REVERSAL, product=original.product, batch=original.batch, quantity=original.quantity,
        source_warehouse=reversal_source, dest_warehouse=reversal_dest, station=original.station,
        reason_code="reversal", comment=reason, reversal_of=original, performed_by=performed_by,
    )

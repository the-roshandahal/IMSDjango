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
from django.db.models import F, Q, Sum
from django.utils import timezone

from apps.catalogue.models import Batch, Product
from apps.catalogue.signals import low_stock_signal
from apps.inventory.exceptions import ApprovalRequiredError, InsufficientStockError, StockLevelChangedError
from apps.inventory.models import (
    InventoryTransaction, ProductStockThreshold, StockLevel, Stocktake, StocktakeLine, Transfer, TransactionType,
)
from apps.vehicles.models import Vehicle
from apps.warehouses.models import Station, Warehouse


def _get_or_create_stock_level(
    *, product, warehouse_id=None, station_id=None, vehicle_id=None, project_id=None, batch=None
) -> StockLevel:
    filters = dict(
        product=product, warehouse_id=warehouse_id, station_id=station_id, vehicle_id=vehicle_id,
        project_id=project_id, batch=batch,
    )
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
        level = StockLevel.objects.filter(product=product, warehouse=warehouse, station=None, project=None, batch=None).first()
        available = level.quantity if level else Decimal("0")
        return [(None, min(available, quantity))] if available > 0 else []

    plan = []
    remaining = quantity
    batches = Batch.objects.filter(product=product, warehouse=warehouse).order_by(
        F("expiry_date").asc(nulls_last=True)
    )
    levels_by_batch = {
        level.batch_id: level.quantity
        for level in StockLevel.objects.filter(product=product, warehouse=warehouse, station=None, project=None, batch__in=batches)
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


def effective_reorder_point(product: Product, *, warehouse=None, station=None, vehicle=None) -> int:
    """A ProductStockThreshold override for this exact (product, site) pair
    wins if one exists; otherwise falls back to Product.reorder_point."""
    if sum(bool(site) for site in (warehouse, station, vehicle)) != 1:
        raise ValueError("Pass exactly one of warehouse, station, or vehicle.")
    override = ProductStockThreshold.objects.filter(
        product=product, warehouse=warehouse, station=station, vehicle=vehicle
    ).values_list("reorder_point", flat=True).first()
    return override if override is not None else product.reorder_point


def bulk_effective_reorder_points(stock_levels):
    """{stock_level.pk: effective threshold} for an iterable of StockLevel
    rows (each already warehouse-, station-, or vehicle-scoped), in a
    bounded number of queries regardless of how many rows are passed -- for
    list/detail views that would otherwise call effective_reorder_point()
    once per row."""
    stock_levels = list(stock_levels)
    warehouse_ids = {sl.warehouse_id for sl in stock_levels if sl.warehouse_id}
    station_ids = {sl.station_id for sl in stock_levels if sl.station_id}
    vehicle_ids = {sl.vehicle_id for sl in stock_levels if sl.vehicle_id}
    product_ids = {sl.product_id for sl in stock_levels}

    overrides = {}
    thresholds = ProductStockThreshold.objects.filter(product_id__in=product_ids).filter(
        Q(warehouse_id__in=warehouse_ids) | Q(station_id__in=station_ids) | Q(vehicle_id__in=vehicle_ids)
    )
    for t in thresholds:
        overrides[(t.product_id, t.warehouse_id, t.station_id, t.vehicle_id)] = t.reorder_point

    result = {}
    for sl in stock_levels:
        key = (sl.product_id, sl.warehouse_id, sl.station_id, sl.vehicle_id)
        result[sl.pk] = overrides.get(key, sl.product.reorder_point)
    return result


def attach_low_stock_counts(sites, site_field):
    """Sets .low_stock_count on each Warehouse/Station/Vehicle in `sites`,
    respecting any ProductStockThreshold override for that exact site -- a
    plain Product.reorder_point-only DB annotation can't account for those
    per-location overrides, so this resolves it in Python instead, in a
    bounded number of queries regardless of list size."""
    sites = list(sites)
    site_ids = [s.pk for s in sites]
    levels = StockLevel.objects.filter(**{f"{site_field}_id__in": site_ids}).values(
        "product_id", site_field, "quantity", "product__reorder_point"
    )
    overrides = {
        (t.product_id, getattr(t, f"{site_field}_id")): t.reorder_point
        for t in ProductStockThreshold.objects.filter(**{f"{site_field}_id__in": site_ids})
    }
    counts = {}
    for row in levels:
        threshold = overrides.get((row["product_id"], row[site_field]), row["product__reorder_point"])
        if row["quantity"] <= threshold:
            site_id = row[site_field]
            counts[site_id] = counts.get(site_id, 0) + 1
    for s in sites:
        s.low_stock_count = counts.get(s.pk, 0)
    return sites


def _maybe_fire_low_stock(product: Product, *, warehouse: Warehouse = None, station: Station = None, vehicle: Vehicle = None):
    if sum(bool(site) for site in (warehouse, station, vehicle)) != 1:
        raise ValueError("Pass exactly one of warehouse, station, or vehicle.")
    site_filter = {"warehouse": warehouse, "station": station, "vehicle": vehicle}
    total = (
        StockLevel.objects.filter(product=product, project=None, **site_filter).aggregate(total=Sum("quantity"))["total"]
        or Decimal("0")
    )
    threshold = effective_reorder_point(product, warehouse=warehouse, station=station, vehicle=vehicle)
    if total <= threshold:
        low_stock_signal.send(
            sender=Product, product=product, warehouse_id=warehouse.pk if warehouse else None,
            station_id=station.pk if station else None, vehicle_id=vehicle.pk if vehicle else None,
            quantity=total, reorder_point=threshold,
        )


@transaction.atomic
def stock_in(
    *, product_id, warehouse_id, quantity, performed_by, batch_id=None, reason_code="", comment="",
    purchase_order_id=None,
):
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
        purchase_order_id=purchase_order_id,
    )


@transaction.atomic
def stock_out(
    *, product_id, warehouse_id, quantity, performed_by, station_id=None, project_id=None, vehicle_id=None,
    reason_code="", comment="", batch_id=None, override_fefo=False, request_id=None,
):
    """Debits warehouse stock. If `station_id`, `project_id`, or
    `vehicle_id` is given (mutually exclusive), the same quantity is
    credited to that station's, deep clean project's, or vehicle's stock in
    the same atomic operation (issued-to-station / issued-to-project /
    issued-to-vehicle -- vehicles carry their own running stock of
    equipment and chemicals, restocked from a warehouse just like a
    station); otherwise this is a write-off/consumption with no destination
    stock. Defaults to FEFO for batch-tracked products; passing `batch_id`
    requires `override_fefo=True` and should carry a `reason_code`
    (Supervisor override, SRS Section 5.4). `request_id` is purely for
    traceability back to a StockRequest -- callers (e.g.
    apps.requests.services) are responsible for checking approval status
    before calling this; this function has no opinion on approval workflow.
    """
    if sum(dest is not None for dest in (station_id, project_id, vehicle_id)) > 1:
        raise ValueError("Issue stock to a station, a project, or a vehicle -- not more than one.")

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
            product=product, warehouse=warehouse, station=None, project=None, batch=batch, quantity__gte=take_qty
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
            source_warehouse=warehouse, station_id=station_id, project_id=project_id, vehicle_id=vehicle_id,
            reason_code=reason_code, comment=comment, performed_by=performed_by, request_id=request_id,
        )
        txns.append(txn)

        if station_id is not None:
            station_level = _get_or_create_stock_level(product=product, station_id=station_id, batch=batch)
            StockLevel.objects.filter(pk=station_level.pk).update(quantity=F("quantity") + take_qty)
        elif project_id is not None:
            project_level = _get_or_create_stock_level(product=product, project_id=project_id, batch=batch)
            StockLevel.objects.filter(pk=project_level.pk).update(quantity=F("quantity") + take_qty)
        elif vehicle_id is not None:
            vehicle_level = _get_or_create_stock_level(product=product, vehicle_id=vehicle_id, batch=batch)
            StockLevel.objects.filter(pk=vehicle_level.pk).update(quantity=F("quantity") + take_qty)

    _maybe_fire_low_stock(product, warehouse=warehouse)
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
def adjustment(
    *, product_id, quantity_delta, performed_by, reason_code, warehouse_id=None, station_id=None,
    comment="", batch_id=None,
):
    """`quantity_delta` may be positive or negative. `reason_code` is
    mandatory (SRS Section 5.4). Adjusts a warehouse or a station
    (mutually exclusive) -- station adjustments are how a stocktake count
    correction gets applied."""
    if not reason_code:
        raise ValueError("Stock adjustments require a reason_code.")
    if warehouse_id is not None and station_id is not None:
        raise ValueError("Adjust a warehouse or a station, not both.")
    if warehouse_id is None and station_id is None:
        raise ValueError("Adjustment requires a warehouse_id or station_id.")

    quantity_delta = Decimal(str(quantity_delta))
    product = Product.objects.get(pk=product_id)
    warehouse = Warehouse.objects.get(pk=warehouse_id) if warehouse_id is not None else None
    station = Station.objects.get(pk=station_id) if station_id is not None else None
    batch = Batch.objects.get(pk=batch_id) if batch_id else None

    if quantity_delta < 0:
        updated = StockLevel.objects.filter(
            product=product, warehouse_id=warehouse_id, station_id=station_id, project=None, batch=batch,
            quantity__gte=-quantity_delta,
        ).update(quantity=F("quantity") + quantity_delta)
        if updated == 0:
            raise StockLevelChangedError("Stock level changed; please retry the adjustment.")
    else:
        level = _get_or_create_stock_level(product=product, warehouse_id=warehouse_id, station_id=station_id, batch=batch)
        StockLevel.objects.filter(pk=level.pk).update(quantity=F("quantity") + quantity_delta)

    txn = InventoryTransaction.objects.create(
        type=TransactionType.ADJUSTMENT, product=product, batch=batch, quantity=abs(quantity_delta),
        source_warehouse=warehouse if warehouse and quantity_delta < 0 else None,
        dest_warehouse=warehouse if warehouse and quantity_delta >= 0 else None,
        station_id=station_id,
        reason_code=reason_code, comment=comment, performed_by=performed_by,
    )
    if quantity_delta < 0:
        if warehouse:
            _maybe_fire_low_stock(product, warehouse=warehouse)
        elif station:
            _maybe_fire_low_stock(product, station=station)
    return txn


@transaction.atomic
def create_stocktake(*, started_by, lines, warehouse_id=None, station_id=None):
    """Records a count session and immediately corrects any variance found
    -- `lines` is only the products actually counted this time (SRS: not
    everything gets checked every stocktake), each `{"product_id", "counted_quantity"}`."""
    if warehouse_id is not None and station_id is not None:
        raise ValueError("Stocktake a warehouse or a station, not both.")
    if warehouse_id is None and station_id is None:
        raise ValueError("Stocktake requires a warehouse_id or station_id.")

    stocktake = Stocktake.objects.create(warehouse_id=warehouse_id, station_id=station_id, started_by=started_by)

    stocktake_lines = []
    for line in lines:
        system_qty = (
            StockLevel.objects.filter(
                product_id=line["product_id"], warehouse_id=warehouse_id, station_id=station_id, project=None,
            ).aggregate(total=Sum("quantity"))["total"]
            or Decimal("0")
        )
        stocktake_lines.append(
            StocktakeLine(
                stocktake=stocktake, product_id=line["product_id"],
                system_quantity=system_qty, counted_quantity=Decimal(str(line["counted_quantity"])),
            )
        )
    StocktakeLine.objects.bulk_create(stocktake_lines)

    for sl in stocktake_lines:
        delta = sl.counted_quantity - sl.system_quantity
        if delta == 0:
            continue
        if station_id is not None and delta < 0:
            # Counted less than the system expected at a station -- this IS
            # consumption that was never logged as it happened, so record it
            # as station usage (flows into the consumption report and
            # transaction list the same way logged-as-it-happens usage does),
            # not a generic adjustment.
            station_stock_usage(
                product_id=sl.product_id, station_id=station_id, quantity=-delta, performed_by=started_by,
                comment=f"Stocktake #{stocktake.pk} -- unrecorded usage found during count",
            )
        else:
            adjustment(
                product_id=sl.product_id, warehouse_id=warehouse_id, station_id=station_id,
                quantity_delta=delta, performed_by=started_by, reason_code="stocktake",
                comment=f"Stocktake #{stocktake.pk} count correction",
            )

    stocktake.status = "completed"
    stocktake.completed_at = timezone.now()
    stocktake.save(update_fields=["status", "completed_at"])
    return stocktake


@transaction.atomic
def return_stock(
    *, product_id, warehouse_id, quantity, performed_by, station_id=None, project_id=None, vehicle_id=None,
    reason_code="", comment="", batch_id=None,
):
    """Returns from a station, deep clean project, or vehicle (mutually
    exclusive) back to a warehouse."""
    if sum(source is not None for source in (station_id, project_id, vehicle_id)) > 1:
        raise ValueError("Return from a station, a project, or a vehicle -- not more than one.")

    quantity = Decimal(str(quantity))
    product = Product.objects.get(pk=product_id)
    warehouse = Warehouse.objects.get(pk=warehouse_id)
    batch = Batch.objects.get(pk=batch_id) if batch_id else None

    if station_id is not None:
        updated = StockLevel.objects.filter(
            product=product, station_id=station_id, warehouse=None, project=None, vehicle=None, batch=batch,
            quantity__gte=quantity,
        ).update(quantity=F("quantity") - quantity)
        if updated == 0:
            raise StockLevelChangedError("Station stock level changed; please retry the return.")
    elif project_id is not None:
        updated = StockLevel.objects.filter(
            product=product, project_id=project_id, warehouse=None, station=None, vehicle=None, batch=batch,
            quantity__gte=quantity,
        ).update(quantity=F("quantity") - quantity)
        if updated == 0:
            raise StockLevelChangedError("Project stock level changed; please retry the return.")
    elif vehicle_id is not None:
        updated = StockLevel.objects.filter(
            product=product, vehicle_id=vehicle_id, warehouse=None, station=None, project=None, batch=batch,
            quantity__gte=quantity,
        ).update(quantity=F("quantity") - quantity)
        if updated == 0:
            raise StockLevelChangedError("Vehicle stock level changed; please retry the return.")

    level = _get_or_create_stock_level(product=product, warehouse_id=warehouse_id, batch=batch)
    StockLevel.objects.filter(pk=level.pk).update(quantity=F("quantity") + quantity)

    return InventoryTransaction.objects.create(
        type=TransactionType.RETURN, product=product, batch=batch, quantity=quantity,
        dest_warehouse=warehouse, station_id=station_id, project_id=project_id, vehicle_id=vehicle_id,
        reason_code=reason_code, comment=comment, performed_by=performed_by,
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
        product=product, warehouse=warehouse, station=None, project=None, batch=batch, quantity__gte=quantity
    ).update(quantity=F("quantity") - quantity)
    if updated == 0:
        raise StockLevelChangedError(f"Stock level changed; please retry recording this {txn_type}.")

    txn = InventoryTransaction.objects.create(
        type=txn_type, product=product, batch=batch, quantity=quantity, source_warehouse=warehouse,
        reason_code=reason_code, comment=comment, performed_by=performed_by, approved_by=approved_by, photo=photo,
    )
    _maybe_fire_low_stock(product, warehouse=warehouse)
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
            product=original.product, warehouse=original.dest_warehouse, station=None, project=None, batch=original.batch,
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


@transaction.atomic
def station_stock_usage(*, product_id, station_id, quantity, performed_by, comment="", batch_id=None):
    """Routine consumption of stock already held at a station -- e.g. daily
    cleaning chemical usage (SRS Section 5.6). Decrements station-side
    StockLevel directly; nothing flows back to a warehouse."""
    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise ValueError("quantity must be positive.")

    product = Product.objects.get(pk=product_id)
    batch = Batch.objects.get(pk=batch_id) if batch_id else None

    updated = StockLevel.objects.filter(
        product=product, station_id=station_id, warehouse=None, project=None, batch=batch, quantity__gte=quantity
    ).update(quantity=F("quantity") - quantity)
    if updated == 0:
        raise StockLevelChangedError("Station stock level changed; please retry recording this usage.")

    txn = InventoryTransaction.objects.create(
        type=TransactionType.STATION_USAGE, product=product, batch=batch, quantity=quantity,
        station_id=station_id, comment=comment, performed_by=performed_by,
    )
    _maybe_fire_low_stock(product, station=Station.objects.get(pk=station_id))
    return txn


@transaction.atomic
def vehicle_stock_usage(*, product_id, vehicle_id, quantity, performed_by, comment="", batch_id=None):
    """Routine consumption of stock already held on a vehicle -- e.g.
    equipment or chemicals used on a job. Decrements vehicle-side StockLevel
    directly; nothing flows back to a warehouse."""
    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise ValueError("quantity must be positive.")

    product = Product.objects.get(pk=product_id)
    batch = Batch.objects.get(pk=batch_id) if batch_id else None

    updated = StockLevel.objects.filter(
        product=product, vehicle_id=vehicle_id, warehouse=None, station=None, project=None, batch=batch,
        quantity__gte=quantity,
    ).update(quantity=F("quantity") - quantity)
    if updated == 0:
        raise StockLevelChangedError("Vehicle stock level changed; please retry recording this usage.")

    txn = InventoryTransaction.objects.create(
        type=TransactionType.VEHICLE_USAGE, product=product, batch=batch, quantity=quantity,
        vehicle_id=vehicle_id, comment=comment, performed_by=performed_by,
    )
    _maybe_fire_low_stock(product, vehicle=Vehicle.objects.get(pk=vehicle_id))
    return txn

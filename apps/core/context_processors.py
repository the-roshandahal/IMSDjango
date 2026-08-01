from django.conf import settings

from apps.accounts.models import Role
from apps.core.permissions import has_capability


def nav_capabilities(request):
    """Exposes capability flags to every template so the sidebar/nav can
    show only what the signed-in role can actually use, without every
    template re-deriving RBAC logic."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}

    can_view_products = has_capability(user, "product.view")
    can_view_requests = has_capability(user, "station_request.view")
    can_create_requests = has_capability(user, "station_request.create")
    can_view_stocktakes = has_capability(user, "stocktake.manage") or has_capability(user, "stocktake.view")
    # Station-only roles get a deliberately trimmed sidebar -- everything they
    # need lives on their station's own page (stock, requests, stocktakes,
    # usage) plus a station-scoped Transactions view, not a separate
    # catalogue-browsing Inventory section.
    is_station_role = user.role in (Role.STATION_STAFF, Role.STATION_SUPERVISOR)

    return {
        "can_view_products": can_view_products,
        "can_view_warehouses": has_capability(user, "warehouse.view"),
        "can_manage_products": has_capability(user, "product.manage"),
        "can_manage_stock": has_capability(user, "warehouse.stock.manage"),
        "can_record_usage": has_capability(user, "station.usage.record"),
        "can_manage_stocktake": has_capability(user, "stocktake.manage"),
        "can_view_stocktakes": can_view_stocktakes,
        "can_view_requests": can_view_requests,
        "can_create_requests": can_create_requests,
        "can_approve_requests": has_capability(user, "station_request.approve"),
        "can_view_transactions": has_capability(user, "warehouse.stock.manage") or has_capability(user, "transaction.view"),
        "is_station_role": is_station_role,
        "show_inventory_nav": not is_station_role
        and (can_view_products or can_view_requests or can_create_requests or can_view_stocktakes),
        # "*.request" capabilities (station/deepclean supervisors) aren't
        # wired to a page yet -- no equipment/vehicle request-approval flow
        # exists (deliberately out of scope this pass, see commit notes).
        # Only show the nav link where there's a real page behind it.
        "can_view_equipment": has_capability(user, "equipment.view_own") or has_capability(user, "equipment.assign"),
        "can_view_vehicles": has_capability(user, "vehicle.view_own") or has_capability(user, "vehicle.assign"),
        "can_view_projects": has_capability(user, "project.manage")
        or has_capability(user, "project.view")
        or has_capability(user, "project.update_own"),
        "can_view_suppliers": has_capability(user, "supplier.view") or has_capability(user, "supplier.manage"),
        "can_view_purchase_orders": has_capability(user, "purchase_order.view")
        or has_capability(user, "purchase_order.manage"),
        "can_view_employees": has_capability(user, "employee.manage") or has_capability(user, "employee.view"),
        "can_view_hazards": has_capability(user, "hazard.view") or has_capability(user, "hazard.report"),
        "can_view_reports": has_capability(user, "reports.view")
        or has_capability(user, "reports.view_own_site")
        or has_capability(user, "reports.view_own_project"),
        "is_admin": user.role == Role.ADMIN,
        "unread_notifications_count": user.notifications.filter(is_read=False).count(),
        "document_max_upload_mb": settings.DOCUMENT_MAX_UPLOAD_MB,
    }

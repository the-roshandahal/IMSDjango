from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Role, SiteAssignment, User
from apps.catalogue.models import Category, Product
from apps.catalogue.services import provision_codes
from apps.inventory import services as inv_services
from apps.requests import services as req_services
from apps.warehouses.models import Station, Warehouse


class Command(BaseCommand):
    help = "Seeds idempotent demo data so the UI has something to show."

    @transaction.atomic
    def handle(self, *args, **options):
        admin = self._ensure_user("admin", "admin@ims.local", "AdminPass123!", Role.ADMIN, is_superuser=True)
        management = self._ensure_user("manager1", "manager1@ims.local", "ManagerPass123!", Role.MANAGEMENT)
        wh_sup = self._ensure_user("whsup1", "whsup1@ims.local", "SupPass123!", Role.WH_SUPERVISOR)
        wh_staff = self._ensure_user("whstaff1", "whstaff1@ims.local", "StaffPass123!", Role.WH_STAFF)
        st_sup = self._ensure_user("stationsup1", "stationsup1@ims.local", "SupPass123!", Role.STATION_SUPERVISOR)
        st_staff = self._ensure_user("stationstaff1", "stationstaff1@ims.local", "StaffPass123!", Role.STATION_STAFF)

        wh1, _ = Warehouse.objects.get_or_create(name="Central Warehouse", defaults={"address": "12 Depot Road", "capacity": 5000})
        wh2, _ = Warehouse.objects.get_or_create(name="North Regional Warehouse", defaults={"address": "8 Sidings Ave", "capacity": 2000})

        st1, _ = Station.objects.get_or_create(name="Central Station", defaults={"address": "Platform 1-4"})
        st2, _ = Station.objects.get_or_create(name="Riverside Station", defaults={"address": "Riverside Junction"})
        st3, _ = Station.objects.get_or_create(name="Hillcrest Station", defaults={"address": "Hillcrest Road"})

        SiteAssignment.objects.get_or_create(user=wh_sup, warehouse=wh1)
        SiteAssignment.objects.get_or_create(user=wh_staff, warehouse=wh1)
        SiteAssignment.objects.get_or_create(user=st_sup, station=st1)
        SiteAssignment.objects.get_or_create(user=st_staff, station=st1)

        chemicals, _ = Category.objects.get_or_create(name="Chemicals")
        consumables, _ = Category.objects.get_or_create(name="Consumables")
        ppe, _ = Category.objects.get_or_create(name="PPE")
        equipment_cat, _ = Category.objects.get_or_create(name="Equipment")

        products_spec = [
            ("Floor Cleaner 5L", chemicals, "IMS-0001", True, "Corrosive", 20, 10),
            ("Glass Cleaner 1L", chemicals, "IMS-0002", False, "", 15, 8),
            ("Disinfectant Concentrate 5L", chemicals, "IMS-0003", True, "Irritant", 25, 12),
            ("Microfibre Cloths (pack of 10)", consumables, "IMS-0004", False, "", 30, 15),
            ("Bin Liners (roll of 50)", consumables, "IMS-0005", False, "", 40, 20),
            ("Nitrile Gloves (box of 100)", ppe, "IMS-0006", False, "", 20, 10),
            ("Hi-Vis Vest", ppe, "IMS-0007", False, "", 10, 5),
            ("Mop Head (spare)", equipment_cat, "IMS-0008", False, "", 12, 6),
        ]
        products = {}
        for name, category, barcode, hazardous, hazard_class, reorder, minimum in products_spec:
            product, created = Product.objects.get_or_create(
                barcode=barcode,
                defaults=dict(
                    name=name, category=category, is_hazardous=hazardous, hazard_class=hazard_class,
                    reorder_point=reorder, minimum_stock_level=minimum,
                    qr_code_data=f"PENDING-{barcode}",  # placeholder so blank qr_code_data never collides; provision_codes() overwrites it below
                ),
            )
            if created:
                provision_codes(product)
            products[barcode] = product

        # Stock-in to warehouse 1 (generous), warehouse 2 (lighter)
        stock_plan_wh1 = {
            "IMS-0001": 120, "IMS-0002": 8, "IMS-0003": 60, "IMS-0004": 90,
            "IMS-0005": 150, "IMS-0006": 5, "IMS-0007": 25, "IMS-0008": 18,
        }
        for barcode, qty in stock_plan_wh1.items():
            self._ensure_stock_in(products[barcode].id, wh1.id, qty, admin)

        stock_plan_wh2 = {"IMS-0001": 40, "IMS-0004": 30, "IMS-0006": 15}
        for barcode, qty in stock_plan_wh2.items():
            self._ensure_stock_in(products[barcode].id, wh2.id, qty, admin)

        # Issue some stock to stations so station stock/usage has data
        for barcode, qty, station in [("IMS-0001", 15, st1), ("IMS-0004", 20, st1), ("IMS-0006", 3, st1)]:
            try:
                inv_services.stock_out(
                    product_id=products[barcode].id, warehouse_id=wh1.id, quantity=Decimal(qty),
                    performed_by=wh_sup, station_id=station.id, reason_code="initial_issue",
                )
            except Exception:  # noqa: BLE001 -- already issued on a prior run, ignore
                pass

        # A little station usage history
        try:
            inv_services.station_stock_usage(
                product_id=products["IMS-0001"].id, station_id=st1.id, quantity=Decimal("3"),
                performed_by=st_staff, comment="Daily platform clean",
            )
        except Exception:  # noqa: BLE001
            pass

        # Stock requests in various states
        if not st1.stock_requests.filter(status="pending").exists():
            req_services.create_request(
                station_id=st1.id, warehouse_id=wh1.id, requested_by=st_staff,
                lines=[{"product_id": products["IMS-0003"].id, "quantity": Decimal("10")}],
            )
        if not st1.stock_requests.filter(status="fulfilled").exists():
            fulfilled_req = req_services.create_request(
                station_id=st1.id, warehouse_id=wh1.id, requested_by=st_sup,
                lines=[{"product_id": products["IMS-0005"].id, "quantity": Decimal("20")}],
            )
            req_services.approve_request(request_id=fulfilled_req.id, approved_by=wh_sup)
            req_services.dispatch_request(request_id=fulfilled_req.id, dispatched_by=wh_sup)
        if not st2.stock_requests.filter(status="rejected").exists():
            rejected_req = req_services.create_request(
                station_id=st2.id, warehouse_id=wh1.id, requested_by=st_sup,
                lines=[{"product_id": products["IMS-0007"].id, "quantity": Decimal("50")}],
            )
            req_services.reject_request(request_id=rejected_req.id, approved_by=wh_sup, reason="Quantity exceeds monthly allocation")

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write("Log in as: admin / AdminPass123!  (also: manager1, whsup1, whstaff1, stationsup1, stationstaff1 / <Role>Pass123!)")

    def _ensure_user(self, username, email, password, role, is_superuser=False):
        user, created = User.objects.get_or_create(username=username, defaults={"email": email, "role": role})
        if created:
            user.set_password(password)
            if is_superuser:
                user.is_staff = True
                user.is_superuser = True
            user.save()
        elif not user.role:
            user.role = role
            user.save(update_fields=["role"])
        return user

    def _ensure_stock_in(self, product_id, warehouse_id, quantity, performed_by):
        from apps.inventory.models import StockLevel

        existing = StockLevel.objects.filter(
            product_id=product_id, warehouse_id=warehouse_id, station=None, batch=None
        ).first()
        if existing and existing.quantity > 0:
            return
        inv_services.stock_in(
            product_id=product_id, warehouse_id=warehouse_id, quantity=Decimal(quantity),
            performed_by=performed_by, reason_code="initial_stock",
        )

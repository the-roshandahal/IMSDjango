from datetime import time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, SiteAssignment, User
from apps.catalogue.models import Category, Product
from apps.catalogue.services import provision_codes
from apps.employees.models import Employee
from apps.equipment.models import Equipment, EquipmentStatus, TestResult, TestTag
from apps.equipment.services import provision_qr_code
from apps.inventory import services as inv_services
from apps.projects import services as project_services
from apps.projects.models import DeepCleanProject, ProjectStatus, Shift
from apps.purchasing import services as po_services
from apps.purchasing.models import POStatus, PurchaseOrder
from apps.requests import services as req_services
from apps.suppliers.models import Supplier, SupplierProduct
from apps.vehicles import services as vehicle_services
from apps.vehicles.models import Vehicle, VehicleLocation, VehicleStatus
from apps.warehouses.models import Station, Warehouse


class Command(BaseCommand):
    help = "Seeds idempotent demo data so the UI has something to show."

    @transaction.atomic
    def handle(self, *args, **options):
        self.today = timezone.now().date()

        admin = self._ensure_user("admin", "admin@ims.local", "AdminPass123!", Role.ADMIN, is_superuser=True)
        management = self._ensure_user("manager1", "manager1@ims.local", "ManagerPass123!", Role.MANAGEMENT)
        wh_sup = self._ensure_user("whsup1", "whsup1@ims.local", "SupPass123!", Role.WH_SUPERVISOR)
        wh_staff = self._ensure_user("whstaff1", "whstaff1@ims.local", "StaffPass123!", Role.WH_STAFF)
        st_sup = self._ensure_user("stationsup1", "stationsup1@ims.local", "SupPass123!", Role.STATION_SUPERVISOR)
        st_staff = self._ensure_user("stationstaff1", "stationstaff1@ims.local", "StaffPass123!", Role.STATION_STAFF)
        dc_sup = self._ensure_user("dcsup1", "dcsup1@ims.local", "SupPass123!", Role.DEEPCLEAN_SUPERVISOR)

        wh1, _ = Warehouse.objects.get_or_create(name="Sefton Warehouse", defaults={"address": "12 Depot Road", "capacity": 5000})

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
        accessories, _ = Category.objects.get_or_create(name="Accessories")

        products_spec = [
            ("Agar Low Foam", chemicals, "IMS-0001", True, "Irritant", 20, 10),
            ("Agar Once Off", chemicals, "IMS-0002", True, "Corrosive", 15, 8),
            ("Agar pH7", chemicals, "IMS-0003", False, "", 25, 12),
            ("Agar Escalator Cleaner", chemicals, "IMS-0004", True, "Irritant", 15, 8),
            ("Agar Wonder Green", chemicals, "IMS-0005", True, "Corrosive", 15, 8),
            ("Agar Neutrex", chemicals, "IMS-0006", True, "Irritant", 20, 10),
            ("Country Garden", chemicals, "IMS-0007", False, "", 20, 10),
            ("Green Scrubbing Pads", consumables, "IMS-0008", False, "", 40, 20),
            ("Yellow Sponge", consumables, "IMS-0009", False, "", 40, 20),
            ("Magic Sponge", consumables, "IMS-0010", False, "", 30, 15),
            ("Yellow Dusting Chux", consumables, "IMS-0011", False, "", 30, 15),
            ("Dusters", consumables, "IMS-0012", False, "", 25, 10),
            ("Pad Holders", accessories, "IMS-0013", False, "", 15, 8),
            ("Hose - 50m", accessories, "IMS-0014", False, "", 10, 4),
            ("Hose - 100m", accessories, "IMS-0015", False, "", 8, 3),
            ("Nitrile Gloves (box of 100)", ppe, "IMS-0016", False, "", 20, 10),
            ("Hi-Vis Vest", ppe, "IMS-0017", False, "", 10, 5),
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

        # Stock-in to the (single) warehouse
        stock_plan_wh1 = {
            "IMS-0001": 140, "IMS-0002": 40, "IMS-0003": 80, "IMS-0004": 30,
            "IMS-0005": 25, "IMS-0006": 35, "IMS-0007": 50, "IMS-0008": 260,
            "IMS-0009": 150, "IMS-0010": 100, "IMS-0011": 180, "IMS-0012": 120,
            "IMS-0013": 40, "IMS-0014": 20, "IMS-0015": 10, "IMS-0016": 8, "IMS-0017": 30,
        }
        for barcode, qty in stock_plan_wh1.items():
            self._ensure_stock_in(products[barcode].id, wh1.id, qty, admin)

        # Issue some stock to stations so station stock/usage has data
        for barcode, qty, station in [("IMS-0001", 15, st1), ("IMS-0008", 30, st1), ("IMS-0016", 3, st1)]:
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
                lines=[{"product_id": products["IMS-0009"].id, "quantity": Decimal("20")}],
            )
            req_services.approve_request(request_id=fulfilled_req.id, approved_by=wh_sup)
            req_services.dispatch_request(request_id=fulfilled_req.id, dispatched_by=wh_sup)
        if not st2.stock_requests.filter(status="rejected").exists():
            rejected_req = req_services.create_request(
                station_id=st2.id, warehouse_id=wh1.id, requested_by=st_sup,
                lines=[{"product_id": products["IMS-0017"].id, "quantity": Decimal("50")}],
            )
            req_services.reject_request(request_id=rejected_req.id, approved_by=wh_sup, reason="Quantity exceeds monthly allocation")
        for barcode, qty, station in [("IMS-0002", 6, st2), ("IMS-0006", 8, st3)]:
            if not station.stock_requests.filter(status="pending", lines__product_id=products[barcode].id).exists():
                req_services.create_request(
                    station_id=station.id, warehouse_id=wh1.id, requested_by=st_sup,
                    lines=[{"product_id": products[barcode].id, "quantity": Decimal(qty)}],
                )

        suppliers = self._seed_suppliers(products)
        equipment = self._seed_equipment(wh1, st1, admin)
        vehicles = self._seed_vehicles(wh_sup, admin)
        self._seed_test_tags(wh1, st1, st2, st3, admin)
        employees = self._seed_employees(admin, dc_sup)
        self._seed_projects(st1, st2, st3, dc_sup, wh1, equipment, vehicles, products, employees, admin)
        self._seed_purchase_orders(suppliers, wh1, products, wh_sup, wh_staff)

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write(
            "Log in as: admin/AdminPass123! manager1/ManagerPass123! whsup1/SupPass123! "
            "whstaff1/StaffPass123! stationsup1/SupPass123! stationstaff1/StaffPass123! dcsup1/SupPass123!"
        )

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

    # ------------------------------------------------------------ Suppliers

    def _seed_suppliers(self, products):
        specs = [
            ("Agar Cleaning Systems", "Jenny Wu", "+61 2 9555 0101", "orders@agar.example.com",
             [("IMS-0001", "14.50", True), ("IMS-0002", "16.80", False), ("IMS-0003", "11.20", True), ("IMS-0004", "22.00", False)]),
            ("Enviro Chemical Distributors", "Priya Nair", "+61 2 9555 0103", "accounts@envirochem.example.com",
             [("IMS-0005", "19.90", True), ("IMS-0006", "15.40", False), ("IMS-0007", "8.90", True)]),
            ("Bunzl Cleaning & Hygiene", "Tom Baker", "+61 2 9555 0104", "info@bunzl.example.com",
             [
                 ("IMS-0008", "2.20", True), ("IMS-0009", "1.10", False), ("IMS-0010", "1.80", False),
                 ("IMS-0011", "0.95", True), ("IMS-0012", "3.40", False),
             ]),
            ("Hydro Hose & Fittings", "Ana Costa", "+61 2 9555 0105", "sales@hydrohose.example.com",
             [("IMS-0013", "6.50", False), ("IMS-0014", "85.00", True), ("IMS-0015", "160.00", False)]),
            ("SafetyFirst PPE Co", "Marcus Lee", "+61 2 9555 0102", "sales@safetyfirst.example.com",
             [("IMS-0016", "18.90", True), ("IMS-0017", "12.50", True)]),
        ]
        suppliers = {}
        for name, contact, phone, email, links in specs:
            supplier, _ = Supplier.objects.get_or_create(
                name=name, defaults={"contact_person": contact, "phone": phone, "email": email, "is_active": True},
            )
            suppliers[name] = supplier
            for barcode, price, preferred in links:
                SupplierProduct.objects.get_or_create(
                    supplier=supplier, product=products[barcode],
                    defaults={"unit_price": Decimal(price), "is_preferred": preferred, "lead_time_days": 5},
                )
        return suppliers

    # ------------------------------------------------------------ Equipment

    def _seed_equipment(self, wh1, st1, admin):
        # (asset_id, name, interval_days, next_maintenance_offset, test_result, next_test_offset)
        # offsets are days from today: positive = due in the future (healthy), negative = overdue.
        specs = [
            ("EQ-ESB-001", "Escalator Brush", 90, 60, "pass", 300),
            ("EQ-ESC-001", "Escalator Cleaner", 60, 20, "pass", 300),
            ("SM01", "Scrubbing Machine (SM01)", 60, 45, "pass", 300),
            ("SM02", "Scrubbing Machine (SM02)", 60, -15, "pass", 300),  # maintenance overdue
            ("PW01", "Pressure Washer (PW01)", 90, 30, "pass", 300),
            ("PW02", "Pressure Washer (PW02)", 90, 40, "fail", 300),  # failed safety test
            ("EQ-PWR-001", "Pressure Washer Roller", 60, 25, "pass", 300),
            ("EQ-VAC-001", "Vacuum Cleaner", 90, 50, "pass", 300),
            ("EQ-CPT-001", "Carpet Cleaner", 120, 80, "pass", 300),
        ]
        equipment = {}
        for asset_id, name, interval, maint_offset, test_result, test_due_offset in specs:
            defaults = {
                "name": name, "serial_number": f"SN-{asset_id}",
                "current_warehouse": wh1, "status": EquipmentStatus.AVAILABLE,
                "last_test_date": self.today - timedelta(days=365 - test_due_offset),
                "next_test_due": self.today + timedelta(days=test_due_offset),
                "last_test_result": test_result,
            }
            if interval is not None:
                defaults["maintenance_interval_days"] = interval
                defaults["last_maintenance_at"] = self.today + timedelta(days=maint_offset) - timedelta(days=interval)
                defaults["next_maintenance_due"] = self.today + timedelta(days=maint_offset)
            equipment_item, created = Equipment.objects.get_or_create(asset_id=asset_id, defaults=defaults)
            if created:
                provision_qr_code(equipment_item)
            equipment[asset_id] = equipment_item

        # A couple already checked out, and one in maintenance, to show varied statuses
        if equipment["SM01"].status == EquipmentStatus.AVAILABLE:
            from apps.equipment import services as eq_services
            eq_services.assign_to_station(
                equipment_id=equipment["SM01"].id, station_id=st1.id, assigned_user_id=None, performed_by=admin,
                comment="Standing assignment for platform cleaning",
            )
        if equipment["EQ-VAC-001"].status == EquipmentStatus.AVAILABLE:
            from apps.equipment import services as eq_services
            eq_services.start_maintenance(equipment_id=equipment["EQ-VAC-001"].id, performed_by=admin, comment="Routine check")

        return equipment

    # ------------------------------------------------------------- Vehicles

    def _seed_vehicles(self, wh_sup, admin):
        specs = [
            ("MB-UTE-01", "Mercedes-Benz Sprinter Ute", 100, 350),
            ("MB-TRK-01", "Mercedes-Benz Atego Truck", 60, 300),
            ("TY-VAN-01", "Toyota HiAce Van", 45, 250),
            ("ISU-TRK-01", "Isuzu NPR Truck", 200, 300),  # not in use for now -- left unassigned
        ]
        vehicles = {}
        for registration, make_model, service_offset, insurance_offset in specs:
            vehicle, _ = Vehicle.objects.get_or_create(
                registration=registration,
                defaults={
                    "make_model": make_model, "status": VehicleStatus.AVAILABLE,
                    "service_due_date": self.today + timedelta(days=service_offset),
                    "insurance_expiry": self.today + timedelta(days=insurance_offset),
                },
            )
            vehicles[registration] = vehicle

        if vehicles["MB-UTE-01"].status == VehicleStatus.AVAILABLE:
            vehicle_services.assign_to_location(
                vehicle_id=vehicles["MB-UTE-01"].id, location=VehicleLocation.CAR_PARK, driver_id=None, performed_by=wh_sup,
                comment="Standing assignment",
            )

        return vehicles

    # ------------------------------------------------------------ Test tags

    def _seed_test_tags(self, wh1, st1, st2, st3, admin):
        specs = [
            ("Vacuum cleaner extension cord", wh1, None, -300, 65),
            ("Scrubber machine charger", wh1, None, -200, 165),
            ("Pressure washer power lead", wh1, None, -340, 25),  # expiring soon
            ("Extension cord (platform)", None, st1, -400, -35),  # expired
            ("Power board (office)", wh1, None, -100, 265),
            ("Battery charger lead", wh1, None, -150, 215),
            ("Carpet cleaner power cable", None, st1, -250, 115),
            ("Extension reel (yellow)", None, st2, -335, 20),  # expiring soon
            ("RCD safety switch tester lead", wh1, None, -50, 315),
            ("Portable heater cord", None, st3, -380, -15),  # expired
        ]
        for name, warehouse, station, start_offset, expiry_offset in specs:
            TestTag.objects.get_or_create(
                name=name, warehouse=warehouse, station=station,
                defaults={
                    "start_date": self.today + timedelta(days=start_offset),
                    "expiry_date": self.today + timedelta(days=expiry_offset),
                    "tested_by": admin,
                },
            )

    # ------------------------------------------------------------- Projects

    def _seed_employees(self, admin, dc_sup):
        # (first, last, email, phone, position, profile_complete, riw_offset_days)
        specs = [
            ("Maria", "Santos", "maria.santos@cleantech1.example.com", "+61 412 000 001", "Team Leader", True, 400),
            ("Liam", "Chen", "liam.chen@cleantech1.example.com", "+61 412 000 002", "Station Cleaner", True, 20),
            ("Aisha", "Khan", "aisha.khan@cleantech1.example.com", "+61 412 000 003", "Station Cleaner", True, -10),
            ("Noah", "Williams", "noah.williams@cleantech1.example.com", "+61 412 000 004", "Station Cleaner", True, 300),
            ("Sofia", "Garcia", "sofia.garcia@cleantech1.example.com", "+61 412 000 005", "Station Cleaner", False, None),
            ("Ethan", "Nguyen", "ethan.nguyen@cleantech1.example.com", "+61 412 000 006", "Station Cleaner", False, None),
        ]
        employees = {}
        for i, (first, last, email, phone, position, complete, riw_offset) in enumerate(specs):
            employee, created = Employee.objects.get_or_create(
                email=email,
                defaults=dict(first_name=first, last_name=last, phone=phone, position=position, created_by=admin),
            )
            if created:
                employee.invited_at = timezone.now()
                employee.invited_by = dc_sup
                if complete:
                    employee.dob = self.today - timedelta(days=365 * (22 + i * 3))
                    employee.address = "12 Example Street, Sydney NSW 2000"
                    employee.riw_number = f"RIW-{100000 + i}"
                    employee.riw_expiry_date = self.today + timedelta(days=riw_offset)
                    employee.emergency_contact_name = "Jordan " + last
                    employee.emergency_contact_phone = "+61 400 111 000"
                    employee.emergency_contact_relationship = "Spouse"
                    employee.profile_completed_at = timezone.now()
                employee.save()
            employees[email] = employee
        return employees

    def _demo_signature_png(self, seed_text):
        import hashlib
        from io import BytesIO

        from django.core.files.base import ContentFile
        from PIL import Image, ImageDraw

        img = Image.new("RGBA", (300, 120), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        digest = hashlib.md5(seed_text.encode()).hexdigest()
        points = []
        x, y = 15, 60
        for i in range(18):
            x += 15
            y = 60 + (int(digest[i % len(digest)], 16) * 4) - 30
            points.append((x, y))
        draw.line(points, fill=(16, 24, 40, 255), width=3, joint="curve")
        buf = BytesIO()
        img.save(buf, format="PNG")
        return ContentFile(buf.getvalue(), name=f"seed-sig-{abs(hash(seed_text)) % 10000}.png")

    def _seed_projects(self, st1, st2, st3, dc_sup, wh1, equipment, vehicles, products, employees, admin):
        crew = list(employees.values())

        active = DeepCleanProject.objects.filter(reference="DCP-2026-001").first()
        if not active:
            active = project_services.create_project(
                reference="DCP-2026-001", name="Central Station Deep Clean - August", location=st1.name,
                supervisor_id=dc_sup.id, start_date=self.today - timedelta(days=2),
                end_date=self.today + timedelta(days=5), created_by=admin,
            )
            inv_services.stock_out(
                product_id=products["IMS-0001"].id, warehouse_id=wh1.id, quantity=Decimal("10"),
                performed_by=dc_sup, project_id=active.id, reason_code="deep_clean",
            )
            project_services.mark_active(active.id)

        if vehicles["TY-VAN-01"].status == VehicleStatus.AVAILABLE:
            vehicle_services.assign(
                vehicle_id=vehicles["TY-VAN-01"].id, project_id=active.id, driver_id=None, performed_by=dc_sup,
                comment="On site for deep clean",
            )

        if not active.shift_logs.filter(work_date=self.today - timedelta(days=1)).exists():
            project_services.log_shift(
                project_id=active.id, work_date=self.today - timedelta(days=1), shift=Shift.NIGHT,
                start_time=time(22, 0), end_time=time(6, 0), employee_ids=[e.id for e in crew[:3]], logged_by=dc_sup,
                notes="Overnight deep clean, platforms 1-4",
            )
        if not active.shift_logs.filter(work_date=self.today).exists():
            project_services.log_shift(
                project_id=active.id, work_date=self.today, shift=Shift.NIGHT,
                start_time=time(22, 0), end_time=time(6, 0), employee_ids=[e.id for e in crew[2:5]], logged_by=dc_sup,
                notes="Different crew tonight -- platforms 5-8",
            )

        if not active.toolbox_talks.filter(topic="Wet floors & chemical handling").exists():
            talk = project_services.create_toolbox_talk(
                project_id=active.id, work_date=self.today - timedelta(days=1),
                topic="Wet floors & chemical handling",
                content=(
                    "Hazards: slippery platforms after mopping, chemical splash risk when diluting "
                    "Agar Wonder Green.\nControls: wear gloves and non-slip footwear, place wet "
                    "floor signage before starting, dilute chemicals per SDS, buddy up near the platform edge."
                ),
                attachment=None, conducted_by=dc_sup, employee_ids=[e.id for e in crew[:3]],
            )
            for attendee in talk.attendees.select_related("employee").all()[:2]:
                project_services.record_signature(
                    attendee_id=attendee.id, signature_file=self._demo_signature_png(attendee.employee.full_name)
                )

        if not DeepCleanProject.objects.filter(reference="DCP-2026-002").exists():
            project_services.create_project(
                reference="DCP-2026-002", name="Riverside Station Deep Clean", location=st2.name,
                supervisor_id=dc_sup.id, start_date=self.today + timedelta(days=10), end_date=None, created_by=admin,
            )

        if not DeepCleanProject.objects.filter(reference="DCP-2026-003").exists():
            completed = project_services.create_project(
                reference="DCP-2026-003", name="Hillcrest Station Deep Clean - Completed", location=st3.name,
                supervisor_id=dc_sup.id, start_date=self.today - timedelta(days=20),
                end_date=self.today - timedelta(days=18), created_by=admin,
            )
            project_services.log_shift(
                project_id=completed.id, work_date=self.today - timedelta(days=19), shift=Shift.DAY,
                start_time=time(8, 0), end_time=time(16, 0), employee_ids=[e.id for e in crew[3:5]], logged_by=dc_sup,
            )
            project_services.close_project(project_id=completed.id, performed_by=dc_sup)

    # ------------------------------------------------------ Purchase orders

    def _seed_purchase_orders(self, suppliers, wh1, products, wh_sup, wh_staff):
        supplier_list = list(suppliers.values())

        def make(idx, supplier, warehouse, creator, lines, expected_offset):
            ref_marker = f"seed-po-{idx}"
            if PurchaseOrder.objects.filter(notes=ref_marker).exists():
                return PurchaseOrder.objects.get(notes=ref_marker)
            po = po_services.create_purchase_order(
                supplier_id=supplier.id, warehouse_id=warehouse.id,
                expected_date=self.today + timedelta(days=expected_offset), notes=ref_marker, created_by=creator,
                lines=[{"product_id": products[b].id, "quantity": Decimal(q), "unit_price": Decimal(p)} for b, q, p in lines],
            )
            return po

        # 3 drafts
        make(1, supplier_list[0], wh1, wh_sup, [("IMS-0001", 50, "14.50")], 10)
        make(2, supplier_list[4], wh1, wh_staff, [("IMS-0016", 20, "18.90")], 14)
        make(3, supplier_list[2], wh1, wh_sup, [("IMS-0008", 100, "2.20"), ("IMS-0011", 80, "0.95")], 7)

        # 2 sent
        for idx, supplier, warehouse, creator, lines in [
            (4, supplier_list[1], wh1, wh_sup, [("IMS-0006", 30, "15.40")]),
            (5, supplier_list[0], wh1, wh_staff, [("IMS-0002", 25, "16.80")]),
        ]:
            po = make(idx, supplier, warehouse, creator, lines, 5)
            if po.status == POStatus.DRAFT:
                po_services.send(po_id=po.id, performed_by=creator)

        # 2 partially received
        for idx, supplier, warehouse, creator, lines in [
            (6, supplier_list[2], wh1, wh_sup, [("IMS-0009", 80, "1.10")]),
            (7, supplier_list[4], wh1, wh_staff, [("IMS-0017", 30, "12.50")]),
        ]:
            po = make(idx, supplier, warehouse, creator, lines, -2)
            if po.status == POStatus.DRAFT:
                po_services.send(po_id=po.id, performed_by=creator)
            po.refresh_from_db()
            if po.status == POStatus.SENT:
                line = po.lines.first()
                po_services.receive_line(line_id=line.id, quantity=line.quantity_ordered / 2, performed_by=creator)

        # 2 fully received
        for idx, supplier, warehouse, creator, lines in [
            (8, supplier_list[1], wh1, wh_sup, [("IMS-0007", 40, "8.90")]),
            (9, supplier_list[3], wh1, wh_staff, [("IMS-0014", 15, "85.00")]),
        ]:
            po = make(idx, supplier, warehouse, creator, lines, -5)
            if po.status == POStatus.DRAFT:
                po_services.send(po_id=po.id, performed_by=creator)
            po.refresh_from_db()
            if po.status in (POStatus.SENT, POStatus.PARTIALLY_RECEIVED):
                for line in po.lines.all():
                    if line.quantity_remaining > 0:
                        po_services.receive_line(line_id=line.id, quantity=line.quantity_remaining, performed_by=creator)

        # 1 cancelled
        po = make(10, supplier_list[0], wh1, wh_sup, [("IMS-0001", 20, "14.50")], 3)
        if po.status == POStatus.DRAFT:
            po_services.cancel(po_id=po.id, performed_by=wh_sup, reason="Duplicate order raised by mistake")

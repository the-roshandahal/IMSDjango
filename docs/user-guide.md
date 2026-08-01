# Cleantech1 IMS — User Guide

This guide explains how to use the Cleantech1 Inventory Management System (IMS). It covers every screen, organized by what you actually do day to day. Works the same on a phone, tablet, or computer — on a phone, tap the **☰ menu icon** top-left to open navigation.

---

## 1. Signing in

1. Go to the IMS login page and enter your **username or email** and **password**.
2. Some accounts require a second step (a 6-digit code) — enter it when asked.
3. After **10 minutes of no activity**, you'll be signed out automatically for security. Just log back in.
4. Forgot your password or locked out after failed attempts? Contact your Administrator — only they can reset accounts or unlock you.

---

## 2. What your role can do

Every account has one role, set by an Administrator. Your role decides what you see in the menu and what you're allowed to do.

| Role | Day-to-day job |
|---|---|
| **Administrator** | Full access to everything, including user management and system-wide settings. |
| **Warehouse Supervisor** | Runs the warehouse and has company-wide oversight: manage stock, approve station requests, assign equipment/vehicles, create purchase orders, and see reports across every site, not just their own. |
| **Warehouse Staff** | Not currently in use -- reserved for if a second warehouse person is hired. Would view products, view equipment/vehicles assigned to them, take part in stocktakes, create purchase orders. |
| **Station Supervisor** | Runs a cleaning station (can cover several): request stock from a warehouse, record daily chemical usage, run weekly stock audits, view reports for their stations. |
| **Station Cleaning Staff** | Works at a station: request stock, record chemical usage, run weekly stock audits. |
| **Deep Clean Supervisor** | Runs deep clean projects: dispatch chemicals, take equipment/vehicles, log shifts and hours, close out projects. |

You only see menu sections your role has access to — if something described below isn't in your menu, your role doesn't use it.

---

## 3. Dashboard

The first screen after login. Shows:
- Quick counts (products, warehouses, stations, low stock, pending requests, and role-specific alerts like equipment maintenance due or expired safety test tags)
- **Low stock alerts** — products at or below their reorder point
- **Recent activity** — the latest 20 stock movements, with a "View all" link to the full history
- **Pending stock requests** waiting on approval
- Administrators also see a live **Audit trail**

Tap any number or row to jump straight to that item.

---

## 4. Inventory

### Products (`Inventory → Products`)
- Search by name or barcode.
- Each product shows current stock, its **reorder point** (the level that triggers a "low stock" alert), and a hazard flag if it's a hazardous chemical.
- Open a product to see: stock by location, batch/expiry info (for batch-tracked items), its QR code, Safety Data Sheet (if uploaded), and any file attachments.
- **Warehouse Supervisors/Admins** can create and edit products, and set the reorder point — set it low for slow-moving items, higher for chemicals you burn through fast, so the alert actually means something for that product.

### Categories (`Inventory → Categories`)
Simple grouping for products (e.g. "Chemicals", "PPE", "Equipment consumables"). Admins manage these.

### Transactions (`Inventory → Transactions`)
The full, permanent history of every stock movement — stock in, stock out, transfers, returns, damaged/lost/expired write-offs, station usage. This list can never be edited or deleted, by design — it's the audit trail for where every unit of stock went.

---

## 5. Sites: Warehouses & Stations

- **Warehouses** hold bulk stock. Each has an address and active/inactive status.
- **Stations** are the railway station cleaning sites stock gets issued to.
- Open either to see current stock levels there.
- Warehouse Supervisors manage stock **in** their warehouse (receiving, adjustments, transfers) from the warehouse detail page.

---

## 6. Stock Requests (`Requests → Stock Requests`)

How a station gets more stock from a warehouse.

1. **Station staff/supervisor**: open the station, click **Request stock**, pick a warehouse, add products and quantities, submit.
2. **Warehouse Supervisor**: sees the request in their queue, **Approve** or **Reject** (a rejection needs a reason).
3. Once approved, the warehouse **Dispatches** it — this deducts warehouse stock and adds it to the station automatically. If there isn't enough stock for everything, it dispatches what's available and marks the rest as short (status: *Partially Fulfilled*).

Filter the list by status: Pending, Approved, Rejected, Partially Fulfilled, Fulfilled.

---

## 7. Deep Clean Projects (`Deep Clean → Projects`)

For multi-day deep-clean jobs at a station — tracks chemicals, equipment, vehicles, and hours separately from routine station stock.

- **Admin** creates the project: reference, name, station, supervisor, start/end dates.
- **Deep Clean Supervisor** (or anyone with manage rights) runs it from the project's detail page:
  - **Dispatch chemicals** from a warehouse to the project, and **Return** what's left over when done.
  - **Take equipment / Take vehicle** — checks it out to the project (blocked if that item has overdue maintenance or a failed safety test, unless you tick **Override** with a reason).
  - **Release** equipment/vehicles when finished with them.
  - **Log a shift** — date, day/night, start and end time, who worked it. Hours are calculated automatically, including overnight shifts that cross midnight.
  - **Close project** — only works once every piece of equipment/vehicle taken out has been released. If something's still checked out, you'll see exactly what's outstanding; override with a reason if you really need to close anyway.
- A project's status moves itself from **Planned → Active** the first time anything happens on it (a dispatch, an equipment take, or a shift log), and to **Completed** when you close it.

---

## 8. Fleet: Equipment, Test Tags & Vehicles

### Equipment (`Fleet → Equipment`)
Reusable gear (vacuums, scrubbers, pressure washers, etc.), each with its own asset ID and QR code.
- **Assign** to a station or a deep clean project, and to a specific person if useful.
- **Release** when done, **Start/End maintenance**, or **Record a safety test** result (pass/fail).
- Equipment with maintenance overdue or a failed/overdue safety test is blocked from being assigned — override with a reason if genuinely necessary.
- **Mark lost** or **Write off** when equipment is gone for good (write-off is permanent).

### Test Tags (`Fleet → Test Tags`)
For smaller electrical items too numerous to track individually as full Equipment (extension cords, chargers, power leads). Record the item name, location, start date, and expiry date. Filter by expired / expiring soon.

### Vehicles (`Fleet → Vehicles`)
Same idea as Equipment: assign to a station/project and driver, release, log running costs (fuel, tolls, repairs), track service due dates and insurance expiry. Vehicles with overdue service or expired insurance are blocked from assignment unless overridden.

---

## 9. Purchasing: Suppliers & Purchase Orders

### Suppliers (`Purchasing → Suppliers`)
Contact details for who you buy from, plus what products each supplier sells and at what price — used to auto-fill pricing when you create a purchase order.

### Purchase Orders (`Purchasing → Purchase Orders`)
1. **Create** a purchase order: pick a supplier, the warehouse it's delivering to, and add line items (product, quantity, unit price — auto-fills from the supplier's saved price if you've set one up).
2. It starts as a **Draft** — add or remove lines freely.
3. **Send to supplier** locks it and makes it official.
4. **Print** gives a clean printable copy of the order.
5. When stock arrives, **Receive** it against each line — partial deliveries are fine, receive whatever showed up and the rest stays outstanding. Warehouse stock updates the moment you record a receipt.
6. Status tracks itself: Draft → Sent → Partially Received → Received. **Cancel** is available any time before it's fully received (needs a reason).

---

## 10. Reports (`Reports`)

On-screen reports, filterable by date range where relevant:

- **Inventory** — what's on hand, an estimated stock value, ageing of batch-tracked stock, and what's expiring soon.
- **Consumption** — what's been issued out, broken down by station, by project, and by product.
- **Equipment** — current status breakdown, maintenance history, most-assigned items.
- **Deep clean projects** — cost per project (chemicals + vehicle running costs), whether it finished on time, and any outstanding assets.
- **Purchasing** — spend by supplier, average lead time, on-time delivery rate.
- **Vehicles** — running costs, service/insurance compliance issues.
- **Audit summary** — activity volume by user and by action (Admin only).

What you see is scoped to your role — a Station Supervisor sees their own stations' numbers, Deep Clean Supervisors see their own projects, Admin and Warehouse Supervisor see everything.

*Note: reports are on-screen only for now — no PDF/Excel export or scheduled email reports yet.*

---

## 11. Notifications

Click **Notifications** (top-right, with an unread count badge) to see your alerts:
- **Low stock** — a product you're responsible for dropped to/below its reorder point.
- **Expiring stock** — a batch is expiring soon or has expired.
- **Maintenance due** — equipment, a test tag, or a vehicle needs attention.
- **Outstanding request** — a stock request has been sitting too long unactioned.
- **Purchase order** — an order was fully received, or is overdue against its expected delivery date.

You also get an email for each one (if your account has an email address on file). Click **Open** on a notification to jump straight to what it's about, or **Mark all read** to clear the badge.

---

## 12. Attaching files

Products, purchase orders, equipment, vehicles, and deep clean projects each have an **Attachments** section on their detail page — for Safety Data Sheets, certificates, invoices, service records, contracts, site photos, etc.

- Accepted file types: **PDF, JPG, PNG, DOCX, XLSX**, up to 10MB each.
- Click **Upload**, choose the file, add an optional description.
- Anyone who can edit that record can also upload/remove attachments for it.

---

## 13. Administration (Admin only)

### Users (`Administration → Users`)
Create accounts, assign roles, assign which warehouses/stations a user covers, deactivate accounts (with a reason — this is logged), reset passwords, unlock locked-out accounts.

### Audit Log (`Administration → Audit Log`)
A permanent, unchangeable record of every significant action in the system — logins, role changes, every inventory movement, equipment/vehicle status changes. Nothing here can ever be edited or deleted, by anyone, including Administrators.

---

## 14. Tips for using it on your phone

- Tap the **☰** icon top-left to open the menu; tap outside it or a menu item to close it.
- Wide tables (lots of columns) scroll **sideways within the table** — swipe left/right on the table itself, not the whole page.
- Forms and buttons are sized for tapping — no need to zoom in.
- Everything works the same as on desktop; only the layout adapts.

---

## 15. Common questions

**I don't see a menu item I need.** — Your role doesn't have access to it. Ask your Administrator if you think that's wrong.

**A button/action is greyed out or missing.** — Usually a permission or a status issue (e.g. you can't dispatch stock request until it's approved). Check the item's status first.

**Equipment/vehicle assignment is blocked.** — It has overdue maintenance, an overdue/failed safety test, or (for vehicles) overdue service/expired insurance. Fix the underlying issue, or override with a reason if it's genuinely urgent — overrides are logged.

**I closed a deep clean project by mistake / need to reopen something.** — Nothing in this system can be deleted or un-done by design (it's an audit trail). Contact your Administrator to figure out the right correction.

**Where do I report a bug or ask for a new feature?** — Contact your Administrator.

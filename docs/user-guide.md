# Cleantech1 IMS — User Guide

This guide explains how to use the Cleantech1 Inventory Management System (IMS). It covers every screen, organized by what you actually do day to day. Works the same on a phone, tablet, or computer — on a phone, tap the **☰ menu icon** top-left to open navigation.

---

## 1. Signing in

1. Go to the IMS login page and enter your **username or email** and **password**.
2. Some accounts require a second step (a 6-digit code) — enter it when asked.
3. After **10 minutes of no activity**, you'll be signed out automatically for security. Just log back in.
4. Forgot your password or locked out after failed attempts? Contact your Administrator — only they can reset accounts or unlock you.

An employee clocking in at a station doesn't need any of this — see **[3. Attendance & Duty Sheets](#3-attendance--duty-sheets-job-tracking)** for the tap-and-PIN alternative.

---

## 2. What your role can do

Every account has one role, set by an Administrator. Your role decides what you see in the menu and what you're allowed to do.

| Role | Day-to-day job |
|---|---|
| **Administrator** | Full access to everything, including user management and system-wide settings. |
| **Warehouse Supervisor** | Runs the warehouse and has company-wide oversight: manage stock, approve station requests, assign equipment/vehicles, create purchase orders, manage duty sheets and view attendance across every station, and see reports across every site, not just their own. |
| **Warehouse Staff** | Not currently in use -- reserved for if a second warehouse person is hired. Would view products, view equipment/vehicles assigned to them, take part in stocktakes, create purchase orders. |
| **Station Supervisor** | Runs a cleaning station (can cover several): request stock from a warehouse, record daily chemical usage, run weekly stock audits, set up and manage duty sheets, view attendance/task history, clock in/out themselves, view reports for their stations. |
| **Station Cleaning Staff** | Works at a station: request stock, record chemical usage, run weekly stock audits, clock in/out and work through their duty sheet's tasks. |
| **Deep Clean Supervisor** | Runs deep clean projects: dispatch chemicals, take equipment/vehicles, log shifts and hours, close out projects. |

You only see menu sections your role has access to — if something described below isn't in your menu, your role doesn't use it.

---

## 3. Attendance & Duty Sheets (Job Tracking)

This is how clocking in/out and the daily cleaning checklist work — the core of day-to-day job tracking at a station.

### 3.1 Duty sheets — set up once, reused every day

A **duty sheet** is a standing checklist for a shift at a station (e.g. "6am-2pm Platform"). It's created once and never needs recreating — only the tick marks reset each day.

From `Attendance → [a station]` (**Station Supervisor / Warehouse Supervisor / Administrator**):
- **New duty sheet** — give it a name, a start and end time, and its task list (one task per line). Tick times overnight-style if the shift crosses midnight (e.g. 10pm-6am) — the system handles the date rollover automatically (see 3.4).
- **Edit name & times** — on the duty sheet's own page, change the name or start/end time any time. Tasks aren't edited here on purpose — add or retire them separately so completed-task history stays intact.
- **Add a task** / **Retire a task** — grow the checklist over time, or retire an item you no longer need without losing its past completion history. A retired task can be reactivated later.
- **Deactivate / Reactivate** the whole duty sheet — hides it from the clock-in picker without deleting its history.
- **Assign ahead of time** — pick an employee from the dropdown to claim a duty sheet for a given date yourself, instead of leaving it open for someone to pick. Only employees assigned to that station are offered, and someone already claimed on another duty sheet that day won't double up.

### 3.2 Clocking in and working a shift (employee)

From `Attendance → Clock In/Out` (**Station Cleaning Staff / Station Supervisor**):
1. If you cover more than one station, pick which one.
2. **If a duty sheet is already yours** (you picked it earlier, or a supervisor assigned it) — you go straight to clocking in, no picker shown.
3. **Otherwise**, pick from whichever duty sheets nobody's claimed yet for today. Picking one claims it for the day — it drops off the list for everyone else.
4. Once clocked in, you see your duty sheet's tasks. Tap a task to check it off — this reveals an optional **notes** box and a **photo** upload before you confirm with **Mark done**, so nothing saves until you actually submit it. Both are optional; use them to record why something couldn't be fully done, or as photo proof it was.
5. Anything left undone on **other** duty sheets at the same station shows underneath as **"Left over from another duty sheet today"** — visible so you know it's outstanding, but you can only tick off tasks on your own duty sheet, not someone else's.
6. **Clock out** when you're done.

You can only ever be clocked in at one place at a time — the system blocks a second clock-in until you clock out of the first.

### 3.3 Tap-and-PIN kiosk (shared device, no typing a password)

A station can have one shared NFC tag that any employee taps to identify themselves — no username or password ever typed on the shared device:
1. Tap the tag (or open its link) → pick your name from the list of employees assigned to that station.
2. Enter your short **PIN** (see 3.5 for how a supervisor sets one up).
3. You're signed in and land straight on the clock screen for that station.
4. Tap the tag again later (same shift) and, if you're still signed in, it skips straight to your tasks.
5. **Clocking out automatically signs the shared device out too**, so it's ready for the next person to tap in clean.

Too many wrong PIN attempts locks the account the same way a wrong password does — ask a supervisor to unlock it.

### 3.4 Overnight shifts

A duty sheet whose end time is earlier than its start time (e.g. 10pm-6am) is treated as one continuous overnight shift: the early-morning hours after midnight still count as the date the shift started on, so it doesn't accidentally split into two days or let someone else "pick" it again right after midnight.

### 3.5 Supervisor view: history, evidence, who's on-site

From a duty sheet's page (**Station Supervisor / Warehouse Supervisor / Administrator**):
- A **date picker** lets you look back at any past day and see, per task: done or not done, who did it, when, their notes, and a link to view any attached photo.
- Status resets automatically for the new day — nothing carries over, so today always starts clean.
- The station page also shows who's **currently clocked in** right now, across every duty sheet.

To let an employee use the tap-and-PIN kiosk, they need a PIN set up first — see **[4. Employees](#4-employees) → Kiosk PIN**.

---

## 4. Employees

The employee directory (`Employees`) is separate from user login accounts — it's where you manage the people actually doing the work, including what's needed for Attendance (section 3) above.

- **Add an employee** — name, position, contact details, date started.
- **Onboarding link** — send this to a new employee so they fill in their own details (date of birth, address, RIW card number and expiry, emergency contact) without you typing it for them. They can revisit the same link any time to update it, e.g. after their RIW card renews.
- **Create login** — gives the employee an actual username/password account, needed before they can clock in at all. (Blocked if another account already uses that email.)
- **Station assignment** — which station(s) they're allowed to clock in at and be offered duty sheets for. Add or remove stations from their profile page.
- **Kiosk PIN** — set up (or regenerate) a short PIN so this employee can use the tap-and-PIN kiosk (3.3) instead of typing a password on a shared device.
- **Deactivate / Reactivate** — deactivating stops their onboarding link and login from working.

RIW card expiry is flagged on the employee's page (valid / expiring soon / expired) once they've completed onboarding.

---

## 5. Dashboard

The first screen after login. Shows:
- Quick counts (products, warehouses, stations, low stock, pending requests, and role-specific alerts like equipment maintenance due or expired safety test tags)
- **Low stock alerts** — products at or below their reorder point
- **Recent activity** — the latest 20 stock movements, with a "View all" link to the full history
- **Pending stock requests** waiting on approval
- Administrators also see a live **Audit trail**

Tap any number or row to jump straight to that item.

---

## 6. Inventory

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

## 7. Sites: Warehouses & Stations

- **Warehouses** hold bulk stock. Each has an address and active/inactive status.
- **Stations** are the railway station cleaning sites stock gets issued to.
- Open either to see current stock levels there.
- Warehouse Supervisors manage stock **in** their warehouse (receiving, adjustments, transfers) from the warehouse detail page.

---

## 8. Stock Requests (`Requests → Stock Requests`)

How a station gets more stock from a warehouse.

1. **Station staff/supervisor**: open the station, click **Request stock**, pick a warehouse, add products and quantities, submit.
2. **Warehouse Supervisor**: sees the request in their queue, **Approve** or **Reject** (a rejection needs a reason).
3. Once approved, the warehouse **Dispatches** it — this deducts warehouse stock and adds it to the station automatically. If there isn't enough stock for everything, it dispatches what's available and marks the rest as short (status: *Partially Fulfilled*).

Filter the list by status: Pending, Approved, Rejected, Partially Fulfilled, Fulfilled.

---

## 9. Deep Clean Projects (`Deep Clean → Projects`)

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

## 10. Fleet: Equipment, Test Tags & Vehicles

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

## 11. Purchasing: Suppliers & Purchase Orders

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

## 12. Reports (`Reports`)

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

## 13. Notifications

Click **Notifications** (top-right, with an unread count badge) to see your alerts:
- **Low stock** — a product you're responsible for dropped to/below its reorder point.
- **Expiring stock** — a batch is expiring soon or has expired.
- **Maintenance due** — equipment, a test tag, or a vehicle needs attention.
- **Outstanding request** — a stock request has been sitting too long unactioned.
- **Purchase order** — an order was fully received, or is overdue against its expected delivery date.

You also get an email for each one (if your account has an email address on file). Click **Open** on a notification to jump straight to what it's about, or **Mark all read** to clear the badge.

---

## 14. Attaching files

Products, purchase orders, equipment, vehicles, and deep clean projects each have an **Attachments** section on their detail page — for Safety Data Sheets, certificates, invoices, service records, contracts, site photos, etc.

- Accepted file types: **PDF, JPG, PNG, DOCX, XLSX**, up to 10MB each.
- Click **Upload**, choose the file, add an optional description.
- Anyone who can edit that record can also upload/remove attachments for it.

(A completed duty sheet task's photo, in section 3, is a separate, smaller attachment point specific to that one task — not this general Attachments panel.)

---

## 15. Administration (Admin only)

### Users (`Administration → Users`)
Create accounts, assign roles, assign which warehouses/stations a user covers, deactivate accounts (with a reason — this is logged), reset passwords, unlock locked-out accounts.

### Audit Log (`Administration → Audit Log`)
A permanent, unchangeable record of every significant action in the system — logins, role changes, every inventory movement, equipment/vehicle status changes. Nothing here can ever be edited or deleted, by anyone, including Administrators.

---

## 16. Tips for using it on your phone

- Tap the **☰** icon top-left to open the menu; tap outside it or a menu item to close it.
- Wide tables (lots of columns) scroll **sideways within the table** — swipe left/right on the table itself, not the whole page.
- Forms and buttons are sized for tapping — no need to zoom in.
- The Attendance clock screen (section 3) is built for one-handed phone use on shift — large tap targets, camera-ready photo upload.
- Everything works the same as on desktop; only the layout adapts.

---

## 17. Common questions

**I don't see a menu item I need.** — Your role doesn't have access to it. Ask your Administrator if you think that's wrong.

**A button/action is greyed out or missing.** — Usually a permission or a status issue (e.g. you can't dispatch stock request until it's approved). Check the item's status first.

**Equipment/vehicle assignment is blocked.** — It has overdue maintenance, an overdue/failed safety test, or (for vehicles) overdue service/expired insurance. Fix the underlying issue, or override with a reason if it's genuinely urgent — overrides are logged.

**I can't tick off a task I can see on the clock screen.** — It belongs to a different duty sheet than the one you're clocked in for (shown under "Left over from another duty sheet today"). It's visible so you're aware of it, but only the person clocked in on that duty sheet can tick it off.

**The kiosk PIN says locked / too many attempts.** — Same lockout as a normal password, just triggered by the shared tag instead. Ask a supervisor to unlock the account.

**I closed a deep clean project by mistake / need to reopen something.** — Nothing in this system can be deleted or un-done by design (it's an audit trail). Contact your Administrator to figure out the right correction.

**Where do I report a bug or ask for a new feature?** — Contact your Administrator.

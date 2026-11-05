# Hospitality Core: Refactor Spec (lean, standard-ERPNext-first)

Put this file in the repo as `docs/REFACTOR_SPEC.md`, then give Antigravity the **Master Prompt** below.

---

## 0. Master Prompt (paste this into Antigravity)

```
You are refactoring the existing Frappe app `hospitality_core` (repo root: apps/hospitality_core)
into a LEAN hotel front-desk app that uses STANDARD ERPNext wherever possible.

Read docs/REFACTOR_SPEC.md completely before doing anything. It is the single source of truth.

Environment: local bench at ~/frappe-bench, site `frappe.com`, Frappe/ERPNext v17 develop,
Python 3.14, Node 24. ERPNext/Frappe source is in ~/frappe-bench/apps/frappe and
~/frappe-bench/apps/erpnext: READ IT to verify every standard doctype/field/function you use.
Never assume an API from memory.

Rules:
1. Work in phases (spec section 12). Finish a phase, run its verification, git commit, then continue.
2. FIRST produce a written plan + the inventory (phase 1). Do not delete anything before the backup
   and the keep/remove table are done.
3. Nothing hardcoded: no company names, item codes, account names, user names, reception names.
   Everything comes from the Hotel Settings single doctype (spec section 5).
4. Keep the app name and module path (`hospitality_core`) so the existing site install keeps working.
5. Keep only what the spec lists. Remove everything else (spec section 10).
6. Where the spec says "verify in source", check the installed ERPNext v17 code. If the standard
   doctype cannot do it without hacks, STOP and report the finding with a recommended fallback.
7. At the end run the acceptance tests (spec section 13) and show me the output.
```

---

## 1. Goal in one paragraph

A small custom app for **front desk only**. Custom doctypes only for the hotel inventory and the
stay itself: **Hotel Room Type, Hotel Room, Room Rate Plan, Hotel Reservation**.
Guests are standard **Customer**. Money is standard **Payment Entry** and **Sales Invoice**.
Maintenance is the standard **Issue** (Support). Housekeeping is a room status
with Mark Dirty / Mark Clean (see 2.3 for the Quality-module question).
Everything else in the current app is removed.

## 2. Decisions made (confirm or change before starting)

| # | Decision | Why |
|---|----------|-----|
| 2.1 | **Guest = standard Customer.** Custom `Guest` doctype is deleted. Extra guest fields are Custom Fields on Customer. | Requested. |
| 2.2 | **Billing = standard Sales Invoice created at check-out + standard Payment Entry** (advance payments allowed anytime). **Guest Folio / Folio Transaction are deleted.** | Requested "payment entry standard". A Sales Invoice with Room Rent lines replaces the folio. |
| 2.3 | **Housekeeping** = `status` on Hotel Room (Available / Occupied / Dirty / Out of Order) + Mark Dirty / Mark Clean actions + a Kanban/list view. **Quality Inspection is optional, Phase 9.** | Standard Quality Inspection is built around stock items and fixed reference types (Purchase Receipt, Delivery Note, Job Card...). It cannot link a Hotel Room without hacks. **Verify in source**; if it works cleanly, add an optional inspection on Mark Clean. |
| 2.4 | **Maintenance = standard Issue** with Custom Fields `hotel_room` and `hotel_reservation`. The custom `Hotel Maintenance Request` is deleted. | Requested "maintenance standard". Issue has status, priority, assignee, resolution already. |
| 2.5 | **Hotel Reception is deleted.** If multi-property is needed later, use standard Company / Cost Center. | Not in the required flow; it was a hardcoding source. |
| 2.6 | Check-out bills **actual nights** (check-in date to today), not the planned departure date. No "departure must be today" restriction. | Handles early leave and overstay without extra screens. |

---

## 3. The workflow this app must support (user's own flow)

| # | Real-life step | Screen / action | What the system does |
|---|----------------|-----------------|----------------------|
| 1 | Add room type | Hotel Room Type > New | Stores default rate and billing item. |
| 2 | Add rooms | Hotel Room > New | Status Available. |
| 3 | Add rate plan | Room Rate Plan > New | Special rate for a date range (optionally for a customer / customer group). |
| 4 | Guest arrives | Customer (create or pick) | Guest is a Customer. |
| 5 | Reserve and assign room | Hotel Reservation > New | Validates availability, resolves rate, first stay segment created. |
| 6 | **Check in** | Reservation > Check In | Room Available -> Occupied. Reservation Checked In. |
| 7 | Guest has an issue in the room | Issue > New (room field) | Linked Issue. If room is occupied it stays Occupied until vacated. |
| 8 | **Move room** | Reservation > Move Room | Old segment closed, new segment opened with new room and rate. New room Occupied. Old room: Out of Order if it has an open Issue, otherwise Dirty. |
| 9 | **Take payment** | Reservation > Receive Payment | Opens a standard Payment Entry (advance) linked to the reservation. |
| 10 | **Check out** | Reservation > Check Out | Builds + submits a Sales Invoice for all segments, auto-allocates advances. Room Occupied -> Dirty (or Out of Order if open Issue). |
| 11 | Room dirty | automatic on check-out, or Hotel Room > Mark Dirty | Status Dirty. |
| 12 | **Mark clean** | Hotel Room > Mark Clean (also bulk from list) | Dirty -> Available. |
| 13 | Room has a fault | Hotel Room > Send to Maintenance | Creates a standard Issue; room -> Out of Order (if not occupied). |
| 14 | **Complete maintenance** | Issue status -> Resolved / Closed | If the room has no other open Issue: Out of Order -> status from Hotel Settings (`status_after_maintenance`, default Available). |

---

## 4. Data model

### 4.1 Custom doctypes (module `Hospitality Core`)

**Hotel Room Type** (keep, trim)
`room_type_name` (name), `default_rate` (Currency), `item` (Link Item: billable service item, optional,
falls back to Hotel Settings), `max_adults`, `max_children`, `description`.

**Hotel Room** (keep, trim)
`room_number` (name), `room_type` (Link), `floor`, `status` (Select: Available, Occupied, Dirty, Out of Order),
`is_enabled` (Check), `current_reservation` (Link Hotel Reservation, read only), `notes`.
Remove: hotel_reception, warehouse and any other link to removed doctypes.
Buttons: Mark Dirty, Mark Clean, Send to Maintenance. Bulk list action: Mark Clean.

**Room Rate Plan** (keep, trim)
`plan_name`, `room_type`, `rate`, `valid_from`, `valid_to`, `active`,
optional `customer_group` and `customer` (plan applies only to them when set).
Keep the existing validation: no overlapping active plans for the same room type (and same customer / group).

**Hotel Reservation** (rewrite)
Header: `naming_series`, `company` (default from Hotel Settings), `customer` (Link Customer, mandatory,
quick entry enabled), `room_type`, `room`, `check_in_date`, `check_out_date`, `adults`, `children`,
`rate_plan`, `status` (Reserved, Checked In, Checked Out, Cancelled), `checked_in_on` (Datetime, read only),
`checked_out_on` (Datetime, read only), `sales_invoice` (Link, read only), `remarks`.
Computed, read only, shown in a "Billing" section: `estimated_total`, `total_paid`, `balance`.
Child table **Hotel Reservation Stay** (one row per room segment):
`room`, `room_type`, `from_date`, `to_date`, `rate`, `nights` (computed), `move_reason`.

Not submittable. Status is changed only through the whitelisted methods below.

**Hotel Settings** (Single): see section 5.

### 4.2 Custom Fields on standard doctypes (created by code, not hand-made)

| Doctype | Fieldname | Type | Purpose |
|---------|-----------|------|---------|
| Customer | `is_hotel_guest` | Check | filter guests |
| Customer | `guest_id_type` | Select (Passport, National ID, Driving License, Other) | |
| Customer | `guest_id_number` | Data | |
| Payment Entry | `hotel_reservation` | Link Hotel Reservation | ties payment to the stay |
| Sales Invoice | `hotel_reservation` | Link Hotel Reservation, read only | prevents double invoicing |
| Issue | `hotel_room` | Link Hotel Room | maintenance target |
| Issue | `hotel_reservation` | Link Hotel Reservation | optional context |

Create them in `hospitality_core/setup/custom_fields.py` with
`frappe.custom.doctype.custom_field.custom_field.create_custom_fields`, called from `after_install`
and from a patch so the existing site gets them. Also add Custom DocPerms so role `Hospitality User`
can read/create Customer, Payment Entry, Sales Invoice and Issue (verify the standard role names).

---

## 5. Hotel Settings (the only place for configuration)

Single doctype `Hotel Settings`. **No value below may be hardcoded in Python or JS.**

| Field | Type | Meaning |
|-------|------|---------|
| `company` | Link Company | default company for reservations / invoices |
| `default_room_item` | Link Item | billing item when the room type has none |
| `guest_customer_group` | Link Customer Group | group for auto-created guests |
| `guest_territory` | Link Territory | territory for auto-created guests |
| `sales_taxes_template` | Link Sales Taxes and Charges Template | added to the invoice (GST etc.), optional |
| `cost_center` | Link Cost Center | optional |
| `status_after_maintenance` | Select (Available, Dirty) | room status after Issue is resolved, default Available |
| `allow_checkin_before_arrival` | Check | default off |
| `block_checkout_if_balance` | Check | default on: check-out needs balance <= tolerance |
| `balance_tolerance` | Currency | default 0 |
| `min_billable_nights` | Int | default 1 (same-day stay bills this many nights) |

Provide `hospitality_core/utils.py`:

```python
def get_settings():          # cached via frappe.get_cached_doc("Hotel Settings")
def get_company(): ...       # settings.company or frappe.defaults.get_user_default("Company")
def get_room_item(room_type) # room_type.item or settings.default_room_item, else frappe.throw(clear message)
```

Also expose the settings to JS through the `boot_session` hook as `frappe.boot.hotel_settings`.
Status names live as constants in `hospitality_core/constants.py` (one place, imported everywhere).

---

## 6. Business rules (implement in `hotel_reservation.py`, whitelisted methods)

**Availability** (keep the existing overlap logic): a room is available for [check_in, check_out) if it is enabled,
and has no Reserved / Checked In reservation whose stay segments overlap, and is not Out of Order for the arrival day.
Back-to-back (arrival = other's departure) is allowed. `get_available_rooms(room_type, check_in, check_out)`
feeds the Room dropdown (so only free rooms are offered).

**Rate** `get_room_rate(room_type, date, customer=None)`: active Rate Plan covering the date (customer / group
specific plan wins over a generic one), else `default_rate`. Stored in the stay row and editable by Hospitality Manager.

**check_in(name)**: status must be Reserved. Room status must be Available (else "Room not ready: Dirty / Out of Order / Occupied").
Today must be >= check_in_date unless `allow_checkin_before_arrival`. Set status Checked In, `checked_in_on = now`,
room Occupied, `room.current_reservation = name`. Stay row 1 `from_date = today` if it was earlier/later.

**move_room(name, new_room, reason, keep_rate=0)**: status must be Checked In. New room must be Available.
Close current stay row (`to_date = today`), add a new row (new room, rate = same rate if `keep_rate` else resolved rate).
Rows with 0 nights are dropped from billing. Old room: Out of Order if it has an open Issue, else Dirty.
New room Occupied. Update header `room` / `room_type`.

**receive_payment(name)**: client-side opens a new standard Payment Entry with
`payment_type=Receive, party_type=Customer, party=customer, company, hotel_reservation=name`
(route options). User picks Mode of Payment and amount, saves, submits. Nothing custom beyond the link field.
If the reservation already has a submitted invoice, open the standard "Create Payment" for that invoice instead.

**Billing summary** `get_billing_summary(name)` returns `estimated_total`, `total_paid`, `balance`:
- `estimated_total` = grand total of an **unsaved** Sales Invoice built by `build_sales_invoice(name, as_of=today)`
  after `set_missing_values()` and `calculate_taxes_and_totals()` (taxes included, nothing inserted).
- `total_paid` = submitted Payment Entries with `hotel_reservation = name` (Receive) + payments allocated to the invoice.

**build_sales_invoice(name, as_of)**: one line per stay row with nights > 0 (nights = max(to_date - from_date, 0);
for the last open row `to_date = as_of`; whole stay at least `min_billable_nights`).
`item_code = get_room_item(row.room_type)`, `qty = nights`, `rate = row.rate`,
description "Room {room} ({type}) {from} to {to}". Header: customer, company, `hotel_reservation`,
`taxes_and_charges = settings.sales_taxes_template`, `cost_center = settings.cost_center`,
`allocate_advances_automatically = 1` (**verify the exact field name / behaviour in v17**).
Income account comes from standard Item Defaults; if missing, throw a clear message naming the item.

**check_out(name)**: status must be Checked In. Close last stay row (`to_date = today`).
If `block_checkout_if_balance` and `balance > balance_tolerance`: throw "Receive payment first (balance X)".
Insert + submit the Sales Invoice, advances allocated automatically. Set `sales_invoice`, status Checked Out,
`checked_out_on = now`. Room: Out of Order if it has an open Issue, else Dirty. Clear `current_reservation`.

**cancel_reservation(name)**: only from Reserved. Status Cancelled. If advance Payment Entries exist, show a message
(refund is done with the standard Payment Entry, nothing custom).

**Issue hooks** (`doc_events` on Issue, only when `hotel_room` is set):
- Issue opened / reopened (status Open, Replied, Hold): if room is Available or Dirty -> Out of Order.
  If Occupied -> keep Occupied and `frappe.msgprint` "Move the guest, the room will go Out of Order when vacated".
- Issue Resolved / Closed: if the room is Out of Order and no other open Issue exists -> `status_after_maintenance`.
- Never change a room that is Occupied.

**Hotel Room actions**: `mark_dirty`, `mark_clean` (Dirty -> Available only; refuse if Occupied / Out of Order),
`send_to_maintenance` (creates an Issue prefilled with `hotel_room` and subject "Maintenance: Room X", then applies the Issue rule above).

All state changes to room status go through ONE function `set_room_status(room, status, reason)` in
`hospitality_core/room_status.py` so the rules live in one place.

---

## 7. What to KEEP from the existing app (pages / reports)

Reuse the existing code where possible, but rewrite its queries for the new schema.

| Type | Keep | Notes |
|------|------|-------|
| Page | **Front Desk Console** | Cards: Arrivals Pending (Reserved, check_in_date = date), Departures Pending (Checked In, check_out_date = date), Rooms In-House, Available Rooms + occupancy. Buttons: Tape Chart, Availability, Housekeeping, Reservations, House List, Maintenance. |
| Page | **Tape Chart** | rooms x dates grid built from `Hotel Reservation Stay` rows. |
| Page | **Availability Query** | date range -> free rooms. |
| Button target | Housekeeping | Hotel Room list / Kanban filtered `status = Dirty` (no custom page). |
| Button target | Reservations | Hotel Reservation list view. |
| Button target | Maintenance | Issue list filtered `hotel_room is set`. |
| Report | **House List** | in-house guests, room, nights, balance. |
| Report | **Daily Arrivals**, **Daily Departures** | |
| Report | **Room Availability Report** | |

If the current workspace shows other *front-desk* reports or pages, list them in the Phase 1 inventory and ask
before deciding. Default is to remove anything not in this table.

Workspace `Hotel`: shortcuts to Front Desk Console, Hotel Reservation, Hotel Room, Hotel Room Type, Room Rate Plan,
Customer (filtered `is_hotel_guest = 1`), Issue (hotel), Payment Entry, Sales Invoice, Hotel Settings, and the four reports above.

---

## 8. Client scripts (JS)

- `hotel_reservation.js`: buttons by status. Reserved: **Check In**, Cancel. Checked In: **Move Room** (dialog: new room from
  `get_available_rooms`, reason, keep rate), **Receive Payment**, **Check Out**. Checked Out: **View Invoice**.
  Billing section shows estimated total / paid / balance, refreshed after every action.
- `hotel_room.js`: Mark Dirty, Mark Clean, Send to Maintenance. `hotel_room_list.js`: bulk Mark Clean, status indicator colours.
- Read configuration from `frappe.boot.hotel_settings`, never from literals.

---

## 9. Hardcoding ban (acceptance check)

After the refactor this must return nothing (excluding tests and docs):

```bash
cd ~/frappe-bench/apps/hospitality_core
grep -rniE "Edo Herit
age|ROOM-RENT|POS-CHARGE|Main Reception|Annex|Administrator\"|'Administrator'" hospitality_core --include=*.py --include=*.js --include=*.json
```

Also no literal Company, Account, Item, Mode of Payment or Warehouse names anywhere. Status strings only via `constants.py`.

---

## 10. REMOVE list (verify each in the Phase 1 inventory first)

DocTypes: Guest, Guest Folio, Folio Transaction, Guest Balance Ledger, Hospitality Expense (+ Tax child),
Expense Category, Hospitality Accounting Settings, Hotel Maintenance Request, Hotel Reception,
Hotel Group Booking, Allowance Reason Code, EOD Closing Entry, and every other custom doctype not named in section 4.

Code: `api/night_audit.py` (and its scheduler entry), `api/payment_bridge.py`, `api/accounting.py`,
`api/financial_control.py`, `api/folio.py`, POS integration and POS hooks, city ledger / company-folio logic,
all `doc_events` for Payment Entry / POS Invoice / Folio, the `scheduler_events`, old fixtures and old Custom Fields
(`hotel_reception`, `room_number`, `cashier` on Payment Entry etc.).

UI: Hospitality Analytics dashboard, dashboard charts, number cards, `dashboard_data.py`, Housekeeping Board page,
Guest 360 page, all reports not in section 7, workflows (expense), print formats tied to folios.

Repo root clutter: `debug_*.py`, `verify_*.py`, `diag_*.py`, `check_*.py`, `update_*.py`, `fix_workspace.py`,
`setup_pos_report.py`, `run_test_pos.py`, `test_autoprint.sh`, `COMPOSITE_ITEM_SETUP.md`, compiled/backup folders,
`demo_data.py` (to be regenerated for the new schema in Phase 9).

---

## 11. Migration for the existing site (`frappe.com`, test data only)

1. `bench --site frappe.com backup --with-files` BEFORE anything. Commit current state to a git branch `pre-refactor`.
2. Add `patches.txt` entries:
   - `create_custom_fields`: adds section 4.2 fields.
   - `migrate_reservations` (only if real data matters): map old `Hotel Reservation.guest` -> `Guest.customer` into the new `customer`
     field, build one stay row from the old room / dates. For the current **demo data**: skip and wipe instead.
   - `remove_legacy`: delete removed doctypes with `frappe.delete_doc("DocType", name, force=1)` after deleting their rows,
     and delete removed Custom Fields, Workspace, Pages, Reports, Dashboards, Number Cards, Workflows.
3. `bench --site frappe.com migrate`, `bench build --app hospitality_core`, `bench restart`.
4. `hooks.py` must be cleaned: no references to deleted modules (a single broken `doc_events` path breaks the whole site).

---

## 12. Phases (do in order, commit after each)

| Phase | Work | Verification |
|-------|------|--------------|
| 1 | **Inventory.** Table of every doctype, page, report, hook, scheduler job, fixture, with KEEP / REMOVE / CHANGE. Backup + branch. | I review the table before Phase 2. |
| 2 | Hotel Settings, `utils.py`, `constants.py`, `room_status.py`, custom fields setup. | `bench migrate` clean; Hotel Settings opens. |
| 3 | Trim Hotel Room Type, Hotel Room, Room Rate Plan. Room actions (Mark Dirty / Clean / Send to Maintenance). | Create type, room, plan in UI. |
| 4 | Hotel Reservation rewrite: availability, rate, check-in, move-room, cancel. | Scenario steps 5 to 8 in section 3. |
| 5 | Billing: Receive Payment, billing summary, check-out + Sales Invoice, Issue hooks. | Steps 9 to 14. |
| 6 | Front Desk Console, Tape Chart, Availability, 4 reports, workspace. | Pages load, numbers correct. |
| 7 | Remove everything in section 10, clean `hooks.py`, run patches. | `bench migrate` + `bench start` without errors; section 9 grep is empty. |
| 8 | Tests + README rewrite (setup guide, one page). | Section 13. |
| 9 (optional) | New `demo_data.py` for the new schema; optional Quality Inspection on Mark Clean if verified feasible. | Demo loads / clears. |

---

## 13. Acceptance tests (must pass, write them in `hospitality_core/tests/test_flow.py`)

One end-to-end test that mirrors the user's flow:

1. Create Hotel Settings (company, default room item with HSN/SAC if India Compliance is installed).
2. Create 1 room type, 3 rooms, 1 rate plan (cheaper rate for a date range).
3. Create Customer (guest). Create reservation for 2 nights: rate must come from the plan.
4. Check in: room Occupied, reservation Checked In. Checking in a Dirty room must fail.
5. Create Issue with `hotel_room` = that room: room stays Occupied.
6. Move room to room 2: stay rows = 2, room 1 -> Out of Order (open Issue), room 2 Occupied.
7. Receive payment (Payment Entry with `hotel_reservation`): billing balance drops.
8. Check out with balance > 0: must fail. Pay the rest, check out: Sales Invoice submitted, paid, lines match the 2 segments,
   room 2 -> Dirty, status Checked Out.
9. Mark Clean room 2 -> Available. Resolve the Issue -> room 1 -> `status_after_maintenance`.
10. Send room 3 to maintenance: Out of Order and an Issue exists. Close the Issue: Available again.
11. Double booking the same room and dates must fail. Back-to-back stays must pass.

Also confirm: section 9 grep is empty, `bench --site frappe.com migrate` is clean, the Front Desk Console loads,
and all 4 reports run without errors.

---

## 14. Things to ask me if unclear (do not guess)

- Any extra front-desk page or report found in the inventory that is not in section 7.
- If `Allocate Advances Automatically` or the Quality Inspection fit differs from what this spec assumes in v17.
- If India Compliance (GST) is installed: which HSN/SAC and tax template to put in Hotel Settings.


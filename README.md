# Sky Hotel Management System (Hospitality Core)

Lean, standard-ERPNext-first hotel front-desk management application for Frappe / ERPNext.

---

## 1. Architecture Overview

Sky Hotel Management System replaces redundant custom accounting, folio, and maintenance doctypes with **standard ERPNext native workflows**:

- **Hotel Inventory & Stays**: Custom doctypes: `Hotel Room Type`, `Hotel Room`, `Room Rate Plan`, and `Hotel Reservation` (with `Hotel Reservation Stay` child table for room moves and rate tracking).
- **Guest Profiles**: Standard ERPNext **Customer** with custom fields (`is_hotel_guest`, `guest_id_type`, `guest_id_number`).
- **Billing & Folio**: Standard ERPNext **Payment Entry** (for advance or direct receipts) and **Sales Invoice** (automatically created & submitted at check-out, with advances automatically allocated).
- **Maintenance**: Standard ERPNext **Issue** with custom fields `hotel_room` and `hotel_reservation`. Rooms automatically transition to `Out of Order` upon opening issues and back to Available/Dirty upon resolution.
- **Housekeeping**: Handled directly on `Hotel Room` via statuses (`Available`, `Occupied`, `Dirty`, `Out of Order`) and Mark Dirty / Mark Clean actions with bulk list view support.
- **Zero Hardcoding**: All configurations (Company, Default Room Item, Taxes, Cost Center, Balances, Policies) live in the `Hotel Settings` single doctype.

---

## 2. Setup & Configuration Guide

### Step 1: Configure Hotel Settings
Navigate to **Hotel Settings** from the Hotel Workspace or Awesome Bar:
1. **Company**: Select your hotel company.
2. **Default Room Item**: Select the non-stock service Item representing room rent.
3. **Status After Maintenance**: Select whether rooms become `Available` or `Dirty` after maintenance issues are resolved.
4. **Billing & Controls**: Set `Block Check-out if Balance Remaining` and tolerance as needed.

### Step 2: Hotel Rooms & Types
1. Create **Hotel Room Type** records with default rates and room items.
2. Create **Hotel Room** records assigned to room types and floors.
3. (Optional) Set up **Room Rate Plan** records for date-range, customer-specific, or customer-group-specific discounted rates.

---

## 3. Operations Workflow

1. **New Reservation**: Create a `Hotel Reservation`. Select guest (Customer), Room Type, Room, and dates. Rates are resolved automatically.
2. **Check In**: Click **Check In** on arrival date. The room becomes `Occupied` and the reservation is marked `Checked In`.
3. **Move Room**: If a guest needs a room change, click **Move Room**. Old room becomes `Dirty` (or `Out of Order` if an issue is logged), and new room becomes `Occupied`.
4. **Receive Payment**: Click **Receive Payment** to open a standard `Payment Entry` tied to the reservation.
5. **Check Out**: Click **Check Out**. System validates outstanding balance, generates and submits a standard `Sales Invoice`, auto-allocates payments, and sets the room to `Dirty`.
6. **Housekeeping**: Mark rooms clean individually or using the **Mark Clean** action in the Hotel Room list.

---

## 4. Running Acceptance Tests

Run the full end-to-end lifecycle and report test suite via bench:

```bash
bench --site <site-name> execute "frappe.get_attr('hospitality_core.tests.run.run_all')()"
```
# Hotel-Management-System-ERPNext
# Hotel-Management-System-ERPNext

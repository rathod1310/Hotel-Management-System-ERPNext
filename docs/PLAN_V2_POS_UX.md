# Hospitality Core v2: Implementation Plan
## (1) Standard ERPNext POS: Restaurant + Room orders, (2) Single-screen, popup-only Front Desk Console

Put this file in the repo as `docs/PLAN_V2_POS_UX.md`. It builds on `docs/REFACTOR_SPEC.md` (v1), which is
**complete and working**. Do not change v1 behaviour except where this plan says so.

---

## 0. Master Prompt (paste into Antigravity)

```
Read docs/REFACTOR_SPEC.md (v1, already implemented) and docs/PLAN_V2_POS_UX.md (this plan).
Implement PLAN_V2 phase by phase. After each phase: run its verification, show the output, git commit.

Rules:
1. Tag the current state `v1-stable` BEFORE changing anything.
2. Use the STANDARD ERPNext POS (point-of-sale page, POS Profile, POS Opening / Closing Entry). Do not build a custom POS.
3. Nothing hardcoded (company, item, profile, account, mode of payment names). Config lives in Hotel Settings.
4. Section 2 lists facts I verified in ERPNext v17 develop source. RE-VERIFY each one in
   ~/frappe-bench/apps/erpnext before relying on it. If something differs, stop and tell me.
5. The Front Desk Console must never navigate away (section 6). No frappe.set_route, no links to Desk forms.
6. Keep every v1 acceptance test green.
```

---

## 1. What we are building

| # | Requirement (from the user) | Outcome |
|---|-----------------------------|---------|
| 1 | POS has **2 types**: Restaurant and Room, using the **default ERPNext POS** | Two POS Profiles (names configured in Hotel Settings) on the standard POS page. |
| 2 | Room orders can be **paid or not paid** | Paid: normal "Complete Order". Not paid: **Charge to Room**. |
| 3 | Unpaid room orders **go into the checkout Sales Invoice automatically** | At check-out the room-service lines are merged into the stay invoice. One invoice, one payment. |
| 4 | **Everything from the Front Desk Console, no redirects**, all entry through popups | Single-screen console with dialogs for every action. Standard POS opens as an in-console overlay. |
| 5 | A proper user experience | Section 6 (layout, dialogs, states, shortcuts). |

---

## 2. Verified facts about ERPNext v17 develop (commit 23e6d4d, Nov 2026)

Read from source, not from memory. **Re-verify locally.**

1. **POS Settings has `invoice_type`, default `Sales Invoice`.** In that mode POS creates a **Sales Invoice**
   (`is_pos`, `is_created_using_pos = 1`, `pos_profile` set). Creating a `POS Invoice` is blocked
   ("Sales Invoice mode is activated in POS"). **This plan targets Sales Invoice mode. Do not switch to POS Invoice mode.**
2. **POS Profile** fields we use: `customer`, `company`, `payments` (Table POS Payment Method), `warehouse`,
   `update_stock` (default 1), `taxes_and_charges`, `income_account`, `cost_center`, `selling_price_list`,
   `item_groups`, `applicable_for_users`, **`allow_partial_payment`** (default 0).
3. With `allow_partial_payment = 0` the POS UI refuses "Complete Order" with zero payment, and the server throws
   `PartialPaymentValidationError` on submit. So an unpaid order **cannot be submitted** on a normal profile.
4. In the POS UI, pressing **Checkout saves the invoice as a Draft** (`save_and_checkout`). Drafts appear under
   **Recent Orders** and can be edited or deleted by the cashier.
5. POS needs an open **POS Opening Entry** for (user, profile). Required fields: `period_start_date`, `posting_date`,
   `company`, `pos_profile`, `user`, `balance_details`.
6. Frappe supports `page_js = {"point-of-sale": "public/js/..."}` in `hooks.py` to extend a standard page.
7. The POS payment screen has the DOM element `.submit-order-btn` ("Complete Order"). An extension can add a sibling button.
8. `POS Closing Entry` only works with **submitted** invoices created via POS. Draft invoices are ignored by it (verify).

---

## 3. Architecture decisions

### 3.1 Two POS Profiles, configured in Hotel Settings

Add to **Hotel Settings**:

| Field | Type | Meaning |
|-------|------|---------|
| `restaurant_pos_profile` | Link POS Profile | profile used for restaurant counter sales |
| `room_pos_profile` | Link POS Profile | profile used for in-room orders |
| `update_stock_on_checkout` | Check | default off. If on, merged lines are stock-deducted on the checkout invoice |
| `console_refresh_seconds` | Int | default 60 |
| `default_advance_mode` | Link Mode of Payment | pre-selected in payment dialogs |

A button **Create POS Profiles** in Hotel Settings creates the two profiles from existing settings
(company, warehouse, price list, payment methods chosen in a dialog) so the user does not hand-build them.
Profile **names are never hardcoded**; code always reads them from Hotel Settings.

Both profiles: `allow_partial_payment = 0`. Room profile: `customer` empty (the guest is picked per order).

### 3.2 Room order lifecycle (the core idea)

| Case | What the cashier does in POS | What the system stores | Effect on the bill |
|------|------------------------------|------------------------|--------------------|
| **Restaurant order** (restaurant profile) | normal sale, Complete Order | submitted, paid Sales Invoice, `hotel_order_type = Restaurant` | none, not linked to a stay |
| **Room order, paid now** | pick the in-house guest, Complete Order with a payment | submitted, paid Sales Invoice, `hotel_reservation` = stay, `hotel_order_type = Room Service` | none (already paid). Shown on the console as "paid room orders (info)" |
| **Room order, not paid** | pick the guest, press **Charge to Room** | **Draft** Sales Invoice, `charge_to_room = 1`, `hotel_reservation` = stay | merged into the checkout Sales Invoice, draft then deleted |

**Why a draft and not a submitted unpaid invoice:** a submitted POS Sales Invoice is a real accounting document
(revenue + receivable) and would be counted again when we build the checkout invoice. A flagged draft has no GL,
no stock and no revenue until it is merged, so revenue is recognised **once**, on the checkout invoice.
(Fallback if drafts prove unworkable: section 9, R2.)

### 3.3 Custom Fields (create in `setup/custom_fields.py`, add a patch)

| Doctype | Fieldname | Type | Notes |
|---------|-----------|------|-------|
| Sales Invoice | `hotel_reservation` | Link Hotel Reservation | already exists in v1 |
| Sales Invoice | `hotel_order_type` | Select: Restaurant, Room Service, Stay Checkout | set by hooks, read only |
| Sales Invoice | `charge_to_room` | Check, read only | set only by the Charge to Room action |
| Sales Invoice Item | `hotel_source_invoice` | Data, read only | traces merged lines back to the draft |

### 3.4 Hooks on Sales Invoice (`hospitality_core/pos.py`)

Only act when `doc.pos_profile` equals `room_pos_profile` (read from Hotel Settings) or `restaurant_pos_profile`.

- **validate (room profile):** resolve the guest's **Checked In** reservation from `doc.customer`;
  set `hotel_reservation`, `hotel_order_type = Room Service`. If none: throw "Guest is not checked in".
  If the customer has several in-house reservations, pick the one whose current room matches (the console can pass it).
- **validate (restaurant profile):** set `hotel_order_type = Restaurant`.
- **before_submit:** if `charge_to_room` is set, throw "Room charges are billed at check-out. Delete the flag or pay the order".
  This stops anyone submitting a charge-to-room draft as an invoice by accident.
- **Reservation lifecycle guards:** a room order cannot be created for a reservation that is not Checked In,
  and after check-out starts the reservation is locked (section 5.3).

Whitelisted API in `pos.py`:

```
charge_to_room(invoice_name)        # validates in-house guest + draft state, sets charge_to_room = 1, saves
get_in_house_guests()               # [{customer, guest_name, room, reservation}] for the POS guest picker
unflag_charge_to_room(invoice_name) # cashier changes mind; draft stays a normal draft
get_pending_room_orders(reservation)  # drafts flagged for a stay, with items and totals
```

### 3.5 POS page extension (`public/js/pos_extension.js`, loaded via `page_js`)

Small and defensive. Everything is wrapped so an ERPNext change cannot break the standard POS.

- When the active POS Profile is the **room profile**, add a **Charge to Room** button next to `.submit-order-btn`.
  Click: confirm dialog "Charge N items (total) to Room 101 (Guest)?" then `charge_to_room`, success toast, start a new order.
- Add an **In-House Guest** picker above the customer field (list from `get_in_house_guests`, shown as "101 · Rahul Shah").
  Selecting sets the customer on the current invoice form.
- When loaded inside the console overlay (`window.self !== window.top`): add a body class `hotel-embedded`
  that hides the Desk navbar and sidebar so the POS fills the overlay.
- All DOM hooks are optional. If a selector is missing, log a warning and fall back to the plain POS (still works,
  only the extra button is missing and the console shows a banner explaining the manual alternative).

### 3.6 Billing integration (change `build_sales_invoice` from v1)

1. After the room-night lines, append lines from every draft where
   `hotel_reservation = name AND charge_to_room = 1 AND docstatus = 0 AND is_created_using_pos = 1`.
   Copy `item_code, item_name, description, qty, uom, rate, discount_percentage, discount_amount, cost_center`;
   set `hotel_source_invoice = draft name`. An invoice-level discount on a draft is spread across its lines as
   `discount_percentage` (verify the result equals the draft's grand total).
2. `estimated_total` / `balance` in the billing summary include these lines (preview only, nothing is inserted or deleted).
3. `check_out()`: inside one transaction: lock the reservation row (`for_update`), build, insert and submit the invoice,
   allocate advances, then **delete the merged drafts** and add a Comment on the invoice
   ("Merged room orders: SINV-xxx, SINV-yyy"). Any failure rolls back everything, including the deletes.
4. Taxes: room-night items and food items usually have different GST rates. Use **Item Tax Templates on the items**
   (verify the invoice picks them up together with `taxes_and_charges`). If the standard behaviour cannot do it cleanly,
   report back before inventing a workaround.
5. Stock: if merged items are stock items and `update_stock_on_checkout` is off, no stock moves. Document this in the README.
   Recommendation to the user: kitchen/food items are non-stock service items.

### 3.7 Reservation additions (v1 doctype)

Read-only computed fields shown in the Billing section: `room_service_pending` (sum of flagged drafts),
`room_service_paid` (sum of paid room orders, info only). Both come from `get_billing_summary`.

---

## 4. Backend for the console (`hospitality_core/api/console.py`)

Design goal: **one call to paint the screen, one small call per action.**

| Method | Returns |
|--------|---------|
| `get_console_data(date)` | `{kpis, rooms[], arrivals[], departures[], in_house[], dirty[], maintenance[], settings}` in a single payload |
| `search(text)` | guests, reservations, rooms matching, for the global search box |
| `get_available_rooms(room_type, check_in, check_out)` | free rooms with the resolved rate (reuse v1) |
| `create_reservation(data, advance=None)` | reservation + optional advance Payment Entry in one transaction |
| `walk_in(data, advance=None)` | create + check in in one step |
| `check_in`, `move_room`, `cancel_reservation`, `extend_stay` | the changed reservation + changed rooms (delta) |
| `get_bill_preview(reservation)` | line list (room nights, room service lines), taxes, total, paid, balance |
| `receive_payment(reservation, mode, amount, reference)` | creates and submits the standard Payment Entry, returns new balance |
| `check_out(reservation, collect=None)` | optional payment, invoice, status change; returns invoice name + print URL |
| `report_issue(room, subject, priority)`, `resolve_issue(issue)` | the standard Issue; room status delta |
| `set_housekeeping(room, "Dirty"/"Clean")` | room delta |
| `ensure_pos_opening(profile)` | returns an open POS Opening Entry for (user, profile), creating one with zero balances if allowed |

Every action returns the **changed records** so the UI updates in place without a full reload.
After each change call `frappe.publish_realtime("hotel_console_update", {...})` so a second screen
(housekeeping tablet, another receptionist) refreshes by itself.

---

## 5. Front Desk Console design

### 5.1 Screen layout

```
+----------------------------------------------------------------------------------+
|  Sky Hotel  | < Thu 05 Nov 2026 > Today | [ search guest / room / reservation ]  |
|  [+ Reservation] [+ Walk-in] [Restaurant POS] [Room Service POS]     (refresh)    |
+----------------------------------------------------------------------------------+
|  Arrivals 4 | Departures 3 | In-house 12 | Available 6 | Dirty 2 | OOO 1 | Occ 60% |
+----------------------------------------------------------------------------------+
|  [Rooms] [Arrivals] [In-House] [Departures] [Reservations] [Tape Chart] [HK] [Maint]|
+----------------------------------------------------------------------------------+
|  Floor 1                                                                          |
|  +-----+ +-----+ +-----+ +-----+      Room card:                                  |
|  |101  | |102  | |103  | |104  |      number, type, status colour,                |
|  |Occ  | |Avail| |Dirty| |OOO  |      guest name, balance chip,                   |
|  |Rahul| |     | |     | |     |      "room service Rs X" chip                    |
|  |Rs500| |     | |     | |     |                                                  |
|  +-----+ +-----+ +-----+ +-----+                                                  |
+----------------------------------------------------------------------------------+
```

- **Rooms** tab is the default: cards grouped by floor, filter chips (status, room type), colours identical to the
  housekeeping colours of v1 (green Available, yellow Dirty, dark grey Occupied, red Out of Order, blue Reserved today).
- Clicking a card opens the **Room Dialog** (5.2). Clicking a KPI filters the board / switches tab.
- Arrivals / In-House / Departures / Reservations are in-page tables with row actions (same dialogs).
- **Tape Chart** and **Availability** become tabs (reuse existing code, rendered in the console).
- Reports needed in daily work (House List, Daily Arrivals / Departures, Room Availability) open as **in-page tables**
  with Print and Export CSV, not as Desk report routes.
- Small screens (tablet): cards reflow; HK tab is touch-friendly (large Mark Clean button).

### 5.2 Context actions (inside the Room Dialog and table row menus)

| Room / stay state | Actions offered |
|-------------------|-----------------|
| Available | New Reservation, Walk-in, Send to Maintenance, Mark Dirty |
| Reserved (arriving) | Check In, Edit dates, Cancel |
| Occupied | Room Order (POS), Receive Payment, Move Room, Extend Stay, Report Issue, View Bill, Check Out |
| Dirty | Mark Clean |
| Out of Order | Open Issue summary, Resolve Issue |

### 5.3 Dialog catalogue (all `frappe.ui.Dialog`, never a Desk form)

| Dialog | Contents and behaviour |
|--------|------------------------|
| **New Reservation** | Customer field with inline "Create new guest" (name, phone, ID type, ID number); date range with chips (Today, +1, +2 nights); room type; **live list of free rooms with rate** that refreshes when dates / type change; adults / children; optional **advance payment** block (mode, amount). Save creates everything in one call. |
| **Walk-in** | Same as New Reservation, arrival = today, one button **Create and Check In**. |
| **Check In** | Shows guest, room, nights, rate. Capture ID details if missing. Optional advance. Button **Check In**. If the room is not ready it explains why and offers a different Available room. |
| **Move Room** | New room (free rooms only, with rate), reason, "keep the same rate" toggle. |
| **Receive Payment** | Mode (default from settings), amount (default = balance), reference no. Shows the new balance after submit. |
| **Room Order** | Opens the **POS overlay** (5.4) on the room profile with the guest pre-selected. |
| **Bill / Check Out** | A bill preview table: room-night lines, **room-service lines** (from flagged drafts, labelled with their order no.), taxes, total, paid, balance. If balance > tolerance and blocking is on: an inline **Collect payment** row. Button **Check Out and Print Invoice**. |
| **Extend Stay / Edit Dates** | New departure date, shows availability conflicts. |
| **Cancel Reservation** | Reason, shows advance paid, warns that flagged room orders will be deleted (needs a tick to confirm). |
| **Report Issue / Resolve Issue** | Subject, priority, description; resolve with notes. Room status updates in place. |
| **Housekeeping** | No dialog: one click on the card or table row, toast with Undo for 5 seconds. |

### 5.4 POS inside the console (no redirect)

- Buttons **Restaurant POS** and **Room Service POS** (top bar and Room Dialog) open a **full-screen overlay**
  containing the standard POS page in an `<iframe src="/app/point-of-sale">`, with a **Close** button that returns
  to the console exactly as it was, then triggers a data refresh.
- Before opening, call `ensure_pos_opening(profile)` so the cashier never sees the opening-entry popup mid-flow
  (if the user has no open entry and the setting forbids auto-open, show our own dialog with opening balances).
- The profile is selected automatically (from Hotel Settings). The cashier only picks the guest (room profile).
- **Verify before building:** nginx / Frappe send `X-Frame-Options` and CSP headers that allow same-origin framing
  (they normally do: `SAMEORIGIN`). Test in the local bench.
- **Fallback if framing fails:** open the standard POS in a **new browser tab** (`window.open(url, "_blank")`);
  the console stays open and refreshes when the tab is closed or on focus. Record this in the README.

### 5.5 UX rules (acceptance-checkable)

1. **No navigation.** In `console/` there must be no `frappe.set_route`, `window.location`, `<a href>` to `/app/...`,
   or `frappe.new_doc`. The only allowed exceptions: the POS fallback tab (5.4) and the print view of the final invoice
   (opens in a popup window).
2. Every action: optimistic UI, spinner on the button, success toast, **in-place refresh** of the affected card / row.
3. Errors show plain-language messages with what to do next (e.g. "Room 101 is Dirty. Mark it clean or pick another room"),
   never a raw traceback.
4. Defaults from Hotel Settings; autofocus on the first useful field; Enter submits; Esc closes.
5. Keyboard: `N` new reservation, `W` walk-in, `/` focus search, `R` refresh.
6. Skeleton loaders on first paint; real empty states ("No arrivals today") instead of blank panels.
7. Auto-refresh every `console_refresh_seconds` and instantly on the realtime event.
8. Works in light / dark theme (use Frappe CSS variables), and on a tablet width.
9. Dialogs may stack (e.g. Check Out > Collect payment) but never more than 2 levels.

### 5.6 Code layout

```
hospitality_core/
  api/console.py                    # section 4
  pos.py                            # hooks + POS API (section 3.4)
  public/js/pos_extension.js        # section 3.5
  hospitality_core/page/front_desk_console/
    front_desk_console.js           # bootstraps, state store, realtime, router-free tab switch
    console/board.js  console/tables.js  console/tapechart.js  console/kpis.js
    console/dialogs/{reservation,walkin,checkin,move,payment,bill_checkout,extend,cancel,issue}.js
    console/pos_overlay.js
    console/ui.js                   # toast, confirm, skeleton, shortcuts, helpers
    front_desk_console.css
```

Remove the old console buttons that routed away (Tape Chart, Availability, Housekeeping, Reservations, House List,
Maintenance) and the pages / reports they pointed to once their content lives in tabs.

---

## 6. Phases (commit after each, show verification output)

| Phase | Work | Verification |
|-------|------|--------------|
| P0 | `git tag v1-stable`. Re-verify section 2 facts in local ERPNext source and write findings to `docs/V2_VERIFICATION.md`. | I read the file before P1. |
| P1 | Hotel Settings additions, custom fields (3.3), **Create POS Profiles** button, patch. | `bench migrate`; Settings form works; two profiles created. |
| P2 | `pos.py` hooks and API; extend `build_sales_invoice` and `check_out` to merge flagged drafts; billing summary fields. | Python tests: scenarios A to E (section 7). |
| P3 | `pos_extension.js`: Charge to Room button, in-house guest picker, embedded mode. | Manual: charge a draft to a room from the real POS page. |
| P4 | `api/console.py` with delta responses and realtime events. | API tests; one `get_console_data` call renders everything. |
| P5 | Console shell: top bar, KPI strip, Room Board, tabs, tables, Tape Chart and Availability tabs. | Screenshots of each tab; no console errors. |
| P6 | All dialogs (5.3) including bill preview and inline payment. | Manual script F (section 7). |
| P7 | POS overlay, `ensure_pos_opening`, fallback tab. | Open both POS types from the console and complete an order each. |
| P8 | Remove redirects and obsolete pages; grep checks; update the User Guide; README. | Section 7 checks all green. |

---

## 7. Acceptance tests

**Automated (extend `tests/test_flow.py`):**

| ID | Scenario | Expected |
|----|----------|----------|
| A | Restaurant order paid in the restaurant profile | submitted, paid Sales Invoice, `hotel_order_type = Restaurant`, not linked to a stay |
| B | Room order paid now (in-house guest) | submitted, `hotel_reservation` set, **not** in the checkout invoice, shown as info |
| C | Room order Charge to Room, then check-out | draft flagged; checkout invoice contains its lines with `hotel_source_invoice`; draft deleted; invoice total = nights + order; revenue counted once |
| D | Two unpaid room orders + one advance payment | checkout invoice has both orders; advance auto-allocated; balance correct |
| E | Room order for a guest not checked in / after check-out | blocked with the clear message |
| F | Submit a `charge_to_room` draft manually | blocked by `before_submit` |
| G | Cancel a reservation that has flagged drafts | drafts deleted only after confirmation |
| H | v1 flow (steps 1 to 14) | still green |

**Manual UX checklist (F):** from the console only, with no page navigation: create a reservation with an advance,
check in, take a room order from POS and charge it to room, take another and pay it, move the room, report an issue,
receive a payment, open the bill (both room orders visible as expected), check out, mark the room clean, resolve the issue.
Reload the browser at any point: the console state is rebuilt from the server.

**Static checks:**

```bash
cd ~/frappe-bench/apps/hospitality_core/hospitality_core
grep -rnE "set_route|window\.location|frappe\.new_doc|href=\"/app" hospitality_core/page/front_desk_console   # empty, except POS fallback
grep -rniE "Edo Heritage|ROOM-RENT|Main Reception|\"Restaurant\"|\"Room Service\"" . --include=*.py --include=*.js   # no profile / company names hardcoded
```

---

## 8. Edge cases and decisions

| Case | Decision |
|------|----------|
| Abandoned or mistaken room-profile drafts | Only drafts with `charge_to_room = 1` are billed. Unflagged drafts are ignored and shown on the console as "Unconfirmed drafts (n)" with a Clean up button. |
| Guest changes room mid-stay | Drafts belong to the reservation, not the room: no effect. |
| Order edited after Charge to Room | Allowed while draft; flag stays. The bill preview always reads the current draft. |
| Cashier wants to undo | `unflag_charge_to_room` or delete the draft in POS Recent Orders. |
| Check-out already running | Lock the reservation row (`for_update`) in `check_out` and in `charge_to_room`; the loser gets "Check-out in progress". |
| POS Closing Entry at shift end | Flagged drafts must not block it. Verify drafts are ignored (fact 8). |
| Returns and refunds | Standard POS return, out of scope. |
| Permissions | Role `Hospitality User` needs the POS, Sales Invoice, Payment Entry, Issue, Customer permissions. Add Custom DocPerms in `custom_fields.py`; add users in each POS Profile's `applicable_for_users`. |
| Restaurant guest who wants to charge to room | Out of scope for v2 (restaurant profile is always paid). Easy later extension. |

---

## 9. Risks and fallbacks

| # | Risk | Fallback |
|---|------|----------|
| R1 | POS page cannot be framed in the console | New-tab fallback (5.4). Same functionality, slightly less seamless. |
| R2 | Draft-as-unpaid is not workable (for example if the POS UI cannot leave drafts reliably) | Enable `allow_partial_payment` on the room profile and submit an **unpaid** Sales Invoice. At check-out do not merge; instead **allocate the guest's payment to both invoices** and show them together in the bill. Needs my approval first. |
| R3 | The POS extension selectors change in a future ERPNext version | The extension degrades to plain POS (3.5). Keep selectors in one config object at the top of the file. |
| R4 | Mixed GST rates on one invoice | Item Tax Templates per item; if the standard invoice cannot apply them with a header template, report back. |
| R5 | Stock-tracked food items | Documented; default is no stock movement on checkout. |

---

## 10. Questions to ask me if unclear (do not guess)

- If section 2 facts differ in the local ERPNext source.
- GST: which tax template and Item Tax Templates to use for room vs food items.
- Whether restaurant orders should ever be chargeable to a room.

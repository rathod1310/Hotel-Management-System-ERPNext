import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, now_datetime, add_days, date_diff
from hospitality_core.constants import RoomStatus, ReservationStatus
from hospitality_core.utils import get_settings, get_company
from hospitality_core.room_status import set_room_status
from hospitality_core.hospitality_core.doctype.hotel_reservation.hotel_reservation import (
    get_available_rooms as v1_get_available_rooms,
    get_billing_summary,
    check_in as v1_check_in,
    move_room as v1_move_room,
    cancel_reservation as v1_cancel_reservation,
    check_out as v1_check_out,
    get_room_rate
)


def emit_console_update(event_type, data):
    """Publishes realtime update to all connected front desk consoles"""
    try:
        frappe.publish_realtime("hotel_console_update", {"type": event_type, "data": data})
    except Exception:
        pass


@frappe.whitelist()
def get_console_data(target_date=None):
    """
    Returns single consolidated payload for the entire front desk console:
    {kpis, rooms[], arrivals[], departures[], in_house[], dirty[], maintenance[], settings}
    """
    target_date = getdate(target_date) if target_date else getdate(nowdate())
    settings = get_settings()
    company = settings.company or get_company()

    # 1. Rooms
    rooms = frappe.get_all(
        "Hotel Room",
        fields=["name", "room_number", "room_type", "floor", "status", "current_reservation", "notes"],
        filters={"is_enabled": 1},
        order_by="floor asc, room_number asc"
    )

    # Attach guest details & pending charges to occupied/reserved rooms
    room_map = {r.name: r for r in rooms}
    active_reservations = frappe.db.sql("""
        SELECT r.name, r.customer, c.customer_name as guest_name, r.room, r.room_type,
               r.check_in_date, r.check_out_date, r.status, r.balance
        FROM `tabHotel Reservation` r
        LEFT JOIN `tabCustomer` c ON c.name = r.customer
        WHERE r.status IN ('Reserved', 'Checked In')
    """, as_dict=True)

    res_by_room = {r.room: r for r in active_reservations if r.room}

    # Pending room service drafts
    room_service_totals = frappe.db.sql("""
        SELECT hotel_reservation, SUM(grand_total) as total
        FROM `tabSales Invoice`
        WHERE charge_to_room = 1 AND docstatus = 0
        GROUP BY hotel_reservation
    """, as_dict=True)
    rs_by_res = {rs.hotel_reservation: flt(rs.total, 2) for rs in room_service_totals}

    for r in rooms:
        res = res_by_room.get(r.name)
        if res:
            r["guest_name"] = res.guest_name
            r["customer"] = res.customer
            r["reservation_status"] = res.status
            r["balance"] = flt(res.balance, 2)
            r["room_service_pending"] = rs_by_res.get(res.name, 0.0)
            r["check_in_date"] = res.check_in_date
            r["check_out_date"] = res.check_out_date
        else:
            r["guest_name"] = None
            r["customer"] = None
            r["reservation_status"] = None
            r["balance"] = 0.0
            r["room_service_pending"] = 0.0
            r["check_in_date"] = None
            r["check_out_date"] = None

    # 2. Arrivals (expected on target_date)
    arrivals = frappe.db.sql("""
        SELECT r.name, r.customer, c.customer_name as guest_name, r.room, r.room_type,
               r.check_in_date, r.check_out_date, r.status, r.estimated_total, r.total_paid, r.balance
        FROM `tabHotel Reservation` r
        LEFT JOIN `tabCustomer` c ON c.name = r.customer
        WHERE r.check_in_date = %s
        AND r.status = 'Reserved'
        ORDER BY r.name ASC
    """, (target_date,), as_dict=True)

    # 3. Departures (due on target_date)
    departures = frappe.db.sql("""
        SELECT r.name, r.customer, c.customer_name as guest_name, r.room, r.room_type,
               r.check_in_date, r.check_out_date, r.status, r.balance
        FROM `tabHotel Reservation` r
        LEFT JOIN `tabCustomer` c ON c.name = r.customer
        WHERE r.check_out_date = %s
        AND r.status = 'Checked In'
        ORDER BY r.room ASC
    """, (target_date,), as_dict=True)

    # 4. In-House (currently Checked In)
    in_house = frappe.db.sql("""
        SELECT r.name, r.customer, c.customer_name as guest_name, r.room, r.room_type,
               r.check_in_date, r.check_out_date, r.status, r.balance
        FROM `tabHotel Reservation` r
        LEFT JOIN `tabCustomer` c ON c.name = r.customer
        WHERE r.status = 'Checked In'
        ORDER BY r.room ASC
    """, as_dict=True)
    for inh in in_house:
        inh["room_service_pending"] = rs_by_res.get(inh.name, 0.0)

    # 5. Dirty rooms
    dirty_rooms = [r for r in rooms if r.status == RoomStatus.DIRTY]

    # 6. Maintenance / Issues
    maintenance_issues = frappe.db.sql("""
        SELECT name, subject, hotel_room, status, priority, creation
        FROM `tabIssue`
        WHERE hotel_room IS NOT NULL AND status IN ('Open', 'Replied', 'Hold')
        ORDER BY creation DESC
    """, as_dict=True)

    # 7. KPIs
    total_rooms = len(rooms)
    occupied_count = len([r for r in rooms if r.status == RoomStatus.OCCUPIED])
    available_count = len([r for r in rooms if r.status == RoomStatus.AVAILABLE])
    dirty_count = len(dirty_rooms)
    ooo_count = len([r for r in rooms if r.status == RoomStatus.OUT_OF_ORDER])
    reserved_count = len([r for r in rooms if r.status == RoomStatus.RESERVED])
    occupancy_pct = flt((occupied_count / total_rooms) * 100, 1) if total_rooms > 0 else 0.0

    kpis = {
        "arrivals": len(arrivals),
        "departures": len(departures),
        "in_house": len(in_house),
        "available": available_count,
        "dirty": dirty_count,
        "ooo": ooo_count,
        "reserved": reserved_count,
        "occupancy_pct": occupancy_pct,
        "total_rooms": total_rooms
    }

    return {
        "target_date": target_date,
        "kpis": kpis,
        "rooms": rooms,
        "arrivals": arrivals,
        "departures": departures,
        "in_house": in_house,
        "dirty": dirty_rooms,
        "maintenance": maintenance_issues,
        "settings": {
            "company": company,
            "restaurant_pos_profile": settings.restaurant_pos_profile,
            "room_pos_profile": settings.room_pos_profile,
            "default_advance_mode": settings.default_advance_mode or "Cash",
            "console_refresh_seconds": settings.console_refresh_seconds or 60
        }
    }


@frappe.whitelist()
def search(text):
    """Global search across guests, rooms, and reservations."""
    if not text or len(text.strip()) < 2:
        return []

    q = f"%{text.strip()}%"
    results = []

    # Search Rooms
    rooms = frappe.db.sql("""
        SELECT name, room_number, room_type, status, current_reservation
        FROM `tabHotel Room`
        WHERE room_number LIKE %s OR name LIKE %s
        LIMIT 5
    """, (q, q), as_dict=True)
    for r in rooms:
        results.append({
            "type": "Room",
            "label": f"Room {r.room_number} ({r.status})",
            "value": r.name,
            "details": r.room_type,
            "doc": r
        })

    # Search Reservations
    reservations = frappe.db.sql("""
        SELECT r.name, r.customer, c.customer_name, r.room, r.status
        FROM `tabHotel Reservation` r
        LEFT JOIN `tabCustomer` c ON c.name = r.customer
        WHERE r.name LIKE %s OR r.customer LIKE %s OR c.customer_name LIKE %s
        LIMIT 5
    """, (q, q, q), as_dict=True)
    for res in reservations:
        results.append({
            "type": "Reservation",
            "label": f"{res.name} · {res.customer_name or res.customer} (Room {res.room or 'Unassigned'})",
            "value": res.name,
            "details": res.status,
            "doc": res
        })

    # Search Guests
    customers = frappe.db.sql("""
        SELECT name, customer_name, guest_id_number, mobile_no
        FROM `tabCustomer`
        WHERE is_hotel_guest = 1 AND (customer_name LIKE %s OR name LIKE %s OR guest_id_number LIKE %s)
        LIMIT 5
    """, (q, q, q), as_dict=True)
    for c in customers:
        results.append({
            "type": "Guest",
            "label": f"Guest: {c.customer_name or c.name}",
            "value": c.name,
            "details": f"ID: {c.guest_id_number or '-'}",
            "doc": c
        })

    return results


@frappe.whitelist()
def get_available_rooms(room_type, check_in_date, check_out_date, exclude_reservation=None):
    rooms = v1_get_available_rooms(room_type, check_in_date, check_out_date, exclude_reservation)
    rate = get_room_rate(room_type, check_in_date)
    for r in rooms:
        r["rate"] = rate
    return rooms


@frappe.whitelist()
def create_reservation(data, advance=None):
    if isinstance(data, str):
        data = frappe.parse_json(data)
    if isinstance(advance, str) and advance:
        advance = frappe.parse_json(advance)

    # 1. Inline Guest Creation if needed
    customer = data.get("customer")
    guest_name = data.get("guest_name")
    if not customer and guest_name:
        cust_doc = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": guest_name,
            "customer_type": "Individual",
            "is_hotel_guest": 1,
            "guest_id_type": data.get("guest_id_type"),
            "guest_id_number": data.get("guest_id_number"),
            "mobile_no": data.get("mobile_no")
        })
        cust_doc.insert(ignore_permissions=True)
        customer = cust_doc.name

    data["customer"] = customer
    data["doctype"] = "Hotel Reservation"
    res_doc = frappe.get_doc(data)
    res_doc.insert(ignore_permissions=True)

    # 2. Advance Payment if provided
    payment_entry_name = None
    if advance and flt(advance.get("amount")) > 0:
        company = res_doc.company or get_company()
        company_doc = frappe.get_doc("Company", company)
        mode = advance.get("mode") or get_settings().default_advance_mode or "Cash"
        paid_to = frappe.db.get_value("Mode of Payment Account", {"parent": mode, "company": company}, "default_account") or company_doc.default_cash_account
        paid_from = company_doc.default_receivable_account

        pe = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "party_type": "Customer",
            "party": customer,
            "company": company,
            "hotel_reservation": res_doc.name,
            "mode_of_payment": mode,
            "paid_to": paid_to,
            "paid_from": paid_from,
            "paid_amount": flt(advance.get("amount")),
            "received_amount": flt(advance.get("amount")),
            "reference_no": advance.get("reference_no")
        })
        pe.insert(ignore_permissions=True)
        pe.submit()
        payment_entry_name = pe.name

    billing = get_billing_summary(res_doc.name)
    emit_console_update("reservation_created", {"reservation": res_doc.name, "room": res_doc.room})

    return {
        "reservation": res_doc.as_dict(),
        "billing": billing,
        "payment_entry": payment_entry_name
    }


@frappe.whitelist()
def walk_in(data, advance=None):
    """Creates a reservation and immediately checks in the guest in one step."""
    if isinstance(data, str):
        data = frappe.parse_json(data)

    data["check_in_date"] = nowdate()
    res_out = create_reservation(data, advance)
    res_name = res_out["reservation"]["name"]

    # Check in
    v1_check_in(res_name)
    res_doc = frappe.get_doc("Hotel Reservation", res_name)
    emit_console_update("walk_in_completed", {"reservation": res_name, "room": res_doc.room})

    return {
        "reservation": res_doc.as_dict(),
        "billing": get_billing_summary(res_name)
    }


@frappe.whitelist()
def check_in(reservation_name):
    res = v1_check_in(reservation_name)
    res_doc = frappe.get_doc("Hotel Reservation", reservation_name)
    emit_console_update("check_in", {"reservation": reservation_name, "room": res_doc.room})
    return {"status": "success", "reservation": res_doc.as_dict()}


@frappe.whitelist()
def move_room(reservation_name, new_room, reason=None, keep_rate=0):
    res = v1_move_room(reservation_name, new_room, reason, keep_rate)
    res_doc = frappe.get_doc("Hotel Reservation", reservation_name)
    emit_console_update("move_room", {"reservation": reservation_name, "new_room": new_room})
    return {"status": "success", "reservation": res_doc.as_dict()}


@frappe.whitelist()
def cancel_reservation(reservation_name, reason=None):
    res = v1_cancel_reservation(reservation_name)
    emit_console_update("cancel_reservation", {"reservation": reservation_name})
    return {"status": "success"}


@frappe.whitelist()
def extend_stay(reservation_name, new_check_out_date):
    res = frappe.get_doc("Hotel Reservation", reservation_name)
    new_date = getdate(new_check_out_date)
    if new_date <= getdate(res.check_in_date):
        frappe.throw(_("New check out date must be after check in date."))

    res.check_out_date = new_date
    res.save(ignore_permissions=True)
    billing = get_billing_summary(res.name)
    emit_console_update("extend_stay", {"reservation": reservation_name})
    return {"status": "success", "reservation": res.as_dict(), "billing": billing}


@frappe.whitelist()
def get_bill_preview(reservation_name):
    from hospitality_core.hospitality_core.doctype.hotel_reservation.hotel_reservation import build_sales_invoice
    inv = build_sales_invoice(reservation_name)
    billing = get_billing_summary(reservation_name)

    items = []
    for item in inv.items:
        items.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "qty": item.qty,
            "rate": item.rate,
            "amount": item.amount,
            "discount_percentage": item.discount_percentage,
            "source": item.hotel_source_invoice or "Room Night"
        })

    return {
        "reservation": reservation_name,
        "items": items,
        "taxes": [{"description": t.description, "tax_amount": t.tax_amount} for t in inv.taxes],
        "grand_total": inv.grand_total,
        "total_paid": billing["total_paid"],
        "balance": billing["balance"],
        "room_service_pending": billing.get("room_service_pending", 0.0),
        "room_service_paid": billing.get("room_service_paid", 0.0)
    }


@frappe.whitelist()
def receive_payment(reservation_name, mode, amount, reference=None):
    res = frappe.get_doc("Hotel Reservation", reservation_name)
    company = res.company or get_company()
    company_doc = frappe.get_doc("Company", company)

    paid_to = frappe.db.get_value("Mode of Payment Account", {"parent": mode, "company": company}, "default_account") or company_doc.default_cash_account
    paid_from = company_doc.default_receivable_account

    pe = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Receive",
        "party_type": "Customer",
        "party": res.customer,
        "company": company,
        "hotel_reservation": res.name,
        "mode_of_payment": mode,
        "paid_to": paid_to,
        "paid_from": paid_from,
        "paid_amount": flt(amount),
        "received_amount": flt(amount),
        "reference_no": reference
    })
    pe.insert(ignore_permissions=True)
    pe.submit()

    billing = get_billing_summary(reservation_name)
    emit_console_update("payment_received", {"reservation": reservation_name, "amount": amount})

    return {
        "status": "success",
        "payment_entry": pe.name,
        "billing": billing
    }


@frappe.whitelist()
def check_out(reservation_name, collect_payment=None):
    if collect_payment and isinstance(collect_payment, str):
        collect_payment = frappe.parse_json(collect_payment)

    if collect_payment and flt(collect_payment.get("amount")) > 0:
        receive_payment(
            reservation_name,
            collect_payment.get("mode"),
            collect_payment.get("amount"),
            collect_payment.get("reference")
        )

    res = v1_check_out(reservation_name)
    emit_console_update("checkout_completed", {"reservation": reservation_name})

    print_url = f"/api/method/frappe.utils.print_format.download_pdf?doctype=Sales Invoice&name={res['sales_invoice']}&format=Standard"

    return {
        "status": "success",
        "sales_invoice": res["sales_invoice"],
        "print_url": print_url
    }


@frappe.whitelist()
def report_issue(room, subject, priority="Medium", description=None):
    issue = frappe.get_doc({
        "doctype": "Issue",
        "subject": subject,
        "hotel_room": room,
        "priority": priority,
        "description": description or subject,
        "status": "Open"
    })
    issue.insert(ignore_permissions=True)
    emit_console_update("issue_reported", {"room": room, "issue": issue.name})
    return {"status": "success", "issue": issue.name}


@frappe.whitelist()
def resolve_issue(issue_name, notes=None):
    issue = frappe.get_doc("Issue", issue_name)
    issue.status = "Resolved"
    if notes:
        issue.add_comment("Comment", f"Resolution: {notes}")
    issue.save(ignore_permissions=True)
    emit_console_update("issue_resolved", {"room": issue.hotel_room, "issue": issue.name})
    return {"status": "success", "room": issue.hotel_room}


@frappe.whitelist()
def set_housekeeping(room_number, action):
    from hospitality_core.hospitality_core.page.housekeeping_view.housekeeping_view import toggle_room_status
    res = toggle_room_status(room_number, "mark_clean" if action == "Clean" else "mark_dirty")
    emit_console_update("housekeeping_updated", {"room": room_number, "status": res["status"]})
    return res


@frappe.whitelist()
def ensure_pos_opening(pos_profile):
    """
    Returns an active POS Opening Entry for (user, pos_profile).
    If none exists, automatically creates one with zero balances so cashier is never blocked.
    """
    user = frappe.session.user
    today = nowdate()

    open_entry = frappe.db.get_value(
        "POS Opening Entry",
        {
            "user": user,
            "pos_profile": pos_profile,
            "status": "Open",
            "docstatus": 1
        },
        "name"
    )

    if open_entry:
        return {"name": open_entry, "status": "Open"}

    # Create new POS Opening Entry
    pos_prof_doc = frappe.get_doc("POS Profile", pos_profile)
    company = pos_prof_doc.company

    balances = []
    for p in pos_prof_doc.payments:
        balances.append({
            "mode_of_payment": p.mode_of_payment,
            "opening_amount": 0.0
        })

    opening_doc = frappe.get_doc({
        "doctype": "POS Opening Entry",
        "period_start_date": now_datetime(),
        "posting_date": today,
        "company": company,
        "pos_profile": pos_profile,
        "user": user,
        "balance_details": balances
    })
    opening_doc.insert(ignore_permissions=True)
    opening_doc.submit()

    return {"name": opening_doc.name, "status": "Created"}


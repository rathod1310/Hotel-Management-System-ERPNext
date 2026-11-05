import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, date_diff, flt
from hospitality_core.constants import RoomStatus, ReservationStatus
from hospitality_core.room_status import set_room_status
from hospitality_core.utils import get_settings, get_company, get_room_item


class HotelReservation(Document):
    def validate(self):
        if not self.company:
            self.company = get_company()

        if getdate(self.check_in_date) >= getdate(self.check_out_date):
            frappe.throw(_("Check-out date must be after check-in date."))

        # If rate is not resolved or rate_plan changed, resolve rate
        if not self.stays:
            rate = get_room_rate(self.room_type, self.check_in_date, self.customer)
            nights = max(date_diff(self.check_out_date, self.check_in_date), 1)
            self.append("stays", {
                "room": self.room,
                "room_type": self.room_type,
                "from_date": self.check_in_date,
                "to_date": self.check_out_date,
                "rate": rate,
                "nights": nights
            })
        elif len(self.stays) == 1:
            stay = self.stays[0]
            if self.room and stay.room != self.room:
                stay.room = self.room
            if self.room_type and stay.room_type != self.room_type:
                stay.room_type = self.room_type
            stay.from_date = self.check_in_date
            stay.to_date = self.check_out_date
            stay.nights = max(date_diff(self.check_out_date, self.check_in_date), 1)
        else:
            # Multi-segment stay: ensure last stay finishes on check_out_date
            last_stay = self.stays[-1]
            if getdate(last_stay.to_date) != getdate(self.check_out_date):
                last_stay.to_date = self.check_out_date
                last_stay.nights = max(date_diff(self.check_out_date, last_stay.from_date), 1)

        for s in self.stays:
            if s.to_date and getdate(s.to_date) < getdate(s.from_date):
                frappe.throw(_("Stay to_date ({0}) cannot be before from_date ({1}) for room {2}.").format(
                    s.to_date, s.from_date, s.room
                ))

        # Validate room availability if Reserved
        if self.status == ReservationStatus.RESERVED:
            self.validate_room_availability()

    def on_update(self):
        if self.status == ReservationStatus.RESERVED:
            if self.room:
                old_doc = self.get_doc_before_save()
                if old_doc and old_doc.room and old_doc.room != self.room:
                    try:
                        old_room_doc = frappe.get_doc("Hotel Room", old_doc.room)
                        if old_room_doc.current_reservation == self.name:
                            set_room_status(old_doc.room, RoomStatus.AVAILABLE, reason=f"Room changed in reservation {self.name}")
                    except Exception:
                        pass
                set_room_status(self.room, RoomStatus.RESERVED, reason=f"Reserved by {self.name}", reservation=self.name)
        elif self.status == ReservationStatus.CANCELLED:
            if self.room:
                try:
                    room_doc = frappe.get_doc("Hotel Room", self.room)
                    if room_doc.current_reservation == self.name:
                        set_room_status(self.room, RoomStatus.AVAILABLE, reason=f"Reservation {self.name} cancelled")
                except Exception:
                    pass

    def on_trash(self):
        if self.room:
            try:
                room_doc = frappe.get_doc("Hotel Room", self.room)
                if room_doc.current_reservation == self.name:
                    set_room_status(self.room, RoomStatus.AVAILABLE, reason=f"Reservation {self.name} deleted")
            except Exception:
                pass

    def validate_room_availability(self):
        """
        Validate that self.room is available for [check_in_date, check_out_date).
        """
        if not self.room:
            return

        room_doc = frappe.get_doc("Hotel Room", self.room)
        if not room_doc.is_enabled:
            frappe.throw(_("Room {0} is disabled.").format(self.room))

        # Prevent booking Dirty rooms
        if room_doc.status == RoomStatus.DIRTY:
            frappe.throw(_("Room {0} is currently Dirty. It cannot be booked until cleaned.").format(self.room))

        # Check if Out of Order on arrival
        if room_doc.status == RoomStatus.OUT_OF_ORDER:
            frappe.throw(_("Room {0} is currently Out of Order.").format(self.room))

        # Check if currently Occupied
        if room_doc.status == RoomStatus.OCCUPIED and room_doc.current_reservation != self.name:
            frappe.throw(_("Room {0} is currently Occupied.").format(self.room))

        # Check if Reserved by another reservation
        if room_doc.status == RoomStatus.RESERVED and room_doc.current_reservation and room_doc.current_reservation != self.name:
            frappe.throw(_("Room {0} is already Reserved by reservation {1}.").format(self.room, room_doc.current_reservation))

        # Check overlapping reservations
        overlapping = frappe.db.sql("""
            SELECT r.name, COALESCE(s.room, r.room) as room, s.from_date, s.to_date
            FROM `tabHotel Reservation` r
            LEFT JOIN `tabHotel Reservation Stay` s ON s.parent = r.name
            WHERE COALESCE(s.room, r.room) = %(room)s
            AND r.name != %(name)s
            AND r.status IN ('Reserved', 'Checked In')
            AND (
                (s.from_date < %(check_out)s AND (s.to_date > %(check_in)s OR s.to_date IS NULL))
                OR
                (r.check_in_date < %(check_out)s AND r.check_out_date > %(check_in)s)
            )
        """, {
            "room": self.room,
            "name": self.name or "New Reservation",
            "check_in": self.check_in_date,
            "check_out": self.check_out_date
        }, as_dict=True)

        if overlapping:
            frappe.throw(_("Room {0} is already booked by reservation {1} for the requested dates.").format(
                self.room, overlapping[0].name
            ))


@frappe.whitelist()
def get_available_rooms(room_type, check_in_date, check_out_date, exclude_reservation=None):
    if getdate(check_in_date) >= getdate(check_out_date):
        frappe.throw(_("Check-out date must be after check-in date."))

    all_rooms = frappe.get_all(
        "Hotel Room",
        filters={"room_type": room_type, "is_enabled": 1},
        fields=["name", "room_number", "status", "floor", "current_reservation"]
    )

    # Exclude currently Out of Order, Dirty, Occupied, and Reserved rooms from selection
    def is_room_selectable(r):
        if r.status in (RoomStatus.OUT_OF_ORDER, RoomStatus.DIRTY, RoomStatus.OCCUPIED):
            return False
        if r.status == RoomStatus.RESERVED:
            if exclude_reservation and r.current_reservation == exclude_reservation:
                return True
            return False
        return True

    all_rooms = [r for r in all_rooms if is_room_selectable(r)]

    booked_rooms = frappe.db.sql("""
        SELECT DISTINCT COALESCE(s.room, r.room) as room
        FROM `tabHotel Reservation` r
        LEFT JOIN `tabHotel Reservation Stay` s ON s.parent = r.name
        WHERE r.status IN ('Reserved', 'Checked In')
        AND r.name != %(exclude_res)s
        AND (
            (s.from_date < %(check_out)s AND (s.to_date > %(check_in)s OR s.to_date IS NULL))
            OR
            (r.check_in_date < %(check_out)s AND r.check_out_date > %(check_in)s)
        )
    """, {
        "exclude_res": exclude_reservation or "None",
        "check_in": check_in_date,
        "check_out": check_out_date
    }, as_dict=True)

    booked_room_names = {b.room for b in booked_rooms if b.room}
    return [r for r in all_rooms if r.name not in booked_room_names]


@frappe.whitelist()
def get_room_rate(room_type, date, customer=None):
    customer_group = None
    if customer:
        customer_group = frappe.db.get_value("Customer", customer, "customer_group")

    date = getdate(date)

    if customer:
        plan = frappe.db.get_value(
            "Room Rate Plan",
            {
                "room_type": room_type,
                "customer": customer,
                "active": 1,
                "valid_from": ["<=", date],
                "valid_to": [">=", date]
            },
            "rate"
        )
        if plan:
            return flt(plan)

    if customer_group:
        plan = frappe.db.get_value(
            "Room Rate Plan",
            {
                "room_type": room_type,
                "customer_group": customer_group,
                "active": 1,
                "valid_from": ["<=", date],
                "valid_to": [">=", date]
            },
            "rate"
        )
        if plan:
            return flt(plan)

    plan = frappe.db.sql("""
        SELECT rate FROM `tabRoom Rate Plan`
        WHERE room_type = %s
        AND active = 1
        AND (customer IS NULL OR customer = '')
        AND (customer_group IS NULL OR customer_group = '')
        AND valid_from <= %s AND valid_to >= %s
        ORDER BY rate ASC LIMIT 1
    """, (room_type, date, date), as_dict=True)
    if plan:
        return flt(plan[0].rate)

    default_rate = frappe.db.get_value("Hotel Room Type", room_type, "default_rate")
    return flt(default_rate or 0.0)


@frappe.whitelist()
def check_in(reservation_name):
    res = frappe.get_doc("Hotel Reservation", reservation_name)
    if res.status != ReservationStatus.RESERVED:
        frappe.throw(_("Only reservations in 'Reserved' status can be checked in."))

    settings = get_settings()
    today = getdate()
    if getdate(res.check_in_date) > today and not settings.allow_checkin_before_arrival:
        frappe.throw(_("Check-in before arrival date ({0}) is not allowed by Hotel Settings.").format(res.check_in_date))

    room_doc = frappe.get_doc("Hotel Room", res.room)
    if room_doc.status not in (RoomStatus.AVAILABLE, RoomStatus.RESERVED):
        frappe.throw(_("Room {0} is not ready for check-in: {1}").format(res.room, room_doc.status))

    if room_doc.status == RoomStatus.RESERVED and room_doc.current_reservation and room_doc.current_reservation != res.name:
        frappe.throw(_("Room {0} is reserved by another reservation ({1}).").format(res.room, room_doc.current_reservation))

    if res.stays:
        res.stays[0].from_date = today
        if getdate(res.stays[0].to_date) <= today:
            res.stays[0].to_date = frappe.utils.add_days(today, 1)
        res.stays[0].nights = max(date_diff(res.stays[0].to_date, res.stays[0].from_date), 1)
        res.check_out_date = res.stays[-1].to_date

    res.status = ReservationStatus.CHECKED_IN
    res.checked_in_on = now_datetime()
    res.save()

    set_room_status(res.room, RoomStatus.OCCUPIED, reason=f"Check-in {res.name}", reservation=res.name)
    return {"status": res.status}


@frappe.whitelist()
def move_room(reservation_name, new_room, reason=None, keep_rate=0):
    res = frappe.get_doc("Hotel Reservation", reservation_name)
    if res.status != ReservationStatus.CHECKED_IN:
        frappe.throw(_("Only Checked In reservations can move rooms."))

    new_room_doc = frappe.get_doc("Hotel Room", new_room)
    if new_room_doc.status != RoomStatus.AVAILABLE:
        frappe.throw(_("New room {0} is not Available (current status: {1}).").format(new_room, new_room_doc.status))

    today = getdate()
    old_room = res.room

    last_stay = res.stays[-1] if res.stays else None
    if last_stay:
        last_stay.to_date = today
        last_stay.nights = max(date_diff(last_stay.to_date, last_stay.from_date), 0)

    if int(keep_rate) and last_stay:
        new_rate = last_stay.rate
    else:
        new_rate = get_room_rate(new_room_doc.room_type, today, res.customer)

    remaining_nights = max(date_diff(res.check_out_date, today), 1)
    res.append("stays", {
        "room": new_room,
        "room_type": new_room_doc.room_type,
        "from_date": today,
        "to_date": res.check_out_date,
        "rate": new_rate,
        "nights": remaining_nights,
        "move_reason": reason
    })

    res.room = new_room
    res.room_type = new_room_doc.room_type
    res.save()

    has_open_issue = frappe.db.exists("Issue", {
        "hotel_room": old_room,
        "status": ["in", ["Open", "Replied", "Hold"]]
    })
    old_room_status = RoomStatus.OUT_OF_ORDER if has_open_issue else RoomStatus.DIRTY
    set_room_status(old_room, old_room_status, reason=f"Guest moved to room {new_room}")
    set_room_status(new_room, RoomStatus.OCCUPIED, reason=f"Guest moved from room {old_room}", reservation=res.name)

    return {"status": "success", "new_room": new_room}


@frappe.whitelist()
def cancel_reservation(reservation_name):
    res = frappe.get_doc("Hotel Reservation", reservation_name)
    if res.status != ReservationStatus.RESERVED:
        frappe.throw(_("Only Reserved stays can be cancelled."))

    res.status = ReservationStatus.CANCELLED
    res.save()

    advances = frappe.db.sql("""
        SELECT name, paid_amount FROM `tabPayment Entry`
        WHERE hotel_reservation = %s AND docstatus = 1
    """, res.name, as_dict=True)
    if advances:
        frappe.msgprint(_("Reservation cancelled. Note: advance payments exist ({0}). Please refund using standard Payment Entry if required.").format(
            ", ".join([a.name for a in advances])
        ))

    return {"status": res.status}


def build_sales_invoice(reservation_name, as_of=None):
    """
    Builds an unsaved Sales Invoice document for the reservation stay segments.
    """
    res = frappe.get_doc("Hotel Reservation", reservation_name)
    settings = get_settings()
    as_of = getdate(as_of) if as_of else getdate()

    inv = frappe.new_doc("Sales Invoice")
    inv.customer = res.customer
    inv.company = res.company or get_company()
    inv.hotel_reservation = res.name
    inv.posting_date = as_of
    inv.due_date = as_of

    if settings.sales_taxes_template:
        inv.taxes_and_charges = settings.sales_taxes_template
    if settings.cost_center:
        inv.cost_center = settings.cost_center

    inv.allocate_advances_automatically = 1

    total_nights_stayed = 0
    lines_added = 0

    for i, row in enumerate(res.stays):
        # Calculate nights
        row_from = getdate(row.from_date)
        if row.to_date and i < len(res.stays) - 1:
            row_to = getdate(row.to_date)
        else:
            # Last open row bills up to as_of
            row_to = as_of

        nights = max(date_diff(row_to, row_from), 0)
        total_nights_stayed += nights

        if nights > 0:
            item_code = get_room_item(row.room_type)
            inv.append("items", {
                "item_code": item_code,
                "qty": nights,
                "rate": row.rate,
                "description": _("Room {0} ({1}) from {2} to {3}").format(
                    row.room, row.room_type, row_from, row_to
                )
            })
            lines_added += 1

    # Check minimum billable nights
    min_nights = int(settings.min_billable_nights or 1)
    if total_nights_stayed < min_nights and res.stays:
        first_row = res.stays[0]
        needed_nights = min_nights - total_nights_stayed
        if inv.items:
            inv.items[0].qty += needed_nights
        else:
            item_code = get_room_item(first_row.room_type)
            inv.append("items", {
                "item_code": item_code,
                "qty": needed_nights,
                "rate": first_row.rate,
                "description": _("Room {0} ({1}) [Minimum Stay]").format(first_row.room, first_row.room_type)
            })

    inv.set_missing_values()
    inv.calculate_taxes_and_totals()
    return inv


@frappe.whitelist()
def get_billing_summary(reservation_name):
    """
    Computes estimated_total, total_paid, and balance for a reservation.
    """
    res = frappe.get_doc("Hotel Reservation", reservation_name)

    # 1. Estimated Total
    if res.sales_invoice and frappe.db.exists("Sales Invoice", res.sales_invoice):
        inv = frappe.get_doc("Sales Invoice", res.sales_invoice)
        estimated_total = flt(inv.grand_total)
    else:
        inv = build_sales_invoice(reservation_name)
        estimated_total = flt(inv.grand_total)

    # 2. Total Paid
    # A) Advance payment entries linked to reservation
    pe_total = frappe.db.sql("""
        SELECT SUM(paid_amount) FROM `tabPayment Entry`
        WHERE hotel_reservation = %s
        AND payment_type = 'Receive'
        AND docstatus = 1
    """, reservation_name)[0][0] or 0.0

    # B) If invoice submitted, any direct invoice payment
    inv_paid = 0.0
    if res.sales_invoice and frappe.db.exists("Sales Invoice", res.sales_invoice):
        inv_doc = frappe.get_doc("Sales Invoice", res.sales_invoice)
        inv_paid = flt(inv_doc.outstanding_amount)

    if res.sales_invoice:
        total_paid = flt(estimated_total - inv_paid)
    else:
        total_paid = flt(pe_total)

    balance = flt(estimated_total - total_paid, 2)

    # Update on doc if changed
    if res.estimated_total != estimated_total or res.total_paid != total_paid or res.balance != balance:
        frappe.db.set_value("Hotel Reservation", res.name, {
            "estimated_total": estimated_total,
            "total_paid": total_paid,
            "balance": balance
        }, update_modified=False)

    return {
        "estimated_total": estimated_total,
        "total_paid": total_paid,
        "balance": balance,
        "sales_invoice": res.sales_invoice
    }


@frappe.whitelist()
def check_out(reservation_name):
    res = frappe.get_doc("Hotel Reservation", reservation_name)
    if res.status != ReservationStatus.CHECKED_IN:
        frappe.throw(_("Only Checked In reservations can be checked out."))

    today = getdate()
    settings = get_settings()

    # Close last stay segment
    if res.stays:
        last_stay = res.stays[-1]
        last_stay.to_date = today
        last_stay.nights = max(date_diff(today, getdate(last_stay.from_date)), 0)

    # Check balance tolerance
    billing = get_billing_summary(reservation_name)
    tolerance = flt(settings.balance_tolerance or 0.0)
    if settings.block_checkout_if_balance and billing["balance"] > tolerance:
        frappe.throw(_("Cannot check out. Outstanding balance is {0}. Please receive payment first.").format(
            billing["balance"]
        ))

    # Build and submit Sales Invoice
    inv = build_sales_invoice(reservation_name, as_of=today)
    inv.insert(ignore_permissions=True)
    inv.submit()

    res.sales_invoice = inv.name
    res.status = ReservationStatus.CHECKED_OUT
    res.checked_out_on = now_datetime()
    res.save()

    # Update room status: Out of Order if open issue, else Dirty
    has_open_issue = frappe.db.exists("Issue", {
        "hotel_room": res.room,
        "status": ["in", ["Open", "Replied", "Hold"]]
    })
    room_status = RoomStatus.OUT_OF_ORDER if has_open_issue else RoomStatus.DIRTY
    set_room_status(res.room, room_status, reason=f"Check-out {res.name}")

    return {
        "status": res.status,
        "sales_invoice": inv.name
    }

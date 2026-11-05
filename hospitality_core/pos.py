import frappe
from frappe import _
from frappe.utils import flt
from hospitality_core.constants import ReservationStatus
from hospitality_core.utils import get_settings


def validate_sales_invoice(doc, method):
    """
    Hook on Sales Invoice validate.
    Routes POS orders to hotel order types based on configured POS Profiles in Hotel Settings.
    """
    if not doc.pos_profile:
        return

    settings = get_settings()
    room_profile = settings.room_pos_profile
    restaurant_profile = settings.restaurant_pos_profile

    if restaurant_profile and doc.pos_profile == restaurant_profile:
        doc.hotel_order_type = "Restaurant"

    elif room_profile and doc.pos_profile == room_profile:
        doc.hotel_order_type = "Room Service"

        # Resolve in-house Checked In reservation for this customer
        reservations = frappe.get_all(
            "Hotel Reservation",
            filters={
                "customer": doc.customer,
                "status": ReservationStatus.CHECKED_IN
            },
            fields=["name", "room"],
            order_by="creation desc"
        )

        if not reservations:
            frappe.throw(_("Customer {0} does not have an active Checked In reservation for Room Service.").format(
                frappe.bold(doc.customer)
            ))

        # If doc already has hotel_reservation set and it matches one of the in-house stays, keep it
        matched_res = None
        if doc.hotel_reservation:
            for r in reservations:
                if r.name == doc.hotel_reservation:
                    matched_res = r
                    break

        if not matched_res:
            matched_res = reservations[0]

        doc.hotel_reservation = matched_res.name


def before_submit_sales_invoice(doc, method):
    """
    Prevent submitting a draft invoice if it is flagged as Charge to Room.
    Room charges must be merged and settled on the stay checkout invoice.
    """
    if doc.charge_to_room:
        frappe.throw(
            _("Cannot submit invoice {0}. Room charges are billed at stay check-out. Unflag 'Charge to Room' or pay the order.").format(
                doc.name
            )
        )


@frappe.whitelist()
def charge_to_room(invoice_name):
    """
    Validates that the invoice is a draft from the room POS profile and that the guest is currently Checked In.
    Sets charge_to_room = 1 and saves the draft.
    """
    if not invoice_name:
        frappe.throw(_("Invoice name is required."))

    inv = frappe.get_doc("Sales Invoice", invoice_name)
    if inv.docstatus != 0:
        frappe.throw(_("Only Draft invoices can be charged to a room. Invoice {0} is docstatus {1}.").format(
            inv.name, inv.docstatus
        ))

    settings = get_settings()
    if inv.pos_profile != settings.room_pos_profile:
        frappe.throw(_("Only orders from the Room POS Profile ({0}) can be charged to a room.").format(
            settings.room_pos_profile or "Not configured"
        ))

    # Verify reservation is active and locked for update
    if not inv.hotel_reservation:
        frappe.throw(_("No Hotel Reservation linked to invoice {0}.").format(inv.name))

    res_status = frappe.db.get_value("Hotel Reservation", inv.hotel_reservation, "status", for_update=True)
    if res_status != ReservationStatus.CHECKED_IN:
        frappe.throw(_("Reservation {0} is currently {1}. Only Checked In guests can charge orders to their room.").format(
            inv.hotel_reservation, res_status
        ))

    inv.charge_to_room = 1
    inv.hotel_order_type = "Room Service"
    inv.save(ignore_permissions=True)

    return {
        "status": "success",
        "invoice": inv.name,
        "reservation": inv.hotel_reservation,
        "total": inv.grand_total
    }


@frappe.whitelist()
def unflag_charge_to_room(invoice_name):
    """
    Removes charge_to_room flag so cashier can complete order or change mind.
    """
    inv = frappe.get_doc("Sales Invoice", invoice_name)
    if inv.docstatus != 0:
        frappe.throw(_("Only Draft invoices can be updated."))

    inv.charge_to_room = 0
    inv.save(ignore_permissions=True)
    return {"status": "success", "invoice": inv.name}


@frappe.whitelist()
def get_in_house_guests():
    """
    Returns in-house guests for the POS guest picker:
    [{customer, guest_name, room, reservation}]
    """
    guests = frappe.db.sql("""
        SELECT
            r.customer,
            c.customer_name as guest_name,
            r.room,
            r.name as reservation
        FROM `tabHotel Reservation` r
        LEFT JOIN `tabCustomer` c ON c.name = r.customer
        WHERE r.status = %s
        ORDER BY r.room ASC, c.customer_name ASC
    """, (ReservationStatus.CHECKED_IN,), as_dict=True)

    return guests


@frappe.whitelist()
def get_pending_room_orders(reservation):
    """
    Returns drafts flagged with charge_to_room = 1 for this reservation.
    """
    if not reservation:
        return []

    drafts = frappe.get_all(
        "Sales Invoice",
        filters={
            "hotel_reservation": reservation,
            "charge_to_room": 1,
            "docstatus": 0
        },
        fields=["name", "posting_date", "grand_total", "total_taxes_and_charges", "net_total"]
    )

    result = []
    for d in drafts:
        items = frappe.get_all(
            "Sales Invoice Item",
            filters={"parent": d.name},
            fields=["item_code", "item_name", "qty", "rate", "amount", "discount_percentage", "discount_amount"]
        )
        d["items"] = items
        result.append(d)

    return result

import frappe
from frappe import _
from frappe.utils import getdate, nowdate, flt
from hospitality_core.constants import ReservationStatus
from hospitality_core.hospitality_core.doctype.hotel_reservation.hotel_reservation import get_billing_summary


def execute(filters=None):
    if not filters:
        filters = {}

    target_date = filters.get("date") or nowdate()

    columns = [
        {"label": _("Room"), "fieldname": "room", "fieldtype": "Link", "options": "Hotel Room", "width": 90},
        {"label": _("Guest Name"), "fieldname": "guest_name", "fieldtype": "Data", "width": 160},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": _("Check In Date"), "fieldname": "check_in_date", "fieldtype": "Date", "width": 110},
        {"label": _("Check Out Date"), "fieldname": "check_out_date", "fieldtype": "Date", "width": 110},
        {"label": _("Rate Plan"), "fieldname": "rate_plan", "fieldtype": "Link", "options": "Room Rate Plan", "width": 120},
        {"label": _("Estimated Total"), "fieldname": "estimated_total", "fieldtype": "Currency", "width": 120},
        {"label": _("Total Paid"), "fieldname": "total_paid", "fieldtype": "Currency", "width": 120},
        {"label": _("Balance"), "fieldname": "balance", "fieldtype": "Currency", "width": 120}
    ]

    sql = """
        SELECT
            res.name as reservation,
            res.room,
            c.customer_name as guest_name,
            res.status,
            res.check_in_date,
            res.check_out_date,
            res.rate_plan
        FROM
            `tabHotel Reservation` res
        LEFT JOIN
            `tabCustomer` c ON res.customer = c.name
        WHERE
            res.check_in_date <= %(date)s
            AND res.check_out_date > %(date)s
            AND res.status = 'Checked In'
        ORDER BY
            res.room ASC
    """

    rows = frappe.db.sql(sql, {"date": target_date}, as_dict=True)

    data = []
    for r in rows:
        billing = get_billing_summary(r.reservation)
        r.estimated_total = billing["estimated_total"]
        r.total_paid = billing["total_paid"]
        r.balance = billing["balance"]
        data.append(r)

    report_summary = [
        {"value": len(data), "label": _("Total In-House Guests"), "datatype": "Int"}
    ]

    return columns, data, None, None, report_summary

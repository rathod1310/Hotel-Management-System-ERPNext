import frappe
from frappe import _
from frappe.utils import nowdate


def execute(filters=None):
    if not filters:
        filters = {}

    columns = [
        {"label": _("Reservation"), "fieldname": "name", "fieldtype": "Link", "options": "Hotel Reservation", "width": 140},
        {"label": _("Guest Name"), "fieldname": "guest_name", "fieldtype": "Data", "width": 160},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": _("Checked In On"), "fieldname": "checked_in_on", "fieldtype": "Datetime", "width": 140},
        {"label": _("Room"), "fieldname": "room", "fieldtype": "Link", "options": "Hotel Room", "width": 100},
        {"label": _("Room Type"), "fieldname": "room_type", "fieldtype": "Link", "options": "Hotel Room Type", "width": 120},
        {"label": _("Check Out Date"), "fieldname": "check_out_date", "fieldtype": "Date", "width": 110}
    ]

    target_date = filters.get("date") or nowdate()
    filters["target_date"] = target_date

    sql = """
        SELECT
            res.name,
            c.customer_name as guest_name,
            res.status,
            res.checked_in_on,
            res.room,
            res.room_type,
            res.check_out_date
        FROM
            `tabHotel Reservation` res
        LEFT JOIN
            `tabCustomer` c ON res.customer = c.name
        WHERE
            res.check_in_date = %(target_date)s
            AND res.status IN ('Reserved', 'Checked In', 'Checked Out')
        ORDER BY
            res.check_in_date ASC, res.name ASC
    """

    data = frappe.db.sql(sql, filters, as_dict=True)
    return columns, data

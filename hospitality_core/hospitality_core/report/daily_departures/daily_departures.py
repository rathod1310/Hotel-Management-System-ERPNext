import frappe
from frappe import _
from frappe.utils import nowdate


def execute(filters=None):
    if not filters:
        filters = {}

    target_date = filters.get("date") or nowdate()

    columns = [
        {"label": _("Room"), "fieldname": "room", "fieldtype": "Link", "options": "Hotel Room", "width": 90},
        {"label": _("Guest Name"), "fieldname": "guest_name", "fieldtype": "Data", "width": 160},
        {"label": _("Reservation"), "fieldname": "name", "fieldtype": "Link", "options": "Hotel Reservation", "width": 140},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": _("Checked Out On"), "fieldname": "checked_out_on", "fieldtype": "Datetime", "width": 140},
        {"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 140},
        {"label": _("Total Paid"), "fieldname": "total_paid", "fieldtype": "Currency", "width": 120}
    ]

    sql = """
        SELECT
            res.room,
            c.customer_name as guest_name,
            res.name,
            res.status,
            res.checked_out_on,
            res.sales_invoice,
            res.total_paid
        FROM
            `tabHotel Reservation` res
        LEFT JOIN
            `tabCustomer` c ON res.customer = c.name
        WHERE
            res.check_out_date = %(target_date)s
            AND res.status IN ('Checked In', 'Checked Out')
        ORDER BY
            res.checked_out_on DESC, res.name ASC
    """

    data = frappe.db.sql(sql, {"target_date": target_date}, as_dict=True)
    return columns, data

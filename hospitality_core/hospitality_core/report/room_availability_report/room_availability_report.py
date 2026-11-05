import frappe
from frappe import _
from frappe.utils import add_days, getdate, date_diff, flt, nowdate


def execute(filters=None):
    if not filters:
        filters = {}

    columns = [
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 110},
        {"label": _("Room Type"), "fieldname": "room_type", "fieldtype": "Link", "options": "Hotel Room Type", "width": 150},
        {"label": _("Total Rooms"), "fieldname": "total_rooms", "fieldtype": "Int", "width": 100},
        {"label": _("Out of Order"), "fieldname": "ooo", "fieldtype": "Int", "width": 100},
        {"label": _("Occupied/Sold"), "fieldname": "sold", "fieldtype": "Int", "width": 110},
        {"label": _("Available"), "fieldname": "available", "fieldtype": "Int", "width": 100},
        {"label": _("Occupancy %"), "fieldname": "occupancy_pct", "fieldtype": "Percent", "width": 100}
    ]

    start_date = getdate(filters.get("from_date") or nowdate())
    end_date = getdate(filters.get("to_date") or add_days(start_date, 7))
    filter_type = filters.get("room_type")

    inventory = frappe.db.sql("""
        SELECT room_type, COUNT(name) as cnt
        FROM `tabHotel Room`
        WHERE is_enabled = 1
        GROUP BY room_type
    """, as_dict=True)

    inventory_map = {i.room_type: i.cnt for i in inventory}
    all_types = list(inventory_map.keys())
    if filter_type and filter_type in all_types:
        all_types = [filter_type]

    data = []
    curr_date = start_date
    while curr_date <= end_date:
        str_date = curr_date.strftime("%Y-%m-%d")

        unavailable_data = frappe.db.sql("""
            SELECT room_type, COUNT(name) as cnt
            FROM `tabHotel Room`
            WHERE status IN ('Out of Order', 'Dirty') AND is_enabled = 1
            GROUP BY room_type
        """, as_dict=True)
        ooo_map = {o.room_type: o.cnt for o in unavailable_data}

        sold_data = frappe.db.sql("""
            SELECT s.room_type, COUNT(DISTINCT s.room) as cnt
            FROM `tabHotel Reservation` r
            JOIN `tabHotel Reservation Stay` s ON s.parent = r.name
            WHERE r.status IN ('Reserved', 'Checked In')
            AND s.from_date <= %(date)s
            AND (s.to_date > %(date)s OR s.to_date IS NULL)
            GROUP BY s.room_type
        """, {"date": str_date}, as_dict=True)
        sold_map = {s.room_type: s.cnt for s in sold_data}

        for rt in all_types:
            total = inventory_map.get(rt, 0)
            ooo = ooo_map.get(rt, 0)
            sold = sold_map.get(rt, 0)
            available = max(total - ooo - sold, 0)
            occ_pct = flt((sold / total) * 100, 1) if total > 0 else 0.0

            data.append({
                "date": str_date,
                "room_type": rt,
                "total_rooms": total,
                "ooo": ooo,
                "sold": sold,
                "available": available,
                "occupancy_pct": occ_pct
            })

        curr_date = add_days(curr_date, 1)

    return columns, data

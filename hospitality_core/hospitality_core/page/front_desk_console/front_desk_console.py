import frappe
from frappe.utils import nowdate, flt, getdate
from hospitality_core.constants import RoomStatus, ReservationStatus


@frappe.whitelist()
def get_console_data(target_date=None):
    if not target_date:
        target_date = nowdate()

    # 1. Arrivals for specific date
    arrivals = frappe.db.sql("""
        SELECT res.name, c.customer_name as guest_name, res.status, res.room, res.room_type, res.check_in_date as arrival_date
        FROM `tabHotel Reservation` res
        LEFT JOIN `tabCustomer` c ON res.customer = c.name
        WHERE res.check_in_date = %s
        AND res.status IN ('Reserved', 'Checked In', 'Checked Out')
        ORDER BY res.status DESC, c.customer_name ASC
    """, (target_date,), as_dict=True)

    # 2. Departures for specific date
    departures = frappe.db.sql("""
        SELECT res.name, c.customer_name as guest_name, res.status, res.room, res.room_type, res.check_out_date as departure_date
        FROM `tabHotel Reservation` res
        LEFT JOIN `tabCustomer` c ON res.customer = c.name
        WHERE res.check_out_date = %s
        AND res.status IN ('Checked In', 'Checked Out')
        ORDER BY res.status ASC, res.room ASC
    """, (target_date,), as_dict=True)

    # 3. Stats calculation
    total_rooms = frappe.db.count("Hotel Room", {"is_enabled": 1})

    in_house_count = frappe.db.count("Hotel Reservation", {
        "check_in_date": ["<=", target_date],
        "check_out_date": [">", target_date],
        "status": ReservationStatus.CHECKED_IN
    })

    arrivals_pending = len([a for a in arrivals if a.status == ReservationStatus.RESERVED])
    departures_pending = len([d for d in departures if d.status == ReservationStatus.CHECKED_IN])

    ooo_rooms = frappe.db.count("Hotel Room", {"status": RoomStatus.OUT_OF_ORDER, "is_enabled": 1})
    committed_rooms = in_house_count + arrivals_pending
    available = max(total_rooms - committed_rooms - ooo_rooms, 0)

    occupancy_pct = 0.0
    if total_rooms > 0:
        occupancy_pct = flt((in_house_count / total_rooms) * 100, 1)

    return {
        "arrivals": arrivals,
        "departures": departures,
        "stats": {
            "total_rooms": total_rooms,
            "in_house": in_house_count,
            "occupancy_pct": occupancy_pct,
            "arrivals_pending": arrivals_pending,
            "departures_pending": departures_pending,
            "available": available
        }
    }

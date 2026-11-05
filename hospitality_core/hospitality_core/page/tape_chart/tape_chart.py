import frappe


@frappe.whitelist()
def get_chart_data(start_date, end_date):
    rooms = frappe.get_all(
        "Hotel Room",
        filters={"is_enabled": 1},
        fields=["name", "room_number", "room_type", "status"],
        order_by="room_number asc"
    )

    bookings = frappe.db.sql("""
        SELECT r.name, c.customer_name as guest, s.room, s.from_date as arrival_date, s.to_date as departure_date, r.status
        FROM `tabHotel Reservation` r
        JOIN `tabHotel Reservation Stay` s ON s.parent = r.name
        LEFT JOIN `tabCustomer` c ON r.customer = c.name
        WHERE r.status IN ('Reserved', 'Checked In')
        AND s.from_date < %(end)s
        AND (s.to_date > %(start)s OR s.to_date IS NULL)
    """, {"start": start_date, "end": end_date}, as_dict=True)

    return {
        "rooms": rooms,
        "bookings": bookings
    }

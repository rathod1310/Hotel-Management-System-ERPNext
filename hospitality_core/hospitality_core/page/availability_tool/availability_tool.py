import frappe
from hospitality_core.constants import RoomStatus, ReservationStatus


@frappe.whitelist()
def check_availability_counts(start_date, end_date):
    rooms = frappe.get_all(
        "Hotel Room",
        fields=["name", "room_type", "status as current_status"],
        filters={"is_enabled": 1},
        order_by="room_number"
    )

    reservations = frappe.db.sql("""
        SELECT s.room, r.status, r.name, c.customer_name as guest
        FROM `tabHotel Reservation` r
        JOIN `tabHotel Reservation Stay` s ON s.parent = r.name
        LEFT JOIN `tabCustomer` c ON r.customer = c.name
        WHERE r.status IN ('Reserved', 'Checked In')
        AND s.from_date < %s
        AND (s.to_date > %s OR s.to_date IS NULL)
    """, (end_date, start_date), as_dict=True)

    reservation_map = {r.room: r for r in reservations}

    room_details = []
    summary_map = {}

    for room in rooms:
        res = reservation_map.get(room.name)
        status = RoomStatus.AVAILABLE
        details = ""

        if room.current_status == RoomStatus.OUT_OF_ORDER:
            status = RoomStatus.OUT_OF_ORDER
            details = "Maintenance"
        elif res:
            if res.status == ReservationStatus.CHECKED_IN:
                status = RoomStatus.OCCUPIED
            else:
                status = ReservationStatus.RESERVED
            details = f"{res.name} ({res.guest})"

        room_details.append({
            "room": room.name,
            "room_type": room.room_type,
            "status": status,
            "details": details
        })

        if room.room_type not in summary_map:
            summary_map[room.room_type] = {"room_type": room.room_type, "total": 0, "occupied": 0, "available": 0}

        summary_map[room.room_type]["total"] += 1
        if status in [RoomStatus.OCCUPIED, ReservationStatus.RESERVED, RoomStatus.OUT_OF_ORDER]:
            summary_map[room.room_type]["occupied"] += 1
        else:
            summary_map[room.room_type]["available"] += 1

    return {
        "summary": list(summary_map.values()),
        "room_details": room_details
    }

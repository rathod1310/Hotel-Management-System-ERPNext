import frappe
from frappe.utils import getdate
from hospitality_core.constants import RoomStatus, ReservationStatus


@frappe.whitelist()
def check_availability_counts(start_date, end_date):
    start_date = getdate(start_date)
    end_date = getdate(end_date)

    rooms = frappe.get_all(
        "Hotel Room",
        fields=["name", "room_number", "room_type", "status as current_status", "current_reservation"],
        filters={"is_enabled": 1},
        order_by="room_number"
    )

    reservations = frappe.db.sql("""
        SELECT COALESCE(s.room, r.room) as room, r.status, r.name, c.customer_name as guest
        FROM `tabHotel Reservation` r
        LEFT JOIN `tabHotel Reservation Stay` s ON s.parent = r.name
        LEFT JOIN `tabCustomer` c ON r.customer = c.name
        WHERE r.status IN ('Reserved', 'Checked In')
        AND (
            (s.from_date < %(end_date)s AND (s.to_date > %(start_date)s OR s.to_date IS NULL))
            OR
            (r.check_in_date < %(end_date)s AND r.check_out_date > %(start_date)s)
        )
    """, {"start_date": start_date, "end_date": end_date}, as_dict=True)

    reservation_map = {}
    for r in reservations:
        if r.room and r.room not in reservation_map:
            reservation_map[r.room] = r

    room_details = []
    summary_map = {}

    for room in rooms:
        res = reservation_map.get(room.name)
        status = RoomStatus.AVAILABLE
        details = ""

        # Check physical room status first
        if room.current_status == RoomStatus.OUT_OF_ORDER:
            status = RoomStatus.OUT_OF_ORDER
            details = "Maintenance"
        elif room.current_status == RoomStatus.DIRTY:
            status = RoomStatus.DIRTY
            details = "Housekeeping (Dirty)"
        elif room.current_status == RoomStatus.OCCUPIED:
            status = RoomStatus.OCCUPIED
            guest = res.guest if res else ""
            res_name = res.name if res else (room.current_reservation or "")
            details = f"{res_name} ({guest})" if guest else f"Occupied ({res_name})"
        elif room.current_status == RoomStatus.RESERVED:
            status = RoomStatus.RESERVED
            guest = res.guest if res else ""
            res_name = res.name if res else (room.current_reservation or "")
            details = f"{res_name} ({guest})" if guest else f"Reserved ({res_name})"
        elif res:
            if res.status == ReservationStatus.CHECKED_IN:
                status = RoomStatus.OCCUPIED
            else:
                status = RoomStatus.RESERVED
            details = f"{res.name} ({res.guest or ''})"

        room_details.append({
            "room": room.name,
            "room_type": room.room_type,
            "status": status,
            "details": details
        })

        if room.room_type not in summary_map:
            summary_map[room.room_type] = {"room_type": room.room_type, "total": 0, "occupied": 0, "available": 0}

        summary_map[room.room_type]["total"] += 1
        if status in [RoomStatus.OCCUPIED, RoomStatus.RESERVED, RoomStatus.OUT_OF_ORDER, RoomStatus.DIRTY]:
            summary_map[room.room_type]["occupied"] += 1
        else:
            summary_map[room.room_type]["available"] += 1

    return {
        "summary": list(summary_map.values()),
        "room_details": room_details
    }

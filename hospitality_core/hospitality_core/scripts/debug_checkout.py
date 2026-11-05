
import frappe
from hospitality_core.hospitality_core.hospitality_core.doctype.hotel_reservation.hotel_reservation import HotelReservation

def debug_checkout():
    # 1. Create a dummy reservation
    # We need a guest, a room, and a room type.
    # Assuming test data exists or we create it.
    
    # Check if Room Type exists
    rt = "Standard Room"
    if not frappe.db.exists("Hotel Room Type", rt):
        frappe.get_doc({"doctype": "Hotel Room Type", "name": rt, "default_rate": 100}).insert()

    # Check if Room exists
    room = "101"
    if not frappe.db.exists("Hotel Room", room):
        frappe.get_doc({"doctype": "Hotel Room", "room_number": room, "room_type": rt, "status": "Available", "is_enabled": 1}).insert()
    else:
        frappe.db.set_value("Hotel Room", room, "status", "Available")

    # Check if Guest exists
    guest = "Debug Guest"
    if not frappe.db.exists("Guest", {"full_name": guest}):
        g = frappe.new_doc("Guest")
        g.first_name = "Debug"
        g.last_name = "Guest"
        g.insert()
        guest_name = g.name
    else:
        guest_name = frappe.db.get_value("Guest", {"full_name": guest}, "name")

    # Create Reservation
    res = frappe.new_doc("Hotel Reservation")
    res.guest = guest_name
    res.room_type = rt
    res.room = room
    res.arrival_date = frappe.utils.nowdate()
    res.departure_date = frappe.utils.nowdate()
    res.status = "Reserved"
    res.insert()
    frappe.db.commit()
    print(f"Created Reservation: {res.name}, Folio: {res.folio}")

    # Check In
    print("Checking In...")
    res = frappe.get_doc("Hotel Reservation", res.name) # Fresh fetch
    res.process_check_in()
    frappe.db.commit()
    print("Checked In.")

    # Verify status
    res.reload()
    print(f"Status after Check-in: {res.status}")

    # Check Out
    print("Checking Out...")
    # This mirrors the whitelisted method: fetch doc, call process_check_out
    res = frappe.get_doc("Hotel Reservation", res.name)
    try:
        res.process_check_out()
        frappe.db.commit()
        print("Checked Out Successfully.")
    except Exception as e:
        print(f"Checkout Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        debug_checkout()
    except Exception as e:
        print(e)

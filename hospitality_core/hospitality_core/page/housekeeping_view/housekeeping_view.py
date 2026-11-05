import frappe
from frappe import _
from hospitality_core.constants import RoomStatus
from hospitality_core.room_status import set_room_status


@frappe.whitelist()
def get_rooms_status():
    """
    Returns all enabled rooms ordered by room number for the Housekeeping grid view.
    """
    rooms = frappe.get_all(
        "Hotel Room",
        filters={"is_enabled": 1},
        fields=["name", "room_number", "status", "room_type", "floor"],
        order_by="room_number asc"
    )
    return rooms


@frappe.whitelist()
def toggle_room_status(room_number, action):
    """
    Action can be 'mark_dirty' or 'mark_clean'.
    """
    if action == "mark_dirty":
        room = frappe.get_doc("Hotel Room", room_number)
        if room.status == RoomStatus.OCCUPIED:
            frappe.throw(_("Cannot mark an Occupied room as Dirty."))
        set_room_status(room_number, RoomStatus.DIRTY, reason="Housekeeping View mark dirty")
        return {"status": RoomStatus.DIRTY}
    elif action == "mark_clean":
        room = frappe.get_doc("Hotel Room", room_number)
        if room.status != RoomStatus.DIRTY:
            frappe.throw(_("Only Dirty rooms can be marked as Clean. Current status: {0}").format(room.status))
        set_room_status(room_number, RoomStatus.AVAILABLE, reason="Housekeeping View mark clean")
        return {"status": RoomStatus.AVAILABLE}
    else:
        frappe.throw(_("Invalid action: {0}").format(action))


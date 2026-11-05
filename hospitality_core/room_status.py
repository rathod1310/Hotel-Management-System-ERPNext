import frappe
from frappe import _
from hospitality_core.constants import RoomStatus


def set_room_status(room_number, new_status, reason=None, reservation=None):
    """
    Central function for updating hotel room status.
    Ensures state transition integrity across the entire app.
    """
    if new_status not in RoomStatus.ALL:
        frappe.throw(_("Invalid room status: {0}").format(new_status))

    room = frappe.get_doc("Hotel Room", room_number)

    # If transitioning to Occupied, reservation should usually be provided or kept
    if new_status == RoomStatus.OCCUPIED and reservation:
        room.current_reservation = reservation
    elif new_status != RoomStatus.OCCUPIED and not reservation:
        room.current_reservation = None

    old_status = room.status
    room.status = new_status
    if reason:
        room.add_comment("Comment", _("Status changed from {0} to {1}: {2}").format(old_status, new_status, reason))

    room.flags.ignore_permissions = True
    room.save()
    return room


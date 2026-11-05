import frappe
from frappe import _
from frappe.model.document import Document
from hospitality_core.constants import RoomStatus
from hospitality_core.room_status import set_room_status


class HotelRoom(Document):
    pass


@frappe.whitelist()
def mark_dirty(room_number):
    room = frappe.get_doc("Hotel Room", room_number)
    if room.status == RoomStatus.OCCUPIED:
        frappe.throw(_("Cannot mark an Occupied room as Dirty."))
    set_room_status(room_number, RoomStatus.DIRTY, reason="Manual mark dirty")
    return {"status": RoomStatus.DIRTY}


@frappe.whitelist()
def mark_clean(room_number):
    room = frappe.get_doc("Hotel Room", room_number)
    if room.status != RoomStatus.DIRTY:
        frappe.throw(_("Only Dirty rooms can be marked as Clean. Current status: {0}").format(room.status))
    set_room_status(room_number, RoomStatus.AVAILABLE, reason="Manual mark clean")
    return {"status": RoomStatus.AVAILABLE}


@frappe.whitelist()
def bulk_mark_clean(room_numbers):
    import json
    if isinstance(room_numbers, str):
        room_numbers = json.loads(room_numbers)

    updated = []
    for r in room_numbers:
        room = frappe.get_doc("Hotel Room", r)
        if room.status == RoomStatus.DIRTY:
            set_room_status(r, RoomStatus.AVAILABLE, reason="Bulk mark clean")
            updated.append(r)
    return updated


@frappe.whitelist()
def send_to_maintenance(room_number, description=None):
    room = frappe.get_doc("Hotel Room", room_number)
    # Create Issue
    issue = frappe.new_doc("Issue")
    issue.subject = _("Maintenance: Room {0}").format(room_number)
    issue.hotel_room = room_number
    issue.description = description or _("Maintenance requested for Room {0}").format(room_number)
    issue.status = "Open"
    if room.current_reservation:
        issue.hotel_reservation = room.current_reservation
    issue.insert(ignore_permissions=True)

    # Room status rule: if not occupied, go to Out of Order
    if room.status != RoomStatus.OCCUPIED:
        set_room_status(room_number, RoomStatus.OUT_OF_ORDER, reason=_("Issue {0} opened").format(issue.name))
    else:
        frappe.msgprint(_("Issue {0} created. Room is currently Occupied; it will transition to Out of Order once vacated.").format(issue.name))

    return {"issue": issue.name}

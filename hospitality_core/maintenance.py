import frappe
from frappe import _
from hospitality_core.constants import RoomStatus
from hospitality_core.room_status import set_room_status
from hospitality_core.utils import get_settings


def on_issue_update(doc, method):
    """
    doc_events hook on Issue.
    Only acts when hotel_room is set.
    """
    if not doc.hotel_room:
        return

    room = frappe.get_doc("Hotel Room", doc.hotel_room)

    # 1. Issue Opened / Reopened
    if doc.status in ["Open", "Replied", "Hold"]:
        if room.status == RoomStatus.OCCUPIED:
            frappe.msgprint(_("Room {0} is currently Occupied. Please move the guest; the room will go Out of Order when vacated.").format(
                room.name
            ))
        elif room.status in [RoomStatus.AVAILABLE, RoomStatus.DIRTY]:
            set_room_status(room.name, RoomStatus.OUT_OF_ORDER, reason=_("Issue {0} {1}").format(doc.name, doc.status))

    # 2. Issue Resolved / Closed
    elif doc.status in ["Resolved", "Closed"]:
        # If room is Out of Order, verify if any other open Issue exists for this room
        if room.status == RoomStatus.OUT_OF_ORDER:
            other_open = frappe.db.sql("""
                SELECT name FROM `tabIssue`
                WHERE hotel_room = %s
                AND name != %s
                AND status IN ('Open', 'Replied', 'Hold')
            """, (room.name, doc.name))

            if not other_open:
                settings = get_settings()
                target_status = settings.status_after_maintenance or RoomStatus.AVAILABLE
                set_room_status(room.name, target_status, reason=_("All issues resolved (closed {0})").format(doc.name))


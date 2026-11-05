import frappe
from frappe import _


def get_settings():
    """Returns cached Hotel Settings single doc."""
    return frappe.get_cached_doc("Hotel Settings")


def get_company():
    """Returns default company from Hotel Settings or user defaults."""
    settings = get_settings()
    if settings.company:
        return settings.company
    company = frappe.defaults.get_user_default("Company")
    if not company:
        frappe.throw(_("Please configure default Company in Hotel Settings or User Defaults."))
    return company


def get_room_item(room_type):
    """
    Returns the billable Item code for a room type.
    Falls back to Hotel Settings default_room_item.
    Throws a descriptive error if neither is set.
    """
    item = frappe.db.get_value("Hotel Room Type", room_type, "item")
    if item:
        return item
    settings = get_settings()
    if settings.default_room_item:
        return settings.default_room_item
    frappe.throw(_("No billable Room Item found for Room Type '{0}' or in Hotel Settings.").format(room_type))


def boot_session(bootinfo):
    """Exposes hotel settings to client-side JS."""
    try:
        settings = get_settings()
        bootinfo.hotel_settings = {
            "company": settings.company,
            "default_room_item": settings.default_room_item,
            "guest_customer_group": settings.guest_customer_group,
            "guest_territory": settings.guest_territory,
            "sales_taxes_template": settings.sales_taxes_template,
            "cost_center": settings.cost_center,
            "status_after_maintenance": settings.status_after_maintenance or "Available",
            "allow_checkin_before_arrival": bool(settings.allow_checkin_before_arrival),
            "block_checkout_if_balance": bool(settings.block_checkout_if_balance),
            "balance_tolerance": float(settings.balance_tolerance or 0.0),
            "min_billable_nights": int(settings.min_billable_nights or 1)
        }
    except Exception:
        bootinfo.hotel_settings = {}


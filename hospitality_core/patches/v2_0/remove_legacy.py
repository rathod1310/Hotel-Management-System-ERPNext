import frappe


def execute():
    # 1. DocTypes to delete
    doctypes_to_remove = [
        "Guest Folio",
        "Folio Transaction",
        "Folio Transaction Move Log",
        "Guest Balance Ledger",
        "Hospitality Expense",
        "Hospitality Expense Tax",
        "Expense Category",
        "Hospitality Accounting Settings",
        "Hotel Maintenance Request",
        "Hotel Reception",
        "Hotel Group Booking",
        "Hotel Group Booking Room",
        "Allowance Reason Code",
        "EOD Closing Entry",
        "EOD Discrepancies",
        "EOD Expense Breakdown",
        "EOD Item Group Sales",
        "EOD Item Sales",
        "EOD Payment Summary",
        "EOD POS Profile",
        "EOD Stock Balance",
        "Item Recipe",
        "Recipe Ingredient",
        "Lost and Found Item",
        "Reservation Routing",
        "SalesReport",
        "Guest"
    ]

    for dt in doctypes_to_remove:
        if frappe.db.exists("DocType", dt):
            # Clean records first
            try:
                frappe.db.delete(dt)
            except Exception:
                pass
            frappe.delete_doc("DocType", dt, force=1, ignore_permissions=True)

    # 2. Pages to delete
    pages_to_remove = ["guest_360", "housekeeping_view"]
    for p in pages_to_remove:
        if frappe.db.exists("Page", p):
            frappe.delete_doc("Page", p, force=1, ignore_permissions=True)

    # 3. Workspaces to delete
    if frappe.db.exists("Workspace", "hospitality_analytics"):
        frappe.delete_doc("Workspace", "hospitality_analytics", force=1, ignore_permissions=True)

    # 4. Reports to delete
    reports_to_remove = [
        "City Ledger",
        "Daily Payment Collection",
        "Daily Sales Consumption",
        "Discount and Complimentary Report",
        "Financial Activity Summary",
        "Folio Balance Summary",
        "Folio Transaction Move Report",
        "Frontdesk End of Day Report",
        "Gross Revenue Report",
        "Guest Ledger",
        "Guest List",
        "Hospitality Expense Report",
        "Hotel Performance Analytics",
        "Lost and Found Register",
        "Maintenance Log Report",
        "Point of Sale Report",
        "POS Sales Summary",
        "Reservations Report",
        "Room Only Sales",
        "Taxes and Charges Report",
        "Void and Allowance Report"
    ]
    for r in reports_to_remove:
        if frappe.db.exists("Report", r):
            frappe.delete_doc("Report", r, force=1, ignore_permissions=True)

    # 5. Dashboards & charts
    if frappe.db.exists("Dashboard", "Hospitality Analytics"):
        frappe.delete_doc("Dashboard", "Hospitality Analytics", force=1, ignore_permissions=True)

    # 6. Legacy Custom Fields
    legacy_cf = [
        "hotel_reception",
        "room_number",
        "cashier",
        "guest_name"
    ]
    for cf in legacy_cf:
        frappe.db.sql("DELETE FROM `tabCustom Field` WHERE fieldname = %s AND module = 'Hospitality Core'", cf)

    frappe.db.commit()


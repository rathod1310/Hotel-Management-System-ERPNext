import frappe
from frappe import _
from frappe.model.document import Document


class HotelSettings(Document):
    pass


@frappe.whitelist()
def create_pos_profiles(company=None, warehouse=None, selling_price_list=None, payment_method=None):
    """
    Creates standard Restaurant and Room POS profiles based on configured hotel settings.
    Profile names are not hardcoded but dynamically created or referenced and saved to Hotel Settings.
    """
    settings = frappe.get_single("Hotel Settings")
    company = company or settings.company
    if not company:
        frappe.throw(_("Please select a Company first in Hotel Settings."))

    company_doc = frappe.get_doc("Company", company)

    if not warehouse:
        warehouse = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0}, "name")
        if not warehouse:
            frappe.throw(_("No active warehouse found for company {0}.").format(company))

    if not selling_price_list:
        selling_price_list = frappe.db.get_value("Price List", {"selling": 1, "enabled": 1}, "name") or "Standard Selling"

    # Find valid payment methods for this company that have an account configured
    valid_modes = frappe.db.sql("""
        SELECT a.parent as mode_of_payment, a.default_account
        FROM `tabMode of Payment Account` a
        JOIN `tabMode of Payment` m ON m.name = a.parent
        WHERE a.company = %s AND m.enabled = 1 AND a.default_account IS NOT NULL AND a.default_account != ''
    """, (company,), as_dict=True)

    if not valid_modes:
        cash_account = company_doc.default_cash_account or frappe.db.get_value("Account", {"company": company, "account_type": "Cash", "is_group": 0}, "name")
        cash_mode = frappe.db.get_value("Mode of Payment", {"type": "Cash", "enabled": 1}, "name") or "Cash"
        if cash_account and cash_mode:
            frappe.get_doc({
                "doctype": "Mode of Payment Account",
                "parent": cash_mode,
                "parenttype": "Mode of Payment",
                "parentfield": "accounts",
                "company": company,
                "default_account": cash_account
            }).insert(ignore_permissions=True)
            valid_modes = [{"mode_of_payment": cash_mode, "default_account": cash_account}]
        else:
            frappe.throw(_("No Mode of Payment with a configured default account was found for company {0}.").format(company))

    pos_payments = []
    for idx, vm in enumerate(valid_modes):
        pos_payments.append({
            "mode_of_payment": vm.mode_of_payment,
            "default": 1 if idx == 0 else 0,
            "account": vm.default_account
        })

    cost_center = settings.cost_center or company_doc.cost_center
    write_off_account = company_doc.write_off_account or frappe.db.get_value("Account", {"company": company, "account_type": "Expense Account", "is_group": 0}, "name")
    write_off_cost_center = cost_center

    created_profiles = {}

    # 1. Restaurant Profile
    rest_profile_name = f"{company} - Restaurant"
    if not frappe.db.exists("POS Profile", rest_profile_name):
        rest_doc = frappe.get_doc({
            "doctype": "POS Profile",
            "name": rest_profile_name,
            "company": company,
            "warehouse": warehouse,
            "selling_price_list": selling_price_list,
            "income_account": company_doc.default_income_account,
            "cost_center": cost_center,
            "write_off_account": write_off_account,
            "write_off_cost_center": write_off_cost_center,
            "allow_partial_payment": 0,
            "update_stock": 1,
            "payments": pos_payments
        })
        rest_doc.insert(ignore_permissions=True)
    created_profiles["restaurant"] = rest_profile_name

    # 2. Room Service Profile
    room_profile_name = f"{company} - Room Service"
    if not frappe.db.exists("POS Profile", room_profile_name):
        room_doc = frappe.get_doc({
            "doctype": "POS Profile",
            "name": room_profile_name,
            "company": company,
            "warehouse": warehouse,
            "selling_price_list": selling_price_list,
            "income_account": company_doc.default_income_account,
            "cost_center": cost_center,
            "write_off_account": write_off_account,
            "write_off_cost_center": write_off_cost_center,
            "allow_partial_payment": 0,
            "update_stock": 1,
            "payments": pos_payments
        })
        room_doc.insert(ignore_permissions=True)
    created_profiles["room"] = room_profile_name

    # Update Hotel Settings
    settings.restaurant_pos_profile = rest_profile_name
    settings.room_pos_profile = room_profile_name
    if not settings.default_advance_mode:
        settings.default_advance_mode = pos_payments[0]["mode_of_payment"]
    settings.save(ignore_permissions=True)

    return created_profiles

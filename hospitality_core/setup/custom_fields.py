import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def get_custom_fields():
    return {
        "Customer": [
            {
                "fieldname": "is_hotel_guest",
                "label": "Is Hotel Guest",
                "fieldtype": "Check",
                "default": "0",
                "insert_after": "customer_type"
            },
            {
                "fieldname": "guest_id_type",
                "label": "Guest ID Type",
                "fieldtype": "Select",
                "options": "\nPassport\nNational ID\nDriving License\nOther",
                "depends_on": "eval:doc.is_hotel_guest==1",
                "insert_after": "is_hotel_guest"
            },
            {
                "fieldname": "guest_id_number",
                "label": "Guest ID Number",
                "fieldtype": "Data",
                "depends_on": "eval:doc.is_hotel_guest==1",
                "insert_after": "guest_id_type"
            }
        ],
        "Payment Entry": [
            {
                "fieldname": "hotel_reservation",
                "label": "Hotel Reservation",
                "fieldtype": "Link",
                "options": "Hotel Reservation",
                "insert_after": "party_name"
            }
        ],
        "Sales Invoice": [
            {
                "fieldname": "hotel_reservation",
                "label": "Hotel Reservation",
                "fieldtype": "Link",
                "options": "Hotel Reservation",
                "read_only": 1,
                "insert_after": "customer"
            }
        ],
        "Issue": [
            {
                "fieldname": "hotel_room",
                "label": "Hotel Room",
                "fieldtype": "Link",
                "options": "Hotel Room",
                "insert_after": "customer"
            },
            {
                "fieldname": "hotel_reservation",
                "label": "Hotel Reservation",
                "fieldtype": "Link",
                "options": "Hotel Reservation",
                "insert_after": "hotel_room"
            }
        ]
    }


def setup_custom_fields():
    custom_fields = get_custom_fields()
    create_custom_fields(custom_fields, ignore_validate=True)


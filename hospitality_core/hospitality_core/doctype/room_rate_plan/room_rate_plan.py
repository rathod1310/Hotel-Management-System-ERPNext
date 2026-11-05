import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class RoomRatePlan(Document):
    def validate(self):
        self.validate_dates()
        if self.active:
            self.validate_overlap()

    def validate_dates(self):
        if getdate(self.valid_from) > getdate(self.valid_to):
            frappe.throw(_("Valid From date cannot be after Valid To date."))

    def validate_overlap(self):
        """
        Ensure no other Active rate plan exists for this Room Type
        and customer / customer_group within the overlapping date range.
        """
        conditions = [
            "room_type = %(room_type)s",
            "name != %(name)s",
            "active = 1",
            "valid_from <= %(valid_to)s",
            "valid_to >= %(valid_from)s"
        ]
        values = {
            "room_type": self.room_type,
            "name": self.name or "New Rate Plan",
            "valid_from": self.valid_from,
            "valid_to": self.valid_to
        }

        if self.customer:
            conditions.append("customer = %(customer)s")
            values["customer"] = self.customer
        else:
            conditions.append("(customer IS NULL OR customer = '')")

        if self.customer_group:
            conditions.append("customer_group = %(customer_group)s")
            values["customer_group"] = self.customer_group
        else:
            conditions.append("(customer_group IS NULL OR customer_group = '')")

        overlapping = frappe.db.sql(
            f"""
            SELECT name FROM `tabRoom Rate Plan`
            WHERE {" AND ".join(conditions)}
            """,
            values
        )

        if overlapping:
            frappe.throw(
                _("Rate Plan overlaps with existing active plan: {0} for Room Type {1}").format(
                    overlapping[0][0], self.room_type
                )
            )

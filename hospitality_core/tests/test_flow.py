import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, nowdate
from hospitality_core.constants import RoomStatus, ReservationStatus
from hospitality_core.hospitality_core.doctype.hotel_reservation.hotel_reservation import (
    check_in,
    move_room,
    check_out,
    get_billing_summary
)
from hospitality_core.hospitality_core.doctype.hotel_room.hotel_room import mark_clean, send_to_maintenance


class TestHotelFlow(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = frappe.db.get_single_value("Global Defaults", "default_company")
        if not cls.company:
            cls.company = frappe.get_all("Company", limit=1)[0].name

        company_doc = frappe.get_doc("Company", cls.company)
        cls.currency = company_doc.default_currency or "INR"
        cls.paid_to = frappe.db.get_value("Account", {"company": cls.company, "account_type": "Cash"})
        cls.paid_from = company_doc.default_receivable_account or frappe.db.get_value("Account", {"company": cls.company, "account_type": "Receivable"})

        cls.item_code = "HOTEL-ROOM-SERVICE"
        if not frappe.db.exists("Item", cls.item_code):
            item = frappe.get_doc({
                "doctype": "Item",
                "item_code": cls.item_code,
                "item_name": "Hotel Room Rent Service",
                "item_group": "Services",
                "is_stock_item": 0
            })
            item.insert(ignore_permissions=True)

        settings = frappe.get_doc("Hotel Settings")
        settings.company = cls.company
        settings.default_room_item = cls.item_code
        settings.status_after_maintenance = RoomStatus.AVAILABLE
        settings.allow_checkin_before_arrival = 1
        settings.block_checkout_if_balance = 1
        settings.balance_tolerance = 0.0
        settings.min_billable_nights = 1
        settings.save(ignore_permissions=True)

        cls.room_type = "Deluxe Suite"
        if not frappe.db.exists("Hotel Room Type", cls.room_type):
            rt = frappe.get_doc({
                "doctype": "Hotel Room Type",
                "room_type_name": cls.room_type,
                "default_rate": 200.0,
                "item": cls.item_code
            })
            rt.insert(ignore_permissions=True)

        cls.rooms = ["RM-101", "RM-102", "RM-103"]
        for r_num in cls.rooms:
            if not frappe.db.exists("Hotel Room", r_num):
                r = frappe.get_doc({
                    "doctype": "Hotel Room",
                    "room_number": r_num,
                    "room_type": cls.room_type,
                    "status": RoomStatus.AVAILABLE,
                    "is_enabled": 1
                })
                r.insert(ignore_permissions=True)
            else:
                r = frappe.get_doc("Hotel Room", r_num)
                r.status = RoomStatus.AVAILABLE
                r.is_enabled = 1
                r.current_reservation = None
                r.save(ignore_permissions=True)

        cls.plan_name = "Summer Discount"
        if not frappe.db.exists("Room Rate Plan", cls.plan_name):
            plan = frappe.get_doc({
                "doctype": "Room Rate Plan",
                "plan_name": cls.plan_name,
                "room_type": cls.room_type,
                "rate": 150.0,
                "valid_from": add_days(nowdate(), -10),
                "valid_to": add_days(nowdate(), 20),
                "active": 1
            })
            plan.insert(ignore_permissions=True)

        cls.customer_name = "John Test Doe"
        if not frappe.db.exists("Customer", cls.customer_name):
            cust = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": cls.customer_name,
                "customer_type": "Individual",
                "is_hotel_guest": 1
            })
            cust.insert(ignore_permissions=True)

    def test_complete_hotel_lifecycle(self):
        today = getdate(nowdate())
        checkout_date = add_days(today, 2)

        # 3. Create Reservation for 2 nights
        res = frappe.get_doc({
            "doctype": "Hotel Reservation",
            "company": self.company,
            "customer": self.customer_name,
            "room_type": self.room_type,
            "room": self.rooms[0],
            "check_in_date": today,
            "check_out_date": checkout_date,
            "adults": 1
        })
        res.insert(ignore_permissions=True)

        # Rate must come from plan (150)
        self.assertEqual(res.stays[0].rate, 150.0)

        # Double booking check: same room & dates must fail
        dup_res = frappe.get_doc({
            "doctype": "Hotel Reservation",
            "company": self.company,
            "customer": self.customer_name,
            "room_type": self.room_type,
            "room": self.rooms[0],
            "check_in_date": today,
            "check_out_date": checkout_date
        })
        self.assertRaises(frappe.ValidationError, dup_res.insert)

        # 4. Check in: room Occupied, reservation Checked In
        check_in(res.name)
        res.reload()
        room1 = frappe.get_doc("Hotel Room", self.rooms[0])
        self.assertEqual(res.status, ReservationStatus.CHECKED_IN)
        self.assertEqual(room1.status, RoomStatus.OCCUPIED)

        # 5. Issue on room 1 -> stays Occupied
        issue = frappe.get_doc({
            "doctype": "Issue",
            "subject": f"AC not working in {self.rooms[0]}",
            "hotel_room": self.rooms[0],
            "status": "Open"
        })
        issue.insert(ignore_permissions=True)
        room1.reload()
        self.assertEqual(room1.status, RoomStatus.OCCUPIED)

        # 6. Move room to room 2: room 1 -> Out of Order (open Issue), room 2 Occupied
        move_room(res.name, self.rooms[1], reason="AC Issue", keep_rate=1)
        res.reload()
        room1.reload()
        room2 = frappe.get_doc("Hotel Room", self.rooms[1])

        self.assertEqual(len(res.stays), 2)
        self.assertEqual(room1.status, RoomStatus.OUT_OF_ORDER)
        self.assertEqual(room2.status, RoomStatus.OCCUPIED)

        # 7. Billing summary & check-out block
        billing = get_billing_summary(res.name)
        self.assertGreater(billing["estimated_total"], 0)

        # Check out with balance > 0 must fail
        self.assertRaises(frappe.ValidationError, check_out, res.name)

        # 8. Receive full payment via standard Payment Entry
        pe = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "party_type": "Customer",
            "party": self.customer_name,
            "company": self.company,
            "hotel_reservation": res.name,
            "paid_to": self.paid_to,
            "paid_from": self.paid_from,
            "paid_to_account_currency": self.currency,
            "paid_from_account_currency": self.currency,
            "source_exchange_rate": 1.0,
            "target_exchange_rate": 1.0,
            "paid_amount": billing["estimated_total"],
            "received_amount": billing["estimated_total"]
        })
        pe.insert(ignore_permissions=True)
        pe.submit()

        # Check out: Sales Invoice submitted, room 2 -> Dirty, status Checked Out
        check_out(res.name)
        res.reload()
        room2.reload()
        self.assertEqual(res.status, ReservationStatus.CHECKED_OUT)
        self.assertTrue(bool(res.sales_invoice))
        self.assertEqual(room2.status, RoomStatus.DIRTY)

        # 9. Mark Clean room 2 -> Available
        mark_clean(self.rooms[1])
        room2.reload()
        self.assertEqual(room2.status, RoomStatus.AVAILABLE)

        # Resolve the issue on room 1 -> Available (status_after_maintenance)
        issue.status = "Resolved"
        issue.save(ignore_permissions=True)
        room1.reload()
        self.assertEqual(room1.status, RoomStatus.AVAILABLE)

        # 10. Send room 3 to maintenance: Out of Order & Issue exists
        send_to_maintenance(self.rooms[2], description="Broken tap")
        room3 = frappe.get_doc("Hotel Room", self.rooms[2])
        self.assertEqual(room3.status, RoomStatus.OUT_OF_ORDER)

        # Close the Issue: Available again
        room3_issue_name = frappe.db.get_value("Issue", {"hotel_room": self.rooms[2], "status": "Open"}, "name")
        self.assertTrue(bool(room3_issue_name))
        r3_issue = frappe.get_doc("Issue", room3_issue_name)
        r3_issue.status = "Closed"
        r3_issue.save(ignore_permissions=True)
        room3.reload()
        self.assertEqual(room3.status, RoomStatus.AVAILABLE)

        # 11. Back-to-back reservation (start = checkout_date) must succeed
        b2b_res = frappe.get_doc({
            "doctype": "Hotel Reservation",
            "company": self.company,
            "customer": self.customer_name,
            "room_type": self.room_type,
            "room": self.rooms[0],
            "check_in_date": checkout_date,
            "check_out_date": add_days(checkout_date, 2)
        })
        b2b_res.insert(ignore_permissions=True)
        self.assertTrue(bool(b2b_res.name))

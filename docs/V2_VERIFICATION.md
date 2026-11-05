# Hospitality Core v2: Verification of ERPNext v17 POS Facts

Verified against ERPNext v17 develop source tree at `/home/frappe/frappe-bench/apps/erpnext` and Frappe at `/home/frappe/frappe-bench/apps/frappe`.

---

### Fact 1: POS Settings `invoice_type` & POS Invoice Blocking
- **File**: `/home/frappe/frappe-bench/apps/erpnext/erpnext/accounts/doctype/pos_settings/pos_settings.json`
- **Confirmation**: `invoice_type` field exists with default `Sales Invoice`.
- **File**: `/home/frappe/frappe-bench/apps/erpnext/erpnext/accounts/doctype/pos_invoice/pos_invoice.py`
- **Confirmation**: Line raises `frappe.throw(_("Sales Invoice mode is activated in POS"))` when attempting to create POS Invoice under Sales Invoice mode.
- **Status**: **CONFIRMED**

---

### Fact 2: POS Profile Fields
- **File**: `/home/frappe/frappe-bench/apps/erpnext/erpnext/accounts/doctype/pos_profile/pos_profile.json`
- **Confirmation**: All required fields confirmed:
  - `customer` (Link Customer)
  - `company` (Link Company)
  - `payments` (Table POS Payment Method)
  - `warehouse` (Link Warehouse)
  - `update_stock` (Check, default 1)
  - `taxes_and_charges` (Link Sales Taxes and Charges Template)
  - `income_account` (Link Account)
  - `cost_center` (Link Cost Center)
  - `selling_price_list` (Link Price List)
  - `item_groups` (Table POS Item Group)
  - `applicable_for_users` (Table POS Profile User)
  - `allow_partial_payment` (Check, default 0)
- **Status**: **CONFIRMED**

---

### Fact 3: Partial Payment Restriction
- **Files**:
  - `/home/frappe/frappe-bench/apps/erpnext/erpnext/accounts/doctype/sales_invoice/sales_invoice.py`
  - `/home/frappe/frappe-bench/apps/erpnext/erpnext/accounts/doctype/sales_invoice/services/pos.py`
- **Confirmation**: `PartialPaymentValidationError` is thrown when `allow_partial_payment` is 0 and payment is incomplete or zero on submission.
- **Status**: **CONFIRMED**

---

### Fact 4: Draft Invoices in POS UI (`save_and_checkout`)
- **File**: `/home/frappe/frappe-bench/apps/erpnext/erpnext/selling/page/point_of_sale/pos_controller.js`
- **Confirmation**: `save_and_checkout` method saves the Sales Invoice as Draft (`docstatus = 0`). Drafts appear under Recent Orders for editing/checkout.
- **Status**: **CONFIRMED**

---

### Fact 5: POS Opening Entry Required Fields
- **File**: `/home/frappe/frappe-bench/apps/erpnext/erpnext/accounts/doctype/pos_opening_entry/pos_opening_entry.json`
- **Confirmation**: Contains `period_start_date`, `posting_date`, `company`, `pos_profile`, `user`, `balance_details`.
- **Status**: **CONFIRMED**

---

### Fact 6: `page_js` Hook Support in Frappe
- **File**: `/home/frappe/frappe-bench/apps/frappe/frappe/core/doctype/page/page.py:306`
- **Confirmation**: `get_code_files_via_hooks("page_js", self.name)` dynamically injects custom scripts for pages like `point-of-sale`.
- **Status**: **CONFIRMED**

---

### Fact 7: DOM Element `.submit-order-btn`
- **File**: `/home/frappe/frappe-bench/apps/erpnext/erpnext/selling/page/point_of_sale/pos_payment.js`
- **Confirmation**: Payment component renders `.submit-order-btn` ("Complete Order").
- **Status**: **CONFIRMED**

---

### Fact 8: POS Closing Entry Ignores Drafts
- **File**: `/home/frappe/frappe-bench/apps/erpnext/erpnext/accounts/doctype/pos_closing_entry/pos_closing_entry.py:498`
- **Confirmation**: Queries explicitly filter `(InvoiceDocType.docstatus == 1)`, completely ignoring drafts (`docstatus = 0`).
- **Status**: **CONFIRMED**

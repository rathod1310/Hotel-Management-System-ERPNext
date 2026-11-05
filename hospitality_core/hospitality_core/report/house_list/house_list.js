frappe.query_reports["House List"] = {
    "filters": [
        {
            "fieldname": "date",
            "label": __("Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        }
    ]
};

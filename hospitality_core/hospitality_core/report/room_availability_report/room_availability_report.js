frappe.query_reports["Room Availability Report"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.now_date(),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_days(frappe.datetime.now_date(), 14),
            "reqd": 1
        },
        {
            "fieldname": "room_type",
            "label": __("Room Type"),
            "fieldtype": "Link",
            "options": "Hotel Room Type"
        }
    ],
    "formatter": function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "available") {
            if (data.available <= 0) {
                value = `<span style="color:red; font-weight:bold;">${value}</span>`;
            } else if (data.available < 5) {
                value = `<span style="color:orange; font-weight:bold;">${value}</span>`;
            } else {
                value = `<span style="color:green; font-weight:bold;">${value}</span>`;
            }
        }
        return value;
    }
};

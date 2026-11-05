frappe.query_reports["Daily Departures"] = {
    "filters": [
        {
            "fieldname": "date",
            "label": __("Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.now_date(),
            "reqd": 1
        }
    ],
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        
        if (column.fieldname == "checkout_status") {
            if (data.checkout_status == "Overstay") {
                value = `<span style="color:red; font-weight:bold;">${value}</span>`;
            } else if (data.checkout_status == "Completed") {
                value = `<span style="color:green;">${value}</span>`;
            }
        }
        return value;
    }
};
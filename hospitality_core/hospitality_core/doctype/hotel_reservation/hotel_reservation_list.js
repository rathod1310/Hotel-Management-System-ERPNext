frappe.listview_settings['Hotel Reservation'] = {
    add_fields: ["status"],
    get_indicator: function (doc) {
        var colors = {
            "Reserved": "orange",
            "Checked In": "green",
            "Checked Out": "gray",
            "Cancelled": "red"
        };
        return [__(doc.status), colors[doc.status] || "grey", "status,=," + doc.status];
    }
};

frappe.listview_settings["Hotel Room"] = {
    add_fields: ["status", "is_enabled", "room_type"],
    get_indicator(doc) {
        if (!doc.is_enabled) {
            return [__("Disabled"), "gray", "is_enabled,=,0"];
        }
        if (doc.status === "Available") {
            return [__("Available"), "green", "status,=,Available"];
        } else if (doc.status === "Occupied") {
            return [__("Occupied"), "blue", "status,=,Occupied"];
        } else if (doc.status === "Dirty") {
            return [__("Dirty"), "orange", "status,=,Dirty"];
        } else if (doc.status === "Out of Order") {
            return [__("Out of Order"), "red", "status,=,Out of Order"];
        }
    },
    onload(listview) {
        listview.page.add_action_item(__("Mark Clean"), function () {
            const checked_items = listview.get_checked_items();
            if (!checked_items.length) return;

            const room_numbers = checked_items.map((d) => d.name);
            frappe.call({
                method: "hospitality_core.hospitality_core.doctype.hotel_room.hotel_room.bulk_mark_clean",
                args: { room_numbers: room_numbers },
                callback: function (r) {
                    listview.refresh();
                }
            });
        });
    }
};


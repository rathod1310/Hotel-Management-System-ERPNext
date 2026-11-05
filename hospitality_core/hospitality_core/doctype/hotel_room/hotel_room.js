frappe.ui.form.on("Hotel Room", {
    refresh(frm) {
        if (!frm.is_new()) {
            if (frm.doc.status === "Dirty") {
                frm.add_custom_button(__("Mark Clean"), () => {
                    frappe.call({
                        method: "hospitality_core.hospitality_core.doctype.hotel_room.hotel_room.mark_clean",
                        args: { room_number: frm.doc.room_number },
                        callback: () => {
                            frm.reload_doc();
                        }
                    });
                }).addClass("btn-primary");
            } else if (frm.doc.status === "Available") {
                frm.add_custom_button(__("Mark Dirty"), () => {
                    frappe.call({
                        method: "hospitality_core.hospitality_core.doctype.hotel_room.hotel_room.mark_dirty",
                        args: { room_number: frm.doc.room_number },
                        callback: () => {
                            frm.reload_doc();
                        }
                    });
                });
            }

            frm.add_custom_button(__("Send to Maintenance"), () => {
                frappe.prompt(
                    [
                        {
                            label: __("Description"),
                            fieldname: "description",
                            fieldtype: "Small Text",
                            reqd: 1
                        }
                    ],
                    (values) => {
                        frappe.call({
                            method: "hospitality_core.hospitality_core.doctype.hotel_room.hotel_room.send_to_maintenance",
                            args: {
                                room_number: frm.doc.room_number,
                                description: values.description
                            },
                            callback: (r) => {
                                if (r.message && r.message.issue) {
                                    frappe.show_alert({
                                        message: __("Issue {0} created", [r.message.issue]),
                                        indicator: "green"
                                    });
                                }
                                frm.reload_doc();
                            }
                        });
                    },
                    __("Send Room {0} to Maintenance", [frm.doc.room_number]),
                    __("Create Issue")
                );
            });
        }
    }
});


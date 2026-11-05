frappe.ui.form.on("Hotel Settings", {
    refresh(frm) {
        frm.add_custom_button(__("Create POS Profiles"), function() {
            frappe.confirm(
                __("This will automatically create standard Restaurant and Room Service POS profiles for {0} and configure them in Hotel Settings. Continue?", [frm.doc.company || __("the selected company")]),
                function() {
                    frappe.call({
                        method: "hospitality_core.hospitality_core.doctype.hotel_settings.hotel_settings.create_pos_profiles",
                        args: { company: frm.doc.company },
                        freeze: true,
                        callback: function(r) {
                            if (!r.exc && r.message) {
                                frappe.msgprint({
                                    title: __("Profiles Configured"),
                                    indicator: "green",
                                    message: __("Created/Configured Profiles:<br><b>Restaurant:</b> {0}<br><b>Room:</b> {1}", [r.message.restaurant, r.message.room])
                                });
                                frm.reload_doc();
                            }
                        }
                    });
                }
            );
        }, __("Actions"));
    }
});


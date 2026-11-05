frappe.ui.form.on("Hotel Reservation", {
    refresh(frm) {
        frm.trigger("render_buttons");
        if (!frm.is_new()) {
            frm.trigger("refresh_billing_summary");
        }
    },

    customer(frm) {
        if (frm.doc.customer && frm.doc.room_type && frm.doc.check_in_date) {
            frm.trigger("update_rate_and_stays");
        }
    },

    room_type(frm) {
        frm.set_value("room", "");
        if (frm.doc.room_type && frm.doc.check_in_date && frm.doc.check_out_date) {
            frm.set_query("room", () => {
                return {
                    query: "hospitality_core.hospitality_core.doctype.hotel_reservation.hotel_reservation.get_available_rooms",
                    filters: {
                        room_type: frm.doc.room_type,
                        check_in_date: frm.doc.check_in_date,
                        check_out_date: frm.doc.check_out_date,
                        exclude_reservation: frm.doc.name
                    }
                };
            });
            frm.trigger("update_rate_and_stays");
        }
    },

    check_in_date(frm) {
        if (frm.doc.room_type && frm.doc.check_in_date && frm.doc.check_out_date) {
            frm.trigger("update_rate_and_stays");
        }
    },

    check_out_date(frm) {
        if (frm.doc.room_type && frm.doc.check_in_date && frm.doc.check_out_date) {
            frm.trigger("update_rate_and_stays");
        }
    },

    update_rate_and_stays(frm) {
        if (!frm.doc.room_type || !frm.doc.check_in_date || !frm.doc.check_out_date) return;
        frappe.call({
            method: "hospitality_core.hospitality_core.doctype.hotel_reservation.hotel_reservation.get_room_rate",
            args: {
                room_type: frm.doc.room_type,
                date: frm.doc.check_in_date,
                customer: frm.doc.customer
            },
            callback: (r) => {
                const rate = r.message || 0;
                if (!frm.doc.stays || frm.doc.stays.length === 0) {
                    frm.clear_table("stays");
                    const row = frm.add_child("stays");
                    row.room = frm.doc.room;
                    row.room_type = frm.doc.room_type;
                    row.from_date = frm.doc.check_in_date;
                    row.to_date = frm.doc.check_out_date;
                    row.rate = rate;
                    row.nights = frappe.datetime.get_diff(frm.doc.check_out_date, frm.doc.check_in_date) || 1;
                    frm.refresh_field("stays");
                }
            }
        });
    },

    refresh_billing_summary(frm) {
        frappe.call({
            method: "hospitality_core.hospitality_core.doctype.hotel_reservation.hotel_reservation.get_billing_summary",
            args: { reservation_name: frm.doc.name },
            callback: (r) => {
                if (r.message) {
                    frm.set_value("estimated_total", r.message.estimated_total);
                    frm.set_value("total_paid", r.message.total_paid);
                    frm.set_value("balance", r.message.balance);
                }
            }
        });
    },

    render_buttons(frm) {
        if (frm.is_new()) return;

        if (frm.doc.status === "Reserved") {
            frm.add_custom_button(__("Check In"), () => {
                frappe.call({
                    method: "hospitality_core.hospitality_core.doctype.hotel_reservation.hotel_reservation.check_in",
                    args: { reservation_name: frm.doc.name },
                    callback: () => {
                        frm.reload_doc();
                    }
                });
            }).addClass("btn-primary");

            frm.add_custom_button(__("Cancel Reservation"), () => {
                frappe.confirm(__("Are you sure you want to cancel this reservation?"), () => {
                    frappe.call({
                        method: "hospitality_core.hospitality_core.doctype.hotel_reservation.hotel_reservation.cancel_reservation",
                        args: { reservation_name: frm.doc.name },
                        callback: () => {
                            frm.reload_doc();
                        }
                    });
                });
            });
        } else if (frm.doc.status === "Checked In") {
            frm.add_custom_button(__("Move Room"), () => {
                frm.trigger("show_move_room_dialog");
            });

            frm.add_custom_button(__("Receive Payment"), () => {
                frappe.new_doc("Payment Entry", {
                    payment_type: "Receive",
                    party_type: "Customer",
                    party: frm.doc.customer,
                    company: frm.doc.company,
                    hotel_reservation: frm.doc.name
                });
            });

            frm.add_custom_button(__("Check Out"), () => {
                frappe.confirm(__("Are you sure you want to check out this guest and finalize billing?"), () => {
                    frappe.call({
                        method: "hospitality_core.hospitality_core.doctype.hotel_reservation.hotel_reservation.check_out",
                        args: { reservation_name: frm.doc.name },
                        callback: (r) => {
                            if (r.message && r.message.sales_invoice) {
                                frappe.show_alert({
                                    message: __("Check-out complete. Sales Invoice {0} created.", [r.message.sales_invoice]),
                                    indicator: "green"
                                });
                            }
                            frm.reload_doc();
                        }
                    });
                });
            }).addClass("btn-primary");
        } else if (frm.doc.status === "Checked Out" && frm.doc.sales_invoice) {
            frm.add_custom_button(__("View Sales Invoice"), () => {
                frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice);
            });
        }
    },

    show_move_room_dialog(frm) {
        const today = frappe.datetime.get_today();
        frappe.call({
            method: "hospitality_core.hospitality_core.doctype.hotel_reservation.hotel_reservation.get_available_rooms",
            args: {
                room_type: frm.doc.room_type,
                check_in_date: today,
                check_out_date: frm.doc.check_out_date,
                exclude_reservation: frm.doc.name
            },
            callback: (r) => {
                const rooms = (r.message || []).map((x) => ({ label: `${x.room_number} (${x.status})`, value: x.name }));
                const d = new frappe.ui.Dialog({
                    title: __("Move Room for Reservation {0}", [frm.doc.name]),
                    fields: [
                        {
                            label: __("New Room"),
                            fieldname: "new_room",
                            fieldtype: "Select",
                            options: rooms,
                            reqd: 1
                        },
                        {
                            label: __("Keep Current Rate"),
                            fieldname: "keep_rate",
                            fieldtype: "Check",
                            default: 1
                        },
                        {
                            label: __("Move Reason"),
                            fieldname: "reason",
                            fieldtype: "Small Text"
                        }
                    ],
                    primary_action_label: __("Move Room"),
                    primary_action(values) {
                        d.hide();
                        frappe.call({
                            method: "hospitality_core.hospitality_core.doctype.hotel_reservation.hotel_reservation.move_room",
                            args: {
                                reservation_name: frm.doc.name,
                                new_room: values.new_room,
                                reason: values.reason,
                                keep_rate: values.keep_rate ? 1 : 0
                            },
                            callback: () => {
                                frm.reload_doc();
                            }
                        });
                    }
                });
                d.show();
            }
        });
    }
});

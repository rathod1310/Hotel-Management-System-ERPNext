/**
 * Sky Hotel Management System - POS Extension
 * Extends standard ERPNext POS page (point-of-sale).
 * Provides:
 * 1. "Charge to Room" button for Room POS Profile
 * 2. In-house Guest picker (Room · Guest Name)
 * 3. Embedded mode styling (when inside console iframe overlay)
 */

(function () {
    // Configurable DOM selectors with safe fallbacks
    const SELECTORS = {
        submit_btn: ".submit-order-btn",
        payment_component: ".pos-payment",
        customer_section: ".customer-section",
        page_container: ".point-of-sale-app"
    };

    // 1. Embedded mode: hide desk navbar/sidebar when inside iframe
    if (window.self !== window.top) {
        document.addEventListener("DOMContentLoaded", apply_embedded_mode);
        apply_embedded_mode();
    }

    function apply_embedded_mode() {
        document.body.classList.add("hotel-embedded");
        if (!document.getElementById("hotel-pos-embedded-style")) {
            const style = document.createElement("style");
            style.id = "hotel-pos-embedded-style";
            style.innerHTML = `
                body.hotel-embedded .navbar,
                body.hotel-embedded .page-head,
                body.hotel-embedded .layout-side-section {
                    display: none !important;
                }
                body.hotel-embedded .main-section {
                    padding: 0 !important;
                    margin: 0 !important;
                }
                body.hotel-embedded .page-container {
                    padding: 0 !important;
                    margin: 0 !important;
                }
                .hotel-charge-to-room-btn {
                    background-color: #f39c12 !important;
                    color: #ffffff !important;
                    font-weight: 700 !important;
                    margin-top: 8px;
                    text-align: center;
                    padding: 10px;
                    border-radius: 6px;
                    cursor: pointer;
                    user-select: none;
                    transition: background-color 0.2s;
                }
                .hotel-charge-to-room-btn:hover {
                    background-color: #d68910 !important;
                }
                .hotel-in-house-picker {
                    margin-bottom: 8px;
                }
                .hotel-in-house-select {
                    width: 100%;
                    padding: 6px 10px;
                    border: 1px solid #d1d8dd;
                    border-radius: 4px;
                    font-size: 13px;
                    background-color: #fbfcfd;
                }
            `;
            document.head.appendChild(style);
        }
    }

    // 2. Poll / Observe DOM to attach components safely
    let is_hooking = false;

    function init_pos_hooks() {
        if (!cur_pos) return;

        // Fetch Hotel Settings
        frappe.call({
            method: "frappe.client.get_single_value",
            args: {
                doctype: "Hotel Settings",
                field: "room_pos_profile"
            },
            callback: function (r) {
                const room_profile = r.message;
                setup_observers(room_profile);
            }
        });
    }

    function setup_observers(room_profile) {
        setInterval(() => {
            if (!cur_pos) return;

            const active_profile = cur_pos.pos_profile;
            const is_room_profile = room_profile && active_profile === room_profile;

            // In-house guest picker in cart
            attach_guest_picker(is_room_profile);

            // Charge to Room button in payment screen
            if (is_room_profile) {
                attach_charge_to_room_button();
            } else {
                $(".hotel-charge-to-room-btn").remove();
            }
        }, 800);
    }

    function attach_guest_picker(is_room_profile) {
        if (!is_room_profile) {
            $(".hotel-in-house-picker").remove();
            return;
        }

        const $customer_sec = $(SELECTORS.customer_section);
        if ($customer_sec.length && !$customer_sec.find(".hotel-in-house-picker").length) {
            const $picker = $(`
                <div class="hotel-in-house-picker">
                    <label class="control-label small text-muted">${__("In-House Guest (Room)")}</label>
                    <select class="hotel-in-house-select form-control">
                        <option value="">${__("-- Select In-House Guest --")}</option>
                    </select>
                </div>
            `);

            $customer_sec.prepend($picker);

            frappe.call({
                method: "hospitality_core.pos.get_in_house_guests",
                callback: function (res) {
                    const guests = res.message || [];
                    const $select = $picker.find("select");
                    guests.forEach(g => {
                        $select.append(`<option value="${g.customer}" data-room="${g.room}" data-res="${g.reservation}">Room ${g.room} · ${g.guest_name}</option>`);
                    });

                    $select.on("change", function () {
                        const val = $(this).val();
                        if (val && cur_pos && cur_pos.cart) {
                            cur_pos.cart.set_customer(val);
                        }
                    });
                }
            });
        }
    }

    function attach_charge_to_room_button() {
        const $submit_btn = $(SELECTORS.submit_btn);
        if ($submit_btn.length && !$submit_btn.siblings(".hotel-charge-to-room-btn").length) {
            const $btn = $(`<div class="submit-order-btn hotel-charge-to-room-btn">${__("Charge to Room")}</div>`);
            $submit_btn.after($btn);

            $btn.on("click", function () {
                handle_charge_to_room();
            });
        }
    }

    function handle_charge_to_room() {
        if (!cur_pos) return;

        const frm = cur_pos.frm;
        if (!frm || !frm.doc) {
            frappe.msgprint(__("No active order found."));
            return;
        }

        if (!frm.doc.customer) {
            frappe.msgprint(__("Please select an In-House Guest first."));
            return;
        }

        if (!frm.doc.items || frm.doc.items.length === 0) {
            frappe.msgprint(__("Cart is empty. Add items before charging to room."));
            return;
        }

        frappe.confirm(
            __("Charge {0} items (Total: {1}) to Room for Guest {2}?", [
                frm.doc.items.length,
                format_currency(frm.doc.grand_total),
                frm.doc.customer
            ]),
            function () {
                // Ensure saved as draft first
                cur_pos.save_and_checkout();
                setTimeout(() => {
                    if (cur_pos.frm && cur_pos.frm.doc && cur_pos.frm.doc.name) {
                        const inv_name = cur_pos.frm.doc.name;
                        frappe.call({
                            method: "hospitality_core.pos.charge_to_room",
                            args: { invoice_name: inv_name },
                            freeze: true,
                            callback: function (r) {
                                if (!r.exc && r.message) {
                                    frappe.show_alert({
                                        message: __("Order {0} successfully charged to Room (Reservation {1}).", [inv_name, r.message.reservation]),
                                        indicator: "orange"
                                    });
                                    // Start a new fresh POS order
                                    if (cur_pos.cart) {
                                        cur_pos.cart.new_order();
                                    }
                                }
                            }
                        });
                    }
                }, 600);
            }
        );
    }

    // Attach when POS page is ready
    $(document).on("page-change", function () {
        if (frappe.get_route()[0] === "point-of-sale") {
            setTimeout(init_pos_hooks, 1000);
        }
    });

    if (frappe.get_route && frappe.get_route()[0] === "point-of-sale") {
        setTimeout(init_pos_hooks, 1000);
    }
})();


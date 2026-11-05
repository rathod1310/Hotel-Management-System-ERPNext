/**
 * Sky Hotel Management System - Front Desk Console v2
 * Single-screen, zero-redirect console with Dialogs and embedded POS overlay.
 */

frappe.pages['front-desk-console'] = frappe.pages['front-desk-console'] || {};
frappe.pages['front-desk-console'].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('Front Desk Console'),
        single_column: true
    });

    window.cur_fd_console = new FrontDeskConsole(wrapper, page);
};
frappe.pages['front_desk_console'] = frappe.pages['front-desk-console'];

class FrontDeskConsole {
    constructor(wrapper, page) {
        this.wrapper = wrapper;
        this.page = page;
        this.current_date = frappe.datetime.get_today();
        this.active_tab = "rooms";
        this.state = null;

        this.init_dom();
        this.init_keyboard_shortcuts();
        this.init_realtime();
        this.load_data();
    }

    init_dom() {
        this.$container = $(`
            <div class="fd-console-container">
                <!-- Top Bar -->
                <div class="fd-top-bar">
                    <div class="fd-brand-section">
                        <span class="fd-brand-title">${__("Sky Hotel")}</span>
                        <div class="fd-date-controls">
                            <button class="btn btn-default btn-xs fd-prev-day"><i class="fa fa-chevron-left"></i></button>
                            <span class="fd-display-date font-weight-bold mx-2"></span>
                            <button class="btn btn-default btn-xs fd-next-day"><i class="fa fa-chevron-right"></i></button>
                            <button class="btn btn-default btn-xs fd-today-btn ml-1">${__("Today")}</button>
                        </div>
                    </div>
                    <div class="fd-search-box">
                        <input type="text" class="form-control input-sm fd-global-search" placeholder="${__("Search guest, room, reservation... (/ to focus)")}">
                        <div class="fd-search-results" style="display:none;"></div>
                    </div>
                    <div class="fd-actions-group">
                        <button class="btn btn-primary btn-sm fd-btn-new-res"><i class="fa fa-plus"></i> ${__("Reservation")}</button>
                        <button class="btn btn-success btn-sm fd-btn-walkin"><i class="fa fa-sign-in"></i> ${__("Walk-in")}</button>
                        <button class="btn btn-default btn-sm fd-btn-rest-pos"><i class="fa fa-cutlery"></i> ${__("Restaurant POS")}</button>
                        <button class="btn btn-default btn-sm fd-btn-room-pos"><i class="fa fa-bell"></i> ${__("Room Service POS")}</button>
                        <button class="btn btn-default btn-sm fd-btn-refresh"><i class="fa fa-refresh"></i></button>
                    </div>
                </div>

                <!-- KPI Strip -->
                <div class="fd-kpi-strip"></div>

                <!-- Navigation Tabs -->
                <div class="fd-nav-tabs">
                    <button class="fd-tab-btn active" data-tab="rooms">${__("Rooms")}</button>
                    <button class="fd-tab-btn" data-tab="arrivals">${__("Arrivals")}</button>
                    <button class="fd-tab-btn" data-tab="in_house">${__("In-House")}</button>
                    <button class="fd-tab-btn" data-tab="departures">${__("Departures")}</button>
                    <button class="fd-tab-btn" data-tab="dirty">${__("Housekeeping")}</button>
                    <button class="fd-tab-btn" data-tab="maintenance">${__("Maintenance")}</button>
                    <button class="fd-tab-btn" data-tab="tape_chart">${__("Tape Chart")}</button>
                    <button class="fd-tab-btn" data-tab="availability">${__("Availability")}</button>
                </div>

                <!-- Main Content Area -->
                <div class="fd-tab-content">
                    <div class="text-muted p-4 text-center">${__("Loading Console...")}</div>
                </div>
            </div>
        `).appendTo(this.wrapper.find('.layout-main-section'));

        this.bind_events();
    }

    bind_events() {
        const me = this;

        // Date Controls
        this.$container.find(".fd-prev-day").on("click", () => me.change_date(-1));
        this.$container.find(".fd-next-day").on("click", () => me.change_date(1));
        this.$container.find(".fd-today-btn").on("click", () => {
            me.current_date = frappe.datetime.get_today();
            me.load_data();
        });

        // Refresh
        this.$container.find(".fd-btn-refresh").on("click", () => me.load_data());

        // Tabs
        this.$container.find(".fd-tab-btn").on("click", function () {
            const tab = $(this).attr("data-tab");
            me.switch_tab(tab);
        });

        // Top actions
        this.$container.find(".fd-btn-new-res").on("click", () => me.dialog_new_reservation());
        this.$container.find(".fd-btn-walkin").on("click", () => me.dialog_walkin());
        this.$container.find(".fd-btn-rest-pos").on("click", () => me.open_pos_overlay("restaurant"));
        this.$container.find(".fd-btn-room-pos").on("click", () => me.open_pos_overlay("room"));

        // Global Search
        const $input = this.$container.find(".fd-global-search");
        const $results = this.$container.find(".fd-search-results");

        $input.on("input", frappe.utils.debounce(function () {
            const val = $(this).val();
            if (!val || val.length < 2) {
                $results.hide().empty();
                return;
            }
            frappe.call({
                method: "hospitality_core.api.console.search",
                args: { text: val },
                callback: function (r) {
                    $results.empty();
                    const list = r.message || [];
                    if (list.length === 0) {
                        $results.html(`<div class="p-2 text-muted small">${__("No matches found.")}</div>`).show();
                        return;
                    }
                    list.forEach(item => {
                        $results.append(`
                            <div class="fd-search-item" data-type="${item.type}" data-val="${item.value}">
                                <b>[${item.type}]</b> ${item.label} <small class="text-muted ml-2">${item.details}</small>
                            </div>
                        `);
                    });
                    $results.show();
                }
            });
        }, 300));

        $results.on("click", ".fd-search-item", function () {
            const type = $(this).attr("data-type");
            const val = $(this).attr("data-val");
            $results.hide();
            if (type === "Room") {
                const room = me.state.rooms.find(r => r.name === val);
                if (room) me.show_room_dialog(room);
            } else if (type === "Reservation") {
                me.dialog_view_reservation(val);
            }
        });

        $(document).on("click", (e) => {
            if (!$(e.target).closest(".fd-search-box").length) {
                $results.hide();
            }
        });
    }

    init_keyboard_shortcuts() {
        const me = this;
        $(document).on("keydown", function (e) {
            // Ignore when typing inside input / textarea
            if ($(e.target).is("input, textarea, select")) return;

            if (e.key === "n" || e.key === "N") {
                e.preventDefault();
                me.dialog_new_reservation();
            } else if (e.key === "w" || e.key === "W") {
                e.preventDefault();
                me.dialog_walkin();
            } else if (e.key === "r" || e.key === "R") {
                e.preventDefault();
                me.load_data();
            } else if (e.key === "/") {
                e.preventDefault();
                me.$container.find(".fd-global-search").focus();
            }
        });
    }

    init_realtime() {
        const me = this;
        frappe.realtime.on("hotel_console_update", function (data) {
            me.load_data(true);
        });
    }

    change_date(delta) {
        this.current_date = frappe.datetime.add_days(this.current_date, delta);
        this.load_data();
    }

    load_data(silent = false) {
        const me = this;
        if (!silent) {
            this.$container.find(".fd-btn-refresh i").addClass("fa-spin");
        }
        frappe.call({
            method: "hospitality_core.api.console.get_console_data",
            args: { target_date: me.current_date },
            callback: function (r) {
                me.$container.find(".fd-btn-refresh i").removeClass("fa-spin");
                if (r.message) {
                    me.state = r.message;
                    me.render();
                }
            }
        });
    }

    render() {
        // Display date
        this.$container.find(".fd-display-date").text(frappe.datetime.str_to_user(this.current_date));

        this.render_kpis();
        this.render_tab_content();
    }

    render_kpis() {
        const k = this.state.kpis;
        const html = `
            <div class="fd-kpi-card" data-tab="arrivals">
                <div class="fd-kpi-num text-primary">${k.arrivals}</div>
                <div class="fd-kpi-label">${__("Arrivals")}</div>
            </div>
            <div class="fd-kpi-card" data-tab="in_house">
                <div class="fd-kpi-num text-success">${k.in_house}</div>
                <div class="fd-kpi-label">${__("In-House")}</div>
            </div>
            <div class="fd-kpi-card" data-tab="departures">
                <div class="fd-kpi-num text-warning">${k.departures}</div>
                <div class="fd-kpi-label">${__("Departures")}</div>
            </div>
            <div class="fd-kpi-card" data-tab="rooms">
                <div class="fd-kpi-num text-success">${k.available}</div>
                <div class="fd-kpi-label">${__("Available")}</div>
            </div>
            <div class="fd-kpi-card" data-tab="dirty">
                <div class="fd-kpi-num text-warning">${k.dirty}</div>
                <div class="fd-kpi-label">${__("Dirty")}</div>
            </div>
            <div class="fd-kpi-card" data-tab="maintenance">
                <div class="fd-kpi-num text-danger">${k.ooo}</div>
                <div class="fd-kpi-label">${__("Out of Order")}</div>
            </div>
            <div class="fd-kpi-card" data-tab="rooms">
                <div class="fd-kpi-num text-info">${k.occupancy_pct}%</div>
                <div class="fd-kpi-label">${__("Occupancy")}</div>
            </div>
        `;
        this.$container.find(".fd-kpi-strip").html(html);

        const me = this;
        this.$container.find(".fd-kpi-card").on("click", function () {
            const target_tab = $(this).attr("data-tab");
            me.switch_tab(target_tab);
        });
    }

    switch_tab(tab_name) {
        this.active_tab = tab_name;
        this.$container.find(".fd-tab-btn").removeClass("active");
        this.$container.find(`.fd-tab-btn[data-tab="${tab_name}"]`).addClass("active");
        this.render_tab_content();
    }

    render_tab_content() {
        const $tab = this.$container.find(".fd-tab-content");
        $tab.empty();

        if (this.active_tab === "rooms") {
            this.render_rooms_tab($tab);
        } else if (this.active_tab === "arrivals") {
            this.render_table_tab($tab, this.state.arrivals, __("Expected Arrivals"), "arrivals");
        } else if (this.active_tab === "in_house") {
            this.render_table_tab($tab, this.state.in_house, __("Currently In-House Guests"), "in_house");
        } else if (this.active_tab === "departures") {
            this.render_table_tab($tab, this.state.departures, __("Expected Departures"), "departures");
        } else if (this.active_tab === "dirty") {
            this.render_housekeeping_tab($tab);
        } else if (this.active_tab === "maintenance") {
            this.render_maintenance_tab($tab);
        } else if (this.active_tab === "tape_chart") {
            this.render_tape_chart_tab($tab);
        } else if (this.active_tab === "availability") {
            this.render_availability_tab($tab);
        }
    }

    render_rooms_tab($tab) {
        const rooms = this.state.rooms || [];
        if (!rooms.length) {
            $tab.html(`<div class="p-4 text-muted text-center">${__("No hotel rooms configured.")}</div>`);
            return;
        }

        // Group by floor
        const floors = {};
        rooms.forEach(r => {
            const fl = r.floor || "1";
            if (!floors[fl]) floors[fl] = [];
            floors[fl].push(r);
        });

        let html = "";
        Object.keys(floors).sort().forEach(fl => {
            html += `
                <div class="fd-floor-section">
                    <div class="fd-floor-title">${__("Floor")} ${fl}</div>
                    <div class="fd-room-grid">
            `;
            floors[fl].forEach(room => {
                let status_class = "status-available";
                if (room.status === "Occupied") status_class = "status-occupied";
                else if (room.status === "Reserved") status_class = "status-reserved";
                else if (room.status === "Dirty") status_class = "status-dirty";
                else if (room.status === "Out of Order") status_class = "status-ooo";

                let chips = "";
                if (room.balance > 0) {
                    chips += `<span class="fd-chip fd-chip-balance">${format_currency(room.balance)}</span>`;
                }
                if (room.room_service_pending > 0) {
                    chips += `<span class="fd-chip fd-chip-rs">${__("RS")}: ${format_currency(room.room_service_pending)}</span>`;
                }

                html += `
                    <div class="fd-room-card ${status_class}" data-room="${room.name}">
                        <div class="fd-room-header">
                            <span class="fd-room-number">${room.room_number || room.name}</span>
                            <span class="fd-room-type">${room.room_type}</span>
                        </div>
                        <div class="fd-guest-name">${room.guest_name || __(room.status)}</div>
                        <div class="fd-chips-row">${chips}</div>
                    </div>
                `;
            });
            html += `</div></div>`;
        });

        $tab.html(html);

        const me = this;
        $tab.find(".fd-room-card").on("click", function () {
            const rname = $(this).attr("data-room");
            const room = me.state.rooms.find(r => r.name === rname);
            if (room) me.show_room_dialog(room);
        });
    }

    render_table_tab($tab, list, title, type) {
        if (!list || !list.length) {
            $tab.html(`<div class="p-4 text-muted text-center">${__("No records for {0} on {1}", [title, frappe.datetime.str_to_user(this.current_date)])}</div>`);
            return;
        }

        let rows = "";
        list.forEach(item => {
            let action_btn = "";
            if (type === "arrivals") {
                action_btn = `<button class="btn btn-primary btn-xs fd-row-checkin" data-res="${item.name}">${__("Check In")}</button>`;
            } else if (type === "departures" || type === "in_house") {
                action_btn = `
                    <button class="btn btn-default btn-xs fd-row-bill" data-res="${item.name}">${__("Bill")}</button>
                    <button class="btn btn-primary btn-xs fd-row-checkout" data-res="${item.name}">${__("Check Out")}</button>
                `;
            }

            rows += `
                <tr>
                    <td><b>${item.name}</b></td>
                    <td>${item.guest_name || item.customer}</td>
                    <td>${item.room || "-"}</td>
                    <td>${item.room_type}</td>
                    <td>${frappe.datetime.str_to_user(item.check_in_date)}</td>
                    <td>${frappe.datetime.str_to_user(item.check_out_date)}</td>
                    <td>${format_currency(item.balance || 0)}</td>
                    <td>${action_btn}</td>
                </tr>
            `;
        });

        $tab.html(`
            <h4>${title}</h4>
            <table class="table table-bordered table-hover">
                <thead style="background:#f7fafc;">
                    <tr>
                        <th>${__("Reservation")}</th>
                        <th>${__("Guest")}</th>
                        <th>${__("Room")}</th>
                        <th>${__("Type")}</th>
                        <th>${__("Arrival")}</th>
                        <th>${__("Departure")}</th>
                        <th>${__("Balance")}</th>
                        <th>${__("Actions")}</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        `);

        const me = this;
        $tab.find(".fd-row-checkin").on("click", function () {
            const res = $(this).attr("data-res");
            me.dialog_checkin(res);
        });
        $tab.find(".fd-row-bill").on("click", function () {
            const res = $(this).attr("data-res");
            me.dialog_bill_preview(res);
        });
        $tab.find(".fd-row-checkout").on("click", function () {
            const res = $(this).attr("data-res");
            me.dialog_checkout(res);
        });
    }

    render_housekeeping_tab($tab) {
        const dirty = this.state.dirty || [];
        if (!dirty.length) {
            $tab.html(`<div class="p-4 text-success text-center font-weight-bold"><i class="fa fa-check-circle"></i> ${__("All rooms are clean and ready!")}</div>`);
            return;
        }

        let cards = "";
        dirty.forEach(r => {
            cards += `
                <div class="fd-room-card status-dirty" style="cursor:default;">
                    <div class="fd-room-header">
                        <span class="fd-room-number">${r.room_number || r.name}</span>
                        <span class="fd-room-type">${r.room_type}</span>
                    </div>
                    <div class="text-muted small my-2">${__("Floor")} ${r.floor || "1"}</div>
                    <button class="btn btn-success btn-sm btn-block fd-btn-clean" data-room="${r.name}">${__("Mark Clean")}</button>
                </div>
            `;
        });

        $tab.html(`
            <h4>${__("Housekeeping / Dirty Rooms ({0})", [dirty.length])}</h4>
            <div class="fd-room-grid">${cards}</div>
        `);

        const me = this;
        $tab.find(".fd-btn-clean").on("click", function () {
            const room = $(this).attr("data-room");
            frappe.call({
                method: "hospitality_core.api.console.set_housekeeping",
                args: { room_number: room, action: "Clean" },
                freeze: true,
                callback: function (r) {
                    if (!r.exc) {
                        frappe.show_alert({ message: __("Room {0} marked Clean.", [room]), indicator: "green" });
                        me.load_data();
                    }
                }
            });
        });
    }

    render_maintenance_tab($tab) {
        const maint = this.state.maintenance || [];
        let rows = "";
        maint.forEach(i => {
            rows += `
                <tr>
                    <td><b>${i.name}</b></td>
                    <td>Room ${i.hotel_room}</td>
                    <td>${i.subject}</td>
                    <td><span class="badge badge-warning">${i.status}</span></td>
                    <td>${i.priority}</td>
                    <td>
                        <button class="btn btn-success btn-xs fd-resolve-issue" data-issue="${i.name}">${__("Resolve")}</button>
                    </td>
                </tr>
            `;
        });

        $tab.html(`
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h4>${__("Maintenance Issues ({0})", [maint.length])}</h4>
                <button class="btn btn-danger btn-sm fd-report-new-issue"><i class="fa fa-wrench"></i> ${__("Report Issue")}</button>
            </div>
            <table class="table table-bordered">
                <thead style="background:#f7fafc;">
                    <tr>
                        <th>${__("Issue")}</th>
                        <th>${__("Room")}</th>
                        <th>${__("Subject")}</th>
                        <th>${__("Status")}</th>
                        <th>${__("Priority")}</th>
                        <th>${__("Action")}</th>
                    </tr>
                </thead>
                <tbody>${rows || `<tr><td colspan="6" class="text-muted text-center">${__("No open maintenance issues.")}</td></tr>`}</tbody>
            </table>
        `);

        const me = this;
        $tab.find(".fd-report-new-issue").on("click", () => me.dialog_report_issue());
        $tab.find(".fd-resolve-issue").on("click", function () {
            const issue_name = $(this).attr("data-issue");
            me.dialog_resolve_issue(issue_name);
        });
    }

    render_tape_chart_tab($tab) {
        $tab.html(`
            <h4>${__("Tape Chart / Booking Matrix")}</h4>
            <div id="fd-tapechart-container" style="min-height:350px;">
                <div class="text-muted p-4 text-center">${__("Loading Tape Chart...")}</div>
            </div>
        `);
        const start = frappe.datetime.add_days(this.current_date, -1);
        const end = frappe.datetime.add_days(this.current_date, 14);

        frappe.call({
            method: "hospitality_core.hospitality_core.page.tape_chart.tape_chart.get_chart_data",
            args: { start_date: start, end_date: end },
            callback: function (r) {
                if (r.message) {
                    const rooms = r.message.rooms || [];
                    const bookings = r.message.bookings || [];
                    let html = `<table class="table table-bordered table-sm small"><thead><tr style="background:#edf2f7;"><th>Room</th>`;

                    let d = start;
                    const date_headers = [];
                    while (d <= end) {
                        date_headers.push(d);
                        html += `<th>${frappe.datetime.str_to_user(d).substring(0, 5)}</th>`;
                        d = frappe.datetime.add_days(d, 1);
                    }
                    html += `</tr></thead><tbody>`;

                    rooms.forEach(rm => {
                        html += `<tr><td><b>${rm.room_number || rm.name}</b> (${rm.room_type})</td>`;
                        date_headers.forEach(cur_d => {
                            const bk = bookings.find(b => b.room === rm.name && cur_d >= b.arrival_date && cur_d < b.departure_date);
                            if (bk) {
                                html += `<td style="background:#fed7d7; text-align:center;"><small>${bk.guest || bk.name}</small></td>`;
                            } else {
                                html += `<td style="background:#c6f6d5; text-align:center;">-</td>`;
                            }
                        });
                        html += `</tr>`;
                    });
                    html += `</tbody></table>`;
                    $tab.find("#fd-tapechart-container").html(html);
                }
            }
        });
    }

    render_availability_tab($tab) {
        $tab.html(`
            <h4>${__("Room Availability Tool")}</h4>
            <div id="fd-avail-container" style="min-height:350px;"></div>
        `);
        const start = this.current_date;
        const end = frappe.datetime.add_days(this.current_date, 1);

        frappe.call({
            method: "hospitality_core.hospitality_core.page.availability_tool.availability_tool.check_availability_counts",
            args: { start_date: start, end_date: end },
            callback: function (r) {
                if (r.message) {
                    const summary = r.message.summary || [];
                    let s_html = `<table class="table table-bordered mb-4"><thead style="background:#f7fafc;"><tr><th>${__("Room Type")}</th><th>${__("Total")}</th><th>${__("Unavailable")}</th><th>${__("Available")}</th></tr></thead><tbody>`;
                    summary.forEach(s => {
                        s_html += `<tr><td><b>${s.room_type}</b></td><td>${s.total}</td><td>${s.occupied}</td><td style="color:green; font-weight:bold;">${s.available}</td></tr>`;
                    });
                    s_html += `</tbody></table>`;
                    $tab.find("#fd-avail-container").html(s_html);
                }
            }
        });
    }

    // ==========================================
    // DIALOGS CATALOGUE (Zero Redirects)
    // ==========================================

    show_room_dialog(room) {
        const me = this;
        const d = new frappe.ui.Dialog({
            title: __("Room {0} ({1})", [room.room_number || room.name, room.room_type]),
            fields: [
                { fieldtype: "HTML", fieldname: "info_html" }
            ]
        });

        let info = `
            <div class="mb-3">
                <span class="badge badge-info p-2">${__(room.status)}</span>
                <span class="ml-2 font-weight-bold">${room.guest_name ? `Guest: ${room.guest_name}` : ""}</span>
            </div>
        `;
        if (room.current_reservation) {
            info += `<div class="small text-muted mb-2">${__("Reservation")}: ${room.current_reservation}</div>`;
        }
        d.fields_dict.info_html.$wrapper.html(info);

        if (room.status === "Available") {
            d.set_primary_action(__("Walk-in"), function () {
                d.hide();
                me.dialog_walkin(room.name, room.room_type);
            });
            d.add_custom_button(__("New Reservation"), function () {
                d.hide();
                me.dialog_new_reservation(room.name, room.room_type);
            });
            d.add_custom_button(__("Mark Dirty"), function () {
                d.hide();
                me.set_room_housekeeping(room.name, "Dirty");
            });
            d.add_custom_button(__("Send to Maintenance"), function () {
                d.hide();
                me.dialog_report_issue(room.name);
            });
        } else if (room.status === "Occupied") {
            d.set_primary_action(__("View Bill / Check Out"), function () {
                d.hide();
                me.dialog_bill_preview(room.current_reservation);
            });
            d.add_custom_button(__("Room Service POS"), function () {
                d.hide();
                me.open_pos_overlay("room", room.customer);
            });
            d.add_custom_button(__("Receive Payment"), function () {
                d.hide();
                me.dialog_receive_payment(room.current_reservation);
            });
            d.add_custom_button(__("Move Room"), function () {
                d.hide();
                me.dialog_move_room(room.current_reservation);
            });
            d.add_custom_button(__("Extend Stay"), function () {
                d.hide();
                me.dialog_extend_stay(room.current_reservation);
            });
            d.add_custom_button(__("Report Issue"), function () {
                d.hide();
                me.dialog_report_issue(room.name);
            });
        } else if (room.status === "Dirty") {
            d.set_primary_action(__("Mark Clean"), function () {
                d.hide();
                me.set_room_housekeeping(room.name, "Clean");
            });
        } else if (room.status === "Out of Order") {
            d.set_primary_action(__("Resolve Issue"), function () {
                d.hide();
                me.switch_tab("maintenance");
            });
        } else if (room.status === "Reserved") {
            d.set_primary_action(__("Check In"), function () {
                d.hide();
                me.dialog_checkin(room.current_reservation);
            });
        }

        d.show();
    }

    dialog_new_reservation(pre_room = null, pre_type = null) {
        const me = this;
        const d = new frappe.ui.Dialog({
            title: __("New Reservation"),
            fields: [
                { fieldtype: "Link", fieldname: "customer", label: __("Guest (Customer)"), options: "Customer" },
                { fieldtype: "Data", fieldname: "guest_name", label: __("Or New Guest Name") },
                { fieldtype: "Data", fieldname: "guest_id_number", label: __("Guest ID / Passport") },
                { fieldtype: "Section Break" },
                { fieldtype: "Link", fieldname: "room_type", label: __("Room Type"), options: "Hotel Room Type", reqd: 1, default: pre_type },
                { fieldtype: "Date", fieldname: "check_in_date", label: __("Check In Date"), reqd: 1, default: me.current_date },
                { fieldtype: "Date", fieldname: "check_out_date", label: __("Check Out Date"), reqd: 1, default: frappe.datetime.add_days(me.current_date, 1) },
                { fieldtype: "Column Break" },
                { fieldtype: "Link", fieldname: "room", label: __("Room"), options: "Hotel Room", default: pre_room },
                { fieldtype: "Int", fieldname: "adults", label: __("Adults"), default: 1 },
                { fieldtype: "Section Break", label: __("Optional Advance Payment") },
                { fieldtype: "Currency", fieldname: "advance_amount", label: __("Advance Amount") },
                { fieldtype: "Link", fieldname: "advance_mode", label: __("Mode of Payment"), options: "Mode of Payment", default: me.state.settings.default_advance_mode }
            ],
            primary_action_label: __("Save Reservation"),
            primary_action: function (values) {
                const advance = values.advance_amount ? { amount: values.advance_amount, mode: values.advance_mode } : null;
                frappe.call({
                    method: "hospitality_core.api.console.create_reservation",
                    args: { data: values, advance: advance },
                    freeze: true,
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.show_alert({ message: __("Reservation created."), indicator: "green" });
                            d.hide();
                            me.load_data();
                        }
                    }
                });
            }
        });
        d.show();
    }

    dialog_walkin(pre_room = null, pre_type = null) {
        const me = this;
        const d = new frappe.ui.Dialog({
            title: __("Walk-in Check-in"),
            fields: [
                { fieldtype: "Link", fieldname: "customer", label: __("Guest (Customer)"), options: "Customer" },
                { fieldtype: "Data", fieldname: "guest_name", label: __("Or New Guest Name"), reqd: 1 },
                { fieldtype: "Data", fieldname: "guest_id_number", label: __("Guest ID / Passport") },
                { fieldtype: "Section Break" },
                { fieldtype: "Link", fieldname: "room_type", label: __("Room Type"), options: "Hotel Room Type", reqd: 1, default: pre_type },
                { fieldtype: "Date", fieldname: "check_out_date", label: __("Check Out Date"), reqd: 1, default: frappe.datetime.add_days(frappe.datetime.get_today(), 1) },
                { fieldtype: "Link", fieldname: "room", label: __("Room"), options: "Hotel Room", reqd: 1, default: pre_room },
                { fieldtype: "Section Break", label: __("Optional Advance Payment") },
                { fieldtype: "Currency", fieldname: "advance_amount", label: __("Advance Amount") },
                { fieldtype: "Link", fieldname: "advance_mode", label: __("Mode of Payment"), options: "Mode of Payment", default: me.state.settings.default_advance_mode }
            ],
            primary_action_label: __("Check In Now"),
            primary_action: function (values) {
                const advance = values.advance_amount ? { amount: values.advance_amount, mode: values.advance_mode } : null;
                frappe.call({
                    method: "hospitality_core.api.console.walk_in",
                    args: { data: values, advance: advance },
                    freeze: true,
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.show_alert({ message: __("Guest successfully checked in!"), indicator: "green" });
                            d.hide();
                            me.load_data();
                        }
                    }
                });
            }
        });
        d.show();
    }

    dialog_checkin(reservation_name) {
        const me = this;
        frappe.call({
            method: "hospitality_core.api.console.check_in",
            args: { reservation_name: reservation_name },
            freeze: true,
            callback: function (r) {
                if (!r.exc) {
                    frappe.show_alert({ message: __("Guest Checked In."), indicator: "green" });
                    me.load_data();
                }
            }
        });
    }

    dialog_bill_preview(reservation_name) {
        const me = this;
        frappe.call({
            method: "hospitality_core.api.console.get_bill_preview",
            args: { reservation_name: reservation_name },
            freeze: true,
            callback: function (r) {
                if (!r.message) return;
                const bill = r.message;
                let rows = "";
                bill.items.forEach(it => {
                    rows += `<tr><td>${it.item_name || it.item_code}</td><td><small class="badge badge-light">${it.source}</small></td><td>${it.qty}</td><td>${format_currency(it.rate)}</td><td>${format_currency(it.amount)}</td></tr>`;
                });

                const d = new frappe.ui.Dialog({
                    title: __("Folio Bill Preview ({0})", [reservation_name]),
                    fields: [
                        { fieldtype: "HTML", fieldname: "bill_html" }
                    ]
                });

                const html = `
                    <table class="table table-bordered table-sm mb-3">
                        <thead style="background:#f7fafc;">
                            <tr><th>Item</th><th>Source</th><th>Qty</th><th>Rate</th><th>Total</th></tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                    <div class="row">
                        <div class="col-sm-6">
                            <div><b>${__("Grand Total")}:</b> ${format_currency(bill.grand_total)}</div>
                            <div><b>${__("Total Paid")}:</b> ${format_currency(bill.total_paid)}</div>
                            <div class="h5 mt-2 ${bill.balance > 0 ? "text-danger" : "text-success"}"><b>${__("Outstanding Balance")}:</b> ${format_currency(bill.balance)}</div>
                        </div>
                    </div>
                `;
                d.fields_dict.bill_html.$wrapper.html(html);

                if (bill.balance > 0) {
                    d.add_custom_button(__("Receive Payment"), function () {
                        d.hide();
                        me.dialog_receive_payment(reservation_name, bill.balance);
                    });
                }
                d.set_primary_action(__("Check Out Guest"), function () {
                    d.hide();
                    me.dialog_checkout(reservation_name, bill.balance);
                });

                d.show();
            }
        });
    }

    dialog_receive_payment(reservation_name, default_amount = 0) {
        const me = this;
        const d = new frappe.ui.Dialog({
            title: __("Receive Payment ({0})", [reservation_name]),
            fields: [
                { fieldtype: "Currency", fieldname: "amount", label: __("Amount"), reqd: 1, default: default_amount },
                { fieldtype: "Link", fieldname: "mode", label: __("Mode of Payment"), options: "Mode of Payment", reqd: 1, default: me.state.settings.default_advance_mode },
                { fieldtype: "Data", fieldname: "reference", label: __("Reference / Transaction ID") }
            ],
            primary_action_label: __("Record Payment"),
            primary_action: function (values) {
                frappe.call({
                    method: "hospitality_core.api.console.receive_payment",
                    args: {
                        reservation_name: reservation_name,
                        mode: values.mode,
                        amount: values.amount,
                        reference: values.reference
                    },
                    freeze: true,
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.show_alert({ message: __("Payment recorded successfully."), indicator: "green" });
                            d.hide();
                            me.load_data();
                        }
                    }
                });
            }
        });
        d.show();
    }

    dialog_checkout(reservation_name, balance = 0) {
        const me = this;
        if (balance > 0) {
            // Settle balance first
            frappe.confirm(
                __("Guest has an outstanding balance of {0}. Settle payment now before checkout?", [format_currency(balance)]),
                function () {
                    me.dialog_receive_payment(reservation_name, balance);
                }
            );
            return;
        }

        frappe.confirm(
            __("Are you sure you want to check out reservation {0}? This will finalize the Sales Invoice and release the room.", [reservation_name]),
            function () {
                frappe.call({
                    method: "hospitality_core.api.console.check_out",
                    args: { reservation_name: reservation_name },
                    freeze: true,
                    callback: function (r) {
                        if (!r.exc && r.message) {
                            frappe.msgprint({
                                title: __("Check-Out Completed"),
                                indicator: "green",
                                message: __("Sales Invoice <b>{0}</b> generated.<br><br><a href='{1}' target='_blank' class='btn btn-primary btn-sm'>Print Invoice PDF</a>", [r.message.sales_invoice, r.message.print_url])
                            });
                            me.load_data();
                        }
                    }
                });
            }
        );
    }

    dialog_move_room(reservation_name) {
        const me = this;
        const d = new frappe.ui.Dialog({
            title: __("Move Room ({0})", [reservation_name]),
            fields: [
                { fieldtype: "Link", fieldname: "new_room", label: __("New Room (Available Only)"), options: "Hotel Room", reqd: 1 },
                { fieldtype: "Data", fieldname: "reason", label: __("Reason for Move") },
                { fieldtype: "Check", fieldname: "keep_rate", label: __("Keep Current Rate"), default: 1 }
            ],
            primary_action_label: __("Execute Move"),
            primary_action: function (values) {
                frappe.call({
                    method: "hospitality_core.api.console.move_room",
                    args: {
                        reservation_name: reservation_name,
                        new_room: values.new_room,
                        reason: values.reason,
                        keep_rate: values.keep_rate ? 1 : 0
                    },
                    freeze: true,
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.show_alert({ message: __("Guest moved to new room."), indicator: "green" });
                            d.hide();
                            me.load_data();
                        }
                    }
                });
            }
        });
        d.show();
    }

    dialog_extend_stay(reservation_name) {
        const me = this;
        const d = new frappe.ui.Dialog({
            title: __("Extend Stay ({0})", [reservation_name]),
            fields: [
                { fieldtype: "Date", fieldname: "new_check_out_date", label: __("New Check Out Date"), reqd: 1 }
            ],
            primary_action_label: __("Update Dates"),
            primary_action: function (values) {
                frappe.call({
                    method: "hospitality_core.api.console.extend_stay",
                    args: {
                        reservation_name: reservation_name,
                        new_check_out_date: values.new_check_out_date
                    },
                    freeze: true,
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.show_alert({ message: __("Stay dates extended."), indicator: "green" });
                            d.hide();
                            me.load_data();
                        }
                    }
                });
            }
        });
        d.show();
    }

    dialog_report_issue(pre_room = null) {
        const me = this;
        const d = new frappe.ui.Dialog({
            title: __("Report Maintenance Issue"),
            fields: [
                { fieldtype: "Link", fieldname: "room", label: __("Hotel Room"), options: "Hotel Room", reqd: 1, default: pre_room },
                { fieldtype: "Data", fieldname: "subject", label: __("Subject / Problem"), reqd: 1 },
                { fieldtype: "Select", fieldname: "priority", label: __("Priority"), options: "Low\nMedium\nHigh\nUrgent", default: "Medium" },
                { fieldtype: "Small Text", fieldname: "description", label: __("Detailed Description") }
            ],
            primary_action_label: __("Submit Issue"),
            primary_action: function (values) {
                frappe.call({
                    method: "hospitality_core.api.console.report_issue",
                    args: {
                        room: values.room,
                        subject: values.subject,
                        priority: values.priority,
                        description: values.description
                    },
                    freeze: true,
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.show_alert({ message: __("Issue reported. Room sent to Out of Order."), indicator: "red" });
                            d.hide();
                            me.load_data();
                        }
                    }
                });
            }
        });
        d.show();
    }

    dialog_resolve_issue(issue_name) {
        const me = this;
        const d = new frappe.ui.Dialog({
            title: __("Resolve Issue ({0})", [issue_name]),
            fields: [
                { fieldtype: "Small Text", fieldname: "notes", label: __("Resolution Notes") }
            ],
            primary_action_label: __("Mark Resolved"),
            primary_action: function (values) {
                frappe.call({
                    method: "hospitality_core.api.console.resolve_issue",
                    args: { issue_name: issue_name, notes: values.notes },
                    freeze: true,
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.show_alert({ message: __("Issue resolved."), indicator: "green" });
                            d.hide();
                            me.load_data();
                        }
                    }
                });
            }
        });
        d.show();
    }

    set_room_housekeeping(room, action) {
        const me = this;
        frappe.call({
            method: "hospitality_core.api.console.set_housekeeping",
            args: { room_number: room, action: action },
            freeze: true,
            callback: function (r) {
                if (!r.exc) {
                    frappe.show_alert({ message: __("Room {0} marked {1}.", [room, action]), indicator: action === "Clean" ? "green" : "orange" });
                    me.load_data();
                }
            }
        });
    }

    // ==========================================
    // POS OVERLAY (Single-Screen, Zero Redirect)
    // ==========================================

    open_pos_overlay(type = "room", customer = null) {
        const me = this;
        const profile = type === "restaurant" ? this.state.settings.restaurant_pos_profile : this.state.settings.room_pos_profile;

        if (!profile) {
            frappe.msgprint(__("No {0} POS Profile configured in Hotel Settings.", [type]));
            return;
        }

        // Ensure POS Opening Entry exists
        frappe.call({
            method: "hospitality_core.api.console.ensure_pos_opening",
            args: { pos_profile: profile },
            freeze: true,
            callback: function (r) {
                if (r.exc) return;

                // Frame POS in modal overlay
                const $overlay = $(`
                    <div class="fd-pos-overlay">
                        <div class="fd-pos-header">
                            <div>
                                <span class="font-weight-bold h5 text-white mb-0 mr-3">${type === "restaurant" ? __("Restaurant POS") : __("Room Service POS")}</span>
                                <span class="badge badge-light">${profile}</span>
                            </div>
                            <button class="btn btn-danger btn-sm fd-close-pos"><i class="fa fa-times"></i> ${__("Close POS")}</button>
                        </div>
                        <iframe class="fd-pos-iframe" src="/app/point-of-sale"></iframe>
                    </div>
                `).appendTo("body");

                $overlay.find(".fd-close-pos").on("click", function () {
                    $overlay.remove();
                    me.load_data();
                });
            }
        });
    }
}

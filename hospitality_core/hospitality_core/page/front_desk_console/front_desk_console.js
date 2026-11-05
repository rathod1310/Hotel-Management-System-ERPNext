frappe.pages['front-desk-console'].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('Front Desk Console'),
        single_column: true
    });

    page.add_field({
        fieldname: 'console_date',
        label: __('Date'),
        fieldtype: 'Date',
        default: frappe.datetime.now_date(),
        change: function () {
            render_console(wrapper, page);
        }
    });

    page.set_primary_action(__('Refresh Data'), function () {
        render_console(wrapper, page);
    });

    $(`<style>
        .fd-stat-card {
            background: #fff;
            border: 1px solid #d1d8dd;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            transition: all 0.2s;
            height: 100%;
        }
        .fd-stat-card:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
        .fd-stat-number { font-size: 32px; font-weight: 700; color: #1f272e; margin: 10px 0; }
        .fd-stat-label { font-size: 13px; color: #8d99a6; text-transform: uppercase; letter-spacing: 0.5px; }
        
        .fd-toolbar-btn {
            display: inline-block;
            text-align: center;
            padding: 15px;
            background: #f8f9fa;
            border: 1px solid #ebf1f5;
            border-radius: 6px;
            width: 100%;
            cursor: pointer;
            color: #36414c;
            font-weight: 600;
        }
        .fd-toolbar-btn:hover { background: #e2e6ea; text-decoration: none; color: #1f272e; }

        .fd-list-header { background: #f0f4f7; padding: 10px 15px; font-weight: bold; border-radius: 4px 4px 0 0; border: 1px solid #d1d8dd; border-bottom: none; }
        .fd-list-container { border: 1px solid #d1d8dd; border-radius: 0 0 4px 4px; background: #fff; min-height: 300px; max-height: 500px; overflow-y: auto; }
        .fd-list-item { padding: 12px 15px; border-bottom: 1px solid #f1f1f1; display: flex; align-items: center; justify-content: space-between; }
        .fd-list-item:hover { background: #fafbfc; }
        .fd-list-item:last-child { border-bottom: none; }
        
        .badge-pending { background: #fff5e6; color: #ff9f43; border: 1px solid #ff9f43; padding: 2px 8px; border-radius: 12px; font-size: 11px; }
        .badge-done { background: #e8f5e9; color: #28a745; border: 1px solid #28a745; padding: 2px 8px; border-radius: 12px; font-size: 11px; }
        .badge-missed { background: #ffebee; color: #c62828; border: 1px solid #c62828; padding: 2px 8px; border-radius: 12px; font-size: 11px; }
    </style>`).appendTo(wrapper);

    $(wrapper).find('.layout-main-section').append(`
        <div id="fd-content" style="padding-top: 10px;">
            <!-- Quick Actions Row -->
            <div class="row" style="margin-bottom: 20px;">
                <div class="col-md-2 col-xs-4"><a class="fd-toolbar-btn" onclick="frappe.set_route('tape-chart')">${__("Tape Chart")}</a></div>
                <div class="col-md-2 col-xs-4"><a class="fd-toolbar-btn" onclick="frappe.set_route('availability-tool')">${__("Availability")}</a></div>
                <div class="col-md-2 col-xs-4"><a class="fd-toolbar-btn" onclick="frappe.set_route('housekeeping_view')">${__("Housekeeping")}</a></div>
                <div class="col-md-2 col-xs-4"><a class="fd-toolbar-btn" onclick="frappe.set_route('List', 'Hotel Reservation')">${__("Reservations")}</a></div>
                <div class="col-md-2 col-xs-4"><a class="fd-toolbar-btn" onclick="frappe.set_route('query-report', 'House List')">${__("House List")}</a></div>
                <div class="col-md-2 col-xs-4"><a class="fd-toolbar-btn" onclick="frappe.set_route('List', 'Issue', {'hotel_room': ['!=', '']})">${__("Maintenance")}</a></div>
            </div>

            <!-- Stats Row -->
            <div class="row" style="margin-bottom: 30px;">
                <div class="col-md-3">
                    <div class="fd-stat-card">
                        <div class="fd-stat-label">${__("Arrivals Pending")}</div>
                        <div class="fd-stat-number" id="stat-arr-pending" style="color: #ff9f43">0</div>
                        <small class="text-muted">${__("For selected date")}</small>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="fd-stat-card">
                        <div class="fd-stat-label">${__("Departures Pending")}</div>
                        <div class="fd-stat-number" id="stat-dep-pending" style="color: #ef5350">0</div>
                        <small class="text-muted">${__("For selected date")}</small>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="fd-stat-card">
                        <div class="fd-stat-label">${__("Rooms In-House")}</div>
                        <div class="fd-stat-number" id="stat-occupancy">0</div>
                        <small class="text-muted" id="stat-occ-pct">0% Occupancy</small>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="fd-stat-card">
                        <div class="fd-stat-label">${__("Available Rooms")}</div>
                        <div class="fd-stat-number" id="stat-available" style="color: #28a745">0</div>
                        <small class="text-muted">${__("Net Availability")}</small>
                    </div>
                </div>
            </div>

            <!-- Lists Row -->
            <div class="row">
                <!-- Arrivals Column -->
                <div class="col-md-6">
                    <div class="fd-list-header">
                        <span class="fas fa-plane-arrival" style="color:#5e64ff; margin-right:5px;"></span> ${__("Arrivals")}
                    </div>
                    <div id="list-arrivals" class="fd-list-container">
                        <div class="text-center p-3 text-muted">${__("Loading...")}</div>
                    </div>
                </div>

                <!-- Departures Column -->
                <div class="col-md-6">
                    <div class="fd-list-header">
                        <span class="fas fa-plane-departure" style="color:#ef5350; margin-right:5px;"></span> ${__("Departures")}
                    </div>
                    <div id="list-departures" class="fd-list-container">
                        <div class="text-center p-3 text-muted">${__("Loading...")}</div>
                    </div>
                </div>
            </div>
        </div>
    `);

    render_console(wrapper, page);
};

function render_console(wrapper, page) {
    let selected_date = page.fields_dict.console_date.get_value();

    frappe.call({
        method: "hospitality_core.hospitality_core.page.front_desk_console.front_desk_console.get_console_data",
        args: { target_date: selected_date },
        callback: function (r) {
            if (r.message) {
                update_stats(r.message.stats);
                render_arrivals(r.message.arrivals);
                render_departures(r.message.departures);
            }
        }
    });
}

function update_stats(stats) {
    $('#stat-arr-pending').text(stats.arrivals_pending);
    $('#stat-dep-pending').text(stats.departures_pending);
    $('#stat-occupancy').text(stats.in_house);
    $('#stat-occ-pct').text(stats.occupancy_pct + '% Occupancy');
    $('#stat-available').text(stats.available);
}

function render_arrivals(data) {
    let html = '';
    if (data.length === 0) {
        html = `<div class="text-center p-4 text-muted">${__("No arrivals found for this date.")}</div>`;
    } else {
        data.forEach(d => {
            let is_pending = d.status === 'Reserved';
            let is_arrived = d.status === 'Checked In' || d.status === 'Checked Out';
            let badge = '';

            if (is_arrived) {
                badge = `<span class="badge-done"><i class="fa fa-check"></i> ${__("Arrived")}</span>`;
            } else if (is_pending) {
                let is_past = frappe.datetime.get_diff(frappe.datetime.now_date(), d.arrival_date) > 0;
                if (is_past) badge = `<span class="badge-missed">${__("No Show")}</span>`;
                else badge = `<span class="badge-pending">${__("Pending Check-in")}</span>`;
            }

            html += `
            <div class="fd-list-item">
                <div style="flex:1;">
                    <div style="font-weight:600; font-size:14px;">
                        <a href="#" onclick="frappe.set_route('Form', 'Hotel Reservation', '${d.name}')">${d.guest_name || d.name}</a>
                    </div>
                    <div style="font-size:12px; color:#6c757d;">
                        <span class="fas fa-bed"></span> ${d.room || 'Unassigned'} &middot; ${d.room_type}
                    </div>
                </div>
                <div class="text-right">
                    <div style="margin-bottom:4px;">${badge}</div>
                    ${d.status === 'Reserved' ? `<button class="btn btn-xs btn-primary" onclick="frappe.set_route('Form', 'Hotel Reservation', '${d.name}')">${__("Open")}</button>` : ''}
                </div>
            </div>`;
        });
    }
    $('#list-arrivals').html(html);
}

function render_departures(data) {
    let html = '';
    if (data.length === 0) {
        html = `<div class="text-center p-4 text-muted">${__("No departures found for this date.")}</div>`;
    } else {
        data.forEach(d => {
            let is_left = d.status === 'Checked Out';
            let is_pending = d.status === 'Checked In';
            let badge = '';

            if (is_left) {
                badge = `<span class="badge-done"><i class="fa fa-check"></i> ${__("Checked Out")}</span>`;
            } else if (is_pending) {
                let is_past = frappe.datetime.get_diff(frappe.datetime.now_date(), d.departure_date) > 0;
                if (is_past) badge = `<span class="badge-missed">${__("Overstay")}</span>`;
                else badge = `<span class="badge-pending">${__("Expected Departure")}</span>`;
            }

            html += `
            <div class="fd-list-item">
                <div style="flex:1;">
                    <div style="font-weight:600; font-size:14px;">
                        <a href="#" onclick="frappe.set_route('Form', 'Hotel Reservation', '${d.name}')">${d.guest_name || d.name}</a>
                    </div>
                    <div style="font-size:12px; color:#6c757d;">
                        <span class="fas fa-door-open"></span> ${d.room} &middot; ${d.room_type}
                    </div>
                </div>
                <div class="text-right">
                    <div style="margin-bottom:4px;">${badge}</div>
                    ${d.status === 'Checked In' ? `<button class="btn btn-xs btn-danger" onclick="frappe.set_route('Form', 'Hotel Reservation', '${d.name}')">${__("Checkout")}</button>` : ''}
                </div>
            </div>`;
        });
    }
    $('#list-departures').html(html);
}

frappe.pages['housekeeping_view'].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('Housekeeping View'),
        single_column: true
    });

    page.set_primary_action(__('Refresh'), function () {
        load_rooms(wrapper);
    });

    $(`<style>
        .hk-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 16px;
            padding: 15px 0;
        }
        .hk-card {
            background: #ffffff;
            border-radius: 10px;
            border: 2px solid #28a745;
            padding: 16px 12px;
            text-align: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            min-height: 120px;
            transition: all 0.2s ease;
        }
        .hk-card:hover {
            box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        }
        .hk-card.status-occupied {
            border-color: #212529;
        }
        .hk-card.status-dirty {
            border-color: #ffc107;
        }
        .hk-card.status-ooo {
            border-color: #dc3545;
        }
        .hk-room-num {
            font-size: 18px;
            font-weight: 700;
            color: #1f272e;
            margin-bottom: 4px;
        }
        .hk-room-status {
            font-size: 13px;
            color: #6c757d;
            margin-bottom: 12px;
            font-weight: 500;
        }
        .hk-btn-action {
            width: 100%;
            border-radius: 6px;
            font-weight: 600;
            font-size: 12px;
            padding: 6px 10px;
            border: none;
            cursor: pointer;
            transition: background 0.2s;
        }
        .hk-btn-mark-dirty {
            background-color: #fdb813;
            color: #1f272e;
        }
        .hk-btn-mark-dirty:hover {
            background-color: #e0a310;
        }
        .hk-btn-mark-clean {
            background-color: #28a745;
            color: #ffffff;
        }
        .hk-btn-mark-clean:hover {
            background-color: #218838;
        }
        .hk-btn-disabled {
            background-color: #e9ecef;
            color: #adb5bd;
            cursor: not-allowed;
        }
    </style>`).appendTo(wrapper);

    $(wrapper).find('.layout-main-section').html(`
        <div id="hk-container" style="padding-top: 5px;">
            <div id="hk-rooms-grid" class="hk-grid">
                <div class="text-muted p-4">${__("Loading rooms...")}</div>
            </div>
        </div>
    `);

    load_rooms(wrapper);
};

function load_rooms(wrapper) {
    frappe.call({
        method: "hospitality_core.hospitality_core.page.housekeeping_view.housekeeping_view.get_rooms_status",
        callback: function (r) {
            if (r.message) {
                render_grid(wrapper, r.message);
            }
        }
    });
}

function render_grid(wrapper, rooms) {
    let $grid = $(wrapper).find('#hk-rooms-grid');
    $grid.empty();

    if (!rooms || rooms.length === 0) {
        $grid.html(`<div class="text-muted p-4">${__("No hotel rooms found.")}</div>`);
        return;
    }

    rooms.forEach(room => {
        let borderClass = 'status-available';
        let actionBtnHtml = '';

        if (room.status === 'Available') {
            borderClass = 'status-available';
            actionBtnHtml = `<button class="hk-btn-action hk-btn-mark-dirty" onclick="handle_action('${room.name}', 'mark_dirty')">${__("Mark Dirty")}</button>`;
        } else if (room.status === 'Occupied') {
            borderClass = 'status-occupied';
            actionBtnHtml = `<button class="hk-btn-action hk-btn-mark-dirty" onclick="handle_action('${room.name}', 'mark_dirty')">${__("Mark Dirty")}</button>`;
        } else if (room.status === 'Dirty') {
            borderClass = 'status-dirty';
            actionBtnHtml = `<button class="hk-btn-action hk-btn-mark-clean" onclick="handle_action('${room.name}', 'mark_clean')">${__("Mark Clean")}</button>`;
        } else if (room.status === 'Out of Order') {
            borderClass = 'status-ooo';
            actionBtnHtml = `<button class="hk-btn-action hk-btn-disabled" disabled>${__("Out of Order")}</button>`;
        }

        let cardHtml = `
            <div class="hk-card ${borderClass}" id="hk-card-${room.name}">
                <div>
                    <div class="hk-room-num">${room.room_number || room.name}</div>
                    <div class="hk-room-status">${__(room.status)}</div>
                </div>
                <div>
                    ${actionBtnHtml}
                </div>
            </div>
        `;
        $grid.append(cardHtml);
    });
}

window.handle_action = function (room_name, action) {
    frappe.call({
        method: "hospitality_core.hospitality_core.page.housekeeping_view.housekeeping_view.toggle_room_status",
        args: {
            room_number: room_name,
            action: action
        },
        callback: function (r) {
            if (!r.exc) {
                let current_page = frappe.pages['housekeeping_view'];
                if (current_page && current_page.wrapper) {
                    load_rooms(current_page.wrapper);
                } else {
                    location.reload();
                }
            }
        }
    });
};


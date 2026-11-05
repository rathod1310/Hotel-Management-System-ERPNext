frappe.pages['availability-tool'].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('Availability Tool'),
        single_column: true
    });

    page.add_field({
        fieldname: 'date_range',
        label: __('Date Range'),
        fieldtype: 'DateRange',
        default: [frappe.datetime.now_date(), frappe.datetime.add_days(frappe.datetime.now_date(), 1)],
        reqd: 1
    });

    page.set_primary_action(__('Check'), function () {
        let val = page.fields_dict.date_range.get_value();
        if (!val) return;

        let start, end;
        if (Array.isArray(val)) {
            start = val[0];
            end = val[1];
        } else if (typeof val === 'string') {
            if (val.indexOf(' to ') !== -1) {
                let parts = val.split(' to ');
                start = parts[0].trim();
                end = parts[1].trim();
            } else if (val.indexOf(',') !== -1) {
                let parts = val.split(',');
                start = parts[0].trim();
                end = parts[1].trim();
            } else {
                start = val;
                end = val;
            }
        }

        frappe.call({
            method: "hospitality_core.hospitality_core.page.availability_tool.availability_tool.check_availability_counts",
            args: { start_date: start, end_date: end },
            freeze: true,
            callback: function (r) {
                render_results(wrapper, r.message);
            }
        });
    });

    $(wrapper).find('.layout-main-section').append('<div id="avail-results" style="margin-top:20px;"></div>');
};

function render_results(wrapper, data) {
    if (!data) return;

    let summary_html = `<h4>${__("Room Type Summary")}</h4>
        <table class="table table-bordered">
        <thead><tr style="background-color:#f0f4f7;"><th>${__("Room Type")}</th><th>${__("Total Rooms")}</th><th>${__("Unavailable")}</th><th>${__("Available")}</th></tr></thead>
        <tbody>`;

    data.summary.forEach(row => {
        let color = row.available > 0 ? '#28a745' : '#dc3545';
        summary_html += `
            <tr>
                <td><b>${__(row.room_type)}</b></td>
                <td>${row.total}</td>
                <td>${row.occupied}</td>
                <td style="color:${color}; font-weight:bold; font-size:1.2em;">${row.available}</td>
            </tr>
        `;
    });
    summary_html += `</tbody></table>`;

    let details_html = `<h4 style="margin-top:30px;">${__("Detailed Room Status")}</h4>
        <table class="table table-bordered">
        <thead><tr style="background-color:#f0f4f7;"><th>${__("Room")}</th><th>${__("Type")}</th><th>${__("Status")}</th><th>${__("Reason/Reservation")}</th></tr></thead>
        <tbody>`;

    data.room_details.forEach(row => {
        let bg_color = '#28a745';
        let text_color = '#ffffff';

        if (row.status === 'Occupied') {
            bg_color = '#212529';
            text_color = '#ffffff';
        } else if (row.status === 'Reserved') {
            bg_color = '#17a2b8';
            text_color = '#ffffff';
        } else if (row.status === 'Dirty') {
            bg_color = '#ffc107';
            text_color = '#212529';
        } else if (row.status === 'Out of Order') {
            bg_color = '#dc3545';
            text_color = '#ffffff';
        }

        details_html += `
            <tr>
                <td>${row.room}</td>
                <td>${row.room_type}</td>
                <td><span class="label" style="background-color:${bg_color}; color:${text_color}; padding: 3px 8px; border-radius: 4px; font-weight: 600;">${__(row.status)}</span></td>
                <td><small>${row.details || '-'}</small></td>
            </tr>
        `;
    });
    details_html += `</tbody></table>`;

    $('#avail-results').html(summary_html + details_html);
}

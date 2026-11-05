app_name = "hospitality_core"
app_title = "Sky Hotel Management System"
app_publisher = "Sky Hotel Management"
app_description = "Sky Hotel Management System"
app_email = "info@skyhotel.com"
app_license = "gpl-2.0"

add_to_apps_screen = [
    {
        "name": "hospitality_core",
        "logo": "/files/images.png",
        "title": "Sky Hotel Management System",
        "route": "/desk/hospitality-core/hotel",
        "setup_wizard_text": "Let's manage your hotel business.",
        "sequence_id": 2,
    }
]

# Expose hotel settings to client session
boot_session = "hospitality_core.utils.boot_session"

# Setup custom fields after install
after_install = "hospitality_core.setup.install.after_install"

# Document Events
doc_events = {
    "Issue": {
        "on_update": "hospitality_core.maintenance.on_issue_update"
    },
    "Sales Invoice": {
        "validate": "hospitality_core.pos.validate_sales_invoice",
        "before_submit": "hospitality_core.pos.before_submit_sales_invoice"
    }
}

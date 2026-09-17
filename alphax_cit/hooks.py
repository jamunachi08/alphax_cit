app_name = "alphax_cit"
app_title = "AlphaX CIT"
app_publisher = "Neotec Integrated Solutions"
app_description = "Cash in Transit operations, custody, fleet and billing for ERPNext v15"
app_email = "support@neotec.sa"
app_license = "Commercial"
required_apps = ["frappe/erpnext"]

# ------------------------------------------------------------------ assets
app_include_css = "/assets/alphax_cit/css/cit_process_flow.css"

# ------------------------------------------------------------------ install
# Roles must exist before the DocType JSONs are imported, because their
# permission rows and the desk page link to them.
before_install = "alphax_cit.setup.install.before_install"
after_install = "alphax_cit.setup.install.after_install"
after_migrate = "alphax_cit.setup.install.after_migrate"
before_uninstall = "alphax_cit.setup.install.before_uninstall"

# ------------------------------------------------------------------ document events
doc_events = {
	"Vehicle": {
		"on_update": "alphax_cit.events.vehicle_on_update",
	},
	"Sales Invoice": {
		"on_submit": "alphax_cit.events.sales_invoice_on_submit",
	},
	"CIT Trip": {
		"on_update_after_submit": "alphax_cit.events.trip_after_submit",
	},
}

# ------------------------------------------------------------------ scheduler
scheduler_events = {
	"cron": {
		"*/5 * * * *": [
			"alphax_cit.api.gps.poll_providers",
			"alphax_cit.tasks.detect_operational_alerts",
		],
	},
	"hourly": [
		"alphax_cit.tasks.evaluate_sla",
	],
	"daily": [
		"alphax_cit.tasks.check_document_expiry",
		"alphax_cit.tasks.check_maintenance_due",
		"alphax_cit.tasks.refresh_contract_status",
		"alphax_cit.tasks.snapshot_fleet_availability",
	],
	"weekly": [
		"alphax_cit.tasks.purge_old_positions",
	],
}

# ------------------------------------------------------------------ permissions
permission_query_conditions = {
	"CIT Trip": "alphax_cit.permissions.trip_query_conditions",
	"CIT POD": "alphax_cit.permissions.pod_query_conditions",
}

has_permission = {
	"CIT Trip": "alphax_cit.permissions.trip_has_permission",
}

# ------------------------------------------------------------------ crew app
# The offline-first crew PWA ships inside this app. /crew is the short link
# handed to drivers; the real scope is the assets path so the service worker
# can control it.
website_redirects = [
	{"source": "/crew", "target": "/assets/alphax_cit/crew/index.html"},
	{"source": "/crew/", "target": "/assets/alphax_cit/crew/index.html"},
]

# ------------------------------------------------------------------ fixtures
# Seeded in code (see alphax_cit/seed) rather than fixture JSON, so installs
# are idempotent and diffable.
fixtures = []

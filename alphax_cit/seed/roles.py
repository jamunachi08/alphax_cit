import frappe

CIT_ROLES = [
	("CIT Manager", "Full CIT oversight: operations, cash, fleet, commercial"),
	("CIT Dispatcher", "Plans jobs and trips, assigns vehicles and crew"),
	("CIT Control Room", "Live monitoring, alerts and incident triage"),
	("CIT Crew", "Field crew; mobile access to own trips only"),
	("CIT Vault Controller", "Vault custody, seal issue, bag receipt"),
	("CIT Cash Counter", "Counting sessions and denomination capture"),
	("CIT Fleet Controller", "Vehicles, compliance documents, maintenance, fuel"),
	("CIT Commercial Manager", "Customers, sites, contracts, tariff, SLA"),
	("CIT Finance", "Billing runs, invoicing, discrepancy posting"),
	("CIT Auditor", "Read-only access to every CIT record and the custody chain"),
]


def seed_roles():
	for name, desc in CIT_ROLES:
		if frappe.db.exists("Role", name):
			continue
		doc = frappe.get_doc({
			"doctype": "Role", "role_name": name, "desk_access": 1,
			"is_custom": 1, "search_bar": 1, "notifications": 1,
		})
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)

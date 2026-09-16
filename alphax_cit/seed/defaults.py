import frappe

SERVICE_TYPES = [
	("Cash Collection", "جمع النقد", "Per Stop", 1, 1),
	("Cash Delivery", "تسليم النقد", "Per Stop", 1, 0),
	("ATM Replenishment", "تغذية الصراف الآلي", "Per Stop", 1, 1),
	("ATM First Line Maintenance", "الصيانة الأولية للصراف", "Per Stop", 1, 0),
	("Vault Transfer", "تحويل الخزنة", "Per Trip", 0, 1),
	("Bank Deposit", "إيداع بنكي", "Per Trip", 1, 1),
	("Emergency Call Out", "استدعاء طارئ", "Per Trip", 1, 0),
]

CHECKLIST = [
	("Vehicle armour and glazing inspected", 1, 1),
	("Tyres, lights and brakes checked", 1, 1),
	("Fuel level sufficient for route", 1, 0),
	("Radio tested with control room", 1, 1),
	("Tracker reporting confirmed", 1, 1),
	("Crew identification and permits carried", 1, 1),
	("Weapons signed out and secured", 0, 1),
	("Empty seal bags loaded", 1, 0),
	("Seal register reconciled", 1, 1),
	("Panic button tested", 1, 1),
]

THRESHOLDS = [
	("Band 1 — Supervisor", 0, 500, "CIT Vault Controller", 0),
	("Band 2 — Finance", 500.01, 5000, "CIT Finance", 0),
	("Band 3 — Management", 5000.01, 50000, "CIT Manager", 1),
	("Band 4 — Executive", 50000.01, 99999999, "CIT Manager", 1),
]


def seed_service_types():
	for name, name_ar, basis, pod, count in SERVICE_TYPES:
		if frappe.db.exists("CIT Service Type", name):
			continue
		frappe.get_doc({
			"doctype": "CIT Service Type", "service_type_name": name,
			"service_type_name_ar": name_ar, "charge_basis": basis,
			"requires_pod": pod, "requires_count": count,
		}).insert(ignore_permissions=True)


def seed_checklist_template():
	name = "Standard Pre-Trip Check"
	if frappe.db.exists("CIT Checklist Template", name):
		return
	doc = frappe.get_doc({
		"doctype": "CIT Checklist Template", "template_name": name, "applies_to": "Pre Trip",
	})
	for label, mandatory, blocks in CHECKLIST:
		doc.append("items", {"item_label": label, "mandatory": mandatory,
		                     "blocks_dispatch": blocks})
	doc.insert(ignore_permissions=True)


def seed_settings():
	st = frappe.get_single("AlphaX CIT Settings")
	if not st.approval_thresholds:
		for label, lo, hi, role, dual in THRESHOLDS:
			st.append("approval_thresholds", {
				"band_label": label, "amount_from": lo, "amount_to": hi,
				"approver_role": role if frappe.db.exists("Role", role) else None,
				"dual_approval": dual,
			})
	if not st.override_role and frappe.db.exists("Role", "CIT Manager"):
		st.override_role = "CIT Manager"
	st.flags.ignore_permissions = True
	st.save(ignore_permissions=True)

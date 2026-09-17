import json

import frappe

SHORTCUTS = [
	("CIT Process Flow", "Page", "cit-flow", "Blue"),
	("Journey (customer view)", "URL", "/cit-journey", "Purple"),
	("CIT Job", "DocType", "CIT Job", "Green"),
	("CIT Trip", "DocType", "CIT Trip", "Green"),
	("Cash Custody Entry", "DocType", "Cash Custody Entry", "Orange"),
	("Counting Session", "DocType", "Counting Session", "Orange"),
	("CIT Discrepancy", "DocType", "CIT Discrepancy", "Red"),
	("CIT Alert", "DocType", "CIT Alert", "Red"),
	("CIT Billing Run", "DocType", "CIT Billing Run", "Blue"),
]

LINKS = [
	("Operations", ["CIT Job", "CIT Trip", "CIT POD", "CIT Incident", "CIT Sync Event"]),
	("Cash & Vault", ["Cash Bag", "Seal Register", "Cash Custody Entry", "Counting Session",
	                  "CIT Discrepancy", "CIT Vault"]),
	("Fleet", ["Vehicle", "Vehicle Compliance Document", "CIT Maintenance Request",
	           "CIT Fuel Entry", "Vehicle Incident", "Fleet Availability Log", "Vehicle Log"]),
	("Commercial", ["Customer", "Customer Site", "CIT Service Contract", "CIT SLA Breach",
	                "Contract"]),
	("Finance", ["CIT Billing Run", "Sales Invoice", "Payment Entry", "Journal Entry",
	             "Bank Transaction"]),
	("Telematics", ["GPS Provider", "Geofence", "Geofence Event", "GPS Position Event",
	                "CIT Alert", "CIT Device"]),
	("Setup", ["AlphaX CIT Settings", "CIT Service Type", "CIT Checklist Template",
	           "CIT Process Flow", "CIT Process Node"]),
]


def seed_workspace():
	name = "AlphaX CIT"
	if frappe.db.exists("Workspace", name):
		return
	doc = frappe.get_doc({
		"doctype": "Workspace", "name": name, "label": name, "title": name,
		"module": "CIT Operations", "public": 1, "is_hidden": 0,
		"icon": "shipment", "sequence_id": 30,
		"content": json.dumps([
			{"id": "cit_hdr", "type": "header",
			 "data": {"text": "Cash in Transit", "col": 12}},
			{"id": "cit_sc", "type": "shortcut", "data": {"shortcut_name": "CIT Process Flow", "col": 3}},
		]),
	})
	for label, link_type, link_to, colour in SHORTCUTS:
		row = {"label": label, "type": link_type, "color": colour}
		if link_type == "URL":
			row["url"] = link_to
		else:
			row["link_to"] = link_to
		doc.append("shortcuts", row)
	for section, doctypes in LINKS:
		doc.append("links", {"label": section, "type": "Card Break", "hidden": 0})
		for dt in doctypes:
			if not frappe.db.exists("DocType", dt):
				continue
			doc.append("links", {
				"label": dt, "type": "Link", "link_type": "DocType", "link_to": dt,
				"dependencies": "", "onboard": 0, "is_query_report": 0,
			})
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)

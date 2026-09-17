import frappe
from frappe import _
from frappe.utils import date_diff, getdate


def execute(filters=None):
	return get_columns(), get_data(filters or {})


def get_columns():
	return [
		{"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link",
		 "options": "Vehicle", "width": 130},
		{"label": _("Availability"), "fieldname": "availability", "fieldtype": "Data", "width": 110},
		{"label": _("Document"), "fieldname": "document_type", "fieldtype": "Data", "width": 150},
		{"label": _("Number"), "fieldname": "document_number", "fieldtype": "Data", "width": 130},
		{"label": _("Expiry"), "fieldname": "expiry_date", "fieldtype": "Date", "width": 100},
		{"label": _("Days"), "fieldname": "days", "fieldtype": "Int", "width": 70},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Dispatchable"), "fieldname": "dispatchable", "fieldtype": "Data", "width": 110},
	]


def get_data(filters):
	out = []
	for doc in frappe.get_all(
		"Vehicle Compliance Document",
		fields=["vehicle", "document_type", "document_number", "expiry_date", "status"],
		order_by="expiry_date asc"):
		days = date_diff(getdate(doc.expiry_date), getdate()) if doc.expiry_date else None
		out.append({
			"vehicle": doc.vehicle,
			"availability": frappe.db.get_value("Vehicle", doc.vehicle, "cit_availability"),
			"document_type": doc.document_type,
			"document_number": doc.document_number,
			"expiry_date": doc.expiry_date,
			"days": days,
			"status": doc.status,
			"dispatchable": _("No") if (days is not None and days < 0) else _("Yes"),
		})
	return out

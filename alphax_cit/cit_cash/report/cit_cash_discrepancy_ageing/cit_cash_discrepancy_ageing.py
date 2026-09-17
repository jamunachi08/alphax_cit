import frappe
from frappe import _
from frappe.utils import date_diff, getdate


def execute(filters=None):
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Discrepancy"), "fieldname": "name", "fieldtype": "Link",
		 "options": "CIT Discrepancy", "width": 130},
		{"label": _("Date"), "fieldname": "discrepancy_date", "fieldtype": "Date", "width": 95},
		{"label": _("Type"), "fieldname": "discrepancy_type", "fieldtype": "Data", "width": 120},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link",
		 "options": "Customer", "width": 140},
		{"label": _("Trip"), "fieldname": "cit_trip", "fieldtype": "Link",
		 "options": "CIT Trip", "width": 120},
		{"label": _("Band"), "fieldname": "approval_band", "fieldtype": "Data", "width": 140},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
		{"label": _("Age (days)"), "fieldname": "age", "fieldtype": "Int", "width": 90},
	]


def get_data(filters):
	conditions = {"docstatus": 1}
	if filters.get("status"):
		conditions["status"] = filters["status"]
	if filters.get("customer"):
		conditions["customer"] = filters["customer"]
	rows = frappe.get_all(
		"CIT Discrepancy", filters=conditions,
		fields=["name", "discrepancy_date", "discrepancy_type", "amount", "customer",
		        "cit_trip", "approval_band", "status"],
		order_by="discrepancy_date asc")
	for r in rows:
		r["age"] = date_diff(getdate(), getdate(r.discrepancy_date))
	return rows

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Trip"), "fieldname": "name", "fieldtype": "Link", "options": "CIT Trip", "width": 130},
		{"label": _("Date"), "fieldname": "trip_date", "fieldtype": "Date", "width": 95},
		{"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 110},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": _("Stops"), "fieldname": "stops", "fieldtype": "Int", "width": 70},
		{"label": _("Completed"), "fieldname": "completed", "fieldtype": "Int", "width": 90},
		{"label": _("On Time %"), "fieldname": "on_time", "fieldtype": "Percent", "width": 95},
		{"label": _("Declared Value"), "fieldname": "total_declared_value", "fieldtype": "Currency", "width": 130},
		{"label": _("Discrepancy"), "fieldname": "discrepancy", "fieldtype": "Currency", "width": 120},
		{"label": _("Distance (km)"), "fieldname": "distance_km", "fieldtype": "Float", "width": 110},
		{"label": _("Billing"), "fieldname": "billing_status", "fieldtype": "Data", "width": 100},
	]


def get_data(filters):
	conditions = {"docstatus": 1}
	if filters.get("from_date") and filters.get("to_date"):
		conditions["trip_date"] = ["between", [filters["from_date"], filters["to_date"]]]
	if filters.get("vehicle"):
		conditions["vehicle"] = filters["vehicle"]
	rows = frappe.get_all(
		"CIT Trip", filters=conditions,
		fields=["name", "trip_date", "vehicle", "status", "total_declared_value",
		        "distance_km", "billing_status"],
		order_by="trip_date desc")
	for r in rows:
		stops = frappe.get_all("CIT Trip Stop", filters={"parent": r.name},
		                       fields=["stop_status", "planned_arrival", "actual_arrival"])
		r["stops"] = len(stops)
		r["completed"] = len([s for s in stops if s.stop_status == "Completed"])
		timed = [s for s in stops if s.planned_arrival and s.actual_arrival]
		on_time = [s for s in timed if s.actual_arrival <= s.planned_arrival]
		r["on_time"] = (len(on_time) / len(timed) * 100.0) if timed else 0
		disc = frappe.get_all("CIT Discrepancy",
		                      filters={"cit_trip": r.name, "docstatus": 1},
		                      fields=["sum(amount) as total"])
		r["discrepancy"] = flt(disc[0].total) if disc else 0
	return rows

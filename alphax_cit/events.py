"""Hooked document events. Thin by design — logic lives in the controllers."""

import frappe


def vehicle_on_update(doc, method=None):
	"""Keep the linked Asset in step with the vehicle record."""
	if doc.get("cit_asset"):
		frappe.db.set_value("Asset", doc.cit_asset, "cit_vehicle", doc.name)


def sales_invoice_on_submit(doc, method=None):
	"""Mark the originating trips as billed once the invoice is submitted."""
	trips = {d.get("cit_trip") for d in doc.items if d.get("cit_trip")}
	for trip in trips:
		frappe.db.set_value("CIT Trip", trip, "billing_status", "Billed")


def trip_after_submit(doc, method=None):
	if doc.status == "Reconciled" and doc.reconciliation_status == "Pending":
		frappe.db.set_value("CIT Trip", doc.name, "reconciliation_status", "In Progress")

import frappe
from frappe import _
from frappe.model.document import Document


class VehicleIncident(Document):
	def on_submit(self):
		if not self.cit_incident:
			doc = frappe.get_doc({
				"doctype": "CIT Incident", "incident_datetime": self.incident_date,
				"incident_category": "Accident" if self.incident_type == "Accident" else "Breakdown",
				"severity": "High", "vehicle": self.vehicle, "cit_trip": self.cit_trip,
				"employee": self.driver, "company": self.company,
				"description": self.description,
				"police_report_no": self.police_report_no,
			})
			doc.flags.ignore_permissions = True
			doc.insert(ignore_permissions=True)
			self.db_set("cit_incident", doc.name)
		frappe.get_doc({
			"doctype": "Fleet Availability Log", "vehicle": self.vehicle,
			"log_date": frappe.utils.getdate(self.incident_date),
			"availability_status": "Accident" if self.incident_type == "Accident" else "Workshop",
			"cit_trip": self.cit_trip, "downtime_hours": self.downtime_hours,
			"reason": _("Vehicle incident {0}").format(self.name),
		}).insert(ignore_permissions=True)

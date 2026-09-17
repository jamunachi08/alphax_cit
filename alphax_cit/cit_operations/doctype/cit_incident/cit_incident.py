import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class CITIncident(Document):
	def before_insert(self):
		self.reported_by = frappe.session.user

	def on_update(self):
		if self.status in ("Closed", "Rejected") and not self.closed_on:
			self.db_set("closed_on", now_datetime())

	def on_submit(self):
		if self.severity in ("High", "Critical"):
			frappe.publish_realtime("cit_incident", {"name": self.name, "severity": self.severity})

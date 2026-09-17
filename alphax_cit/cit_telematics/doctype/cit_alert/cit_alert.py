import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class CITAlert(Document):
	@frappe.whitelist()
	def acknowledge(self):
		self.db_set({"status": "Acknowledged", "acknowledged_by": frappe.session.user,
		             "acknowledged_on": now_datetime()})
		return self.status

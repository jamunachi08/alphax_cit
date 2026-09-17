import frappe
from frappe.model.document import Document
from frappe.utils import date_diff, getdate


class VehicleComplianceDocument(Document):
	def validate(self):
		if self.expiry_date:
			self.days_to_expiry = date_diff(getdate(self.expiry_date), getdate())
			if self.days_to_expiry < 0:
				self.status = "Expired"
			elif self.days_to_expiry <= 90:
				self.status = "Expiring"
			else:
				self.status = "Valid"

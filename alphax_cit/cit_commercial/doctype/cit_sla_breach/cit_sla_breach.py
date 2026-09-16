import frappe
from frappe.model.document import Document
from frappe.utils import flt


class CITSLABreach(Document):
	def validate(self):
		self.variance_minutes = int(flt(self.actual_minutes) - flt(self.target_minutes))
		if self.waived and not self.waived_by:
			self.waived_by = frappe.session.user
			self.status = "Waived"

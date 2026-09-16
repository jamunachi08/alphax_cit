import frappe
from frappe import _
from frappe.model.document import Document


class CITProcessNode(Document):
	def validate(self):
		if self.node_type == "DocType" and not self.document_type:
			frappe.throw(_("A document type is required for a DocType node"))
		if self.node_type == "Report" and not self.report_name:
			frappe.throw(_("A report name is required for a Report node"))
		if self.document_type:
			app = frappe.db.get_value("DocType", self.document_type, "module")
			std = frappe.db.get_value("DocType", self.document_type, "custom")
			self.is_erpnext_standard = 0 if (app or "").startswith("CIT ") else 1
		if self.filters_json:
			import json
			try:
				json.loads(self.filters_json)
			except ValueError:
				frappe.throw(_("Filters must be valid JSON"))

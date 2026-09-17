import frappe
from frappe.model.document import Document


class CITMaintenanceRequest(Document):
	def on_update(self):
		if self.status == "Completed" and not self.asset_maintenance_log:
			asset = frappe.db.get_value("Vehicle", self.vehicle, "cit_asset")
			if not asset:
				return
			try:
				log = frappe.get_doc({
					"doctype": "Asset Maintenance Log", "asset_name": asset,
					"task": self.description or self.maintenance_type,
					"maintenance_status": "Completed",
					"completion_date": self.completed_on or frappe.utils.nowdate(),
					"description": self.description,
				})
				log.flags.ignore_permissions = True
				log.insert(ignore_permissions=True)
				self.db_set("asset_maintenance_log", log.name)
			except Exception:
				frappe.log_error(frappe.get_traceback(), "CIT Maintenance -> Asset Maintenance Log")

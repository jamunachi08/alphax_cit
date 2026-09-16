import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import date_diff, getdate


class CITServiceContract(Document):
	def validate(self):
		if getdate(self.end_date) < getdate(self.start_date):
			frappe.throw(_("Contract end date cannot precede the start date"))
		for row in self.sites:
			cust = frappe.db.get_value("Customer Site", row.customer_site, "customer")
			if cust != self.customer:
				frappe.throw(_("Site {0} does not belong to {1}").format(
					row.customer_site, self.customer))
		if not self.tariff:
			frappe.throw(_("At least one tariff line is required"))
		self.set_status()

	def set_status(self):
		if self.docstatus == 0:
			self.status = "Draft"
			return
		days = date_diff(getdate(self.end_date), getdate())
		if days < 0:
			self.status = "Expired"
		elif days <= (self.notice_days or 90):
			self.status = "Expiring"
		else:
			self.status = "Active"

	def on_submit(self):
		self.set_status()
		self.db_set("status", self.status)

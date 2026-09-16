import frappe
from frappe import _
from frappe.model.document import Document

from alphax_cit.cit_utils import s_flag


class CITJob(Document):
	def validate(self):
		self.validate_contract()
		self.validate_site()
		if self.docstatus == 0 and self.status == "Draft":
			self.status = "Draft"

	def validate_contract(self):
		if not self.service_contract:
			return
		con = frappe.db.get_value(
			"CIT Service Contract", self.service_contract,
			["customer", "start_date", "end_date", "status", "docstatus"], as_dict=True)
		if not con:
			return
		if con.customer != self.customer:
			frappe.throw(_("Contract {0} does not belong to customer {1}").format(
				self.service_contract, self.customer))
		if con.docstatus != 1 or con.status in ("Expired", "Terminated"):
			frappe.throw(_("Contract {0} is not active").format(self.service_contract))
		if self.job_date and (self.job_date < con.start_date or self.job_date > con.end_date):
			frappe.throw(_("Job date {0} falls outside the contract period {1} to {2}").format(
				self.job_date, con.start_date, con.end_date))

	def validate_site(self):
		if not self.customer_site:
			return
		cust = frappe.db.get_value("Customer Site", self.customer_site, "customer")
		if cust and cust != self.customer:
			frappe.throw(_("Site {0} does not belong to customer {1}").format(
				self.customer_site, self.customer))

	def on_submit(self):
		self.db_set("status", "Open")

	def on_cancel(self):
		if self.trip:
			frappe.throw(_("Cancel the trip {0} before cancelling this job").format(self.trip))
		self.db_set("status", "Cancelled")

	def set_status(self, status):
		self.db_set("status", status, update_modified=False)


@frappe.whitelist()
def get_open_jobs(job_date=None, customer=None):
	filters = {"docstatus": 1, "status": ["in", ["Open", "Planned"]]}
	if job_date:
		filters["job_date"] = job_date
	if customer:
		filters["customer"] = customer
	return frappe.get_all(
		"CIT Job", filters=filters,
		fields=["name", "customer", "customer_site", "service_type", "job_date",
		        "window_from", "window_to", "declared_value", "expected_bags", "priority", "status"],
		order_by="priority desc, window_from asc", limit_page_length=200)

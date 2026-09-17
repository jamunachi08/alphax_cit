import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class CITPOD(Document):
	def validate(self):
		self.total_declared = sum(flt(b.declared_amount) for b in (self.bags or []))
		if not self.signature and not self.otp_verified:
			frappe.msgprint(_("No signature or OTP verification captured on this proof of delivery."),
			                indicator="orange", alert=True)
		for b in self.bags or []:
			if not b.seal_no:
				b.seal_no = frappe.db.get_value("Cash Bag", b.cash_bag, "seal_no")

	def on_submit(self):
		self.transfer_custody()
		self.mark_stop_complete()

	def transfer_custody(self):
		"""Write one custody entry per bag: customer -> crew, or crew -> customer."""
		from alphax_cit.cit_cash.doctype.cash_custody_entry.cash_custody_entry import record_custody

		trip = frappe.get_doc("CIT Trip", self.cit_trip)
		custodian = None
		for c in trip.crew:
			if c.crew_role == "Custodian":
				custodian = c.employee
				break
		custodian = custodian or (trip.crew[0].employee if trip.crew else None)
		customer = frappe.db.get_value("CIT Job", self.cit_job, "customer")

		for b in self.bags or []:
			if self.pod_type == "Collection":
				frm = ("Customer", customer)
				to = ("Employee", custodian)
			else:
				frm = ("Employee", custodian)
				to = ("Customer", customer)
			record_custody(
				cash_bag=b.cash_bag, amount=b.declared_amount, seal_no=b.seal_no,
				from_party_type=frm[0], from_party=frm[1],
				to_party_type=to[0], to_party=to[1],
				reference_doctype=self.doctype, reference_name=self.name,
				cit_trip=self.cit_trip, latitude=self.latitude, longitude=self.longitude,
				company=self.company)
			if not b.seal_intact:
				frappe.get_doc({
					"doctype": "CIT Incident", "incident_datetime": self.pod_datetime,
					"incident_category": "Seal Broken", "severity": "Critical",
					"cit_trip": self.cit_trip, "cit_job": self.cit_job,
					"customer_site": self.customer_site, "company": self.company,
					"description": _("Seal {0} reported not intact at proof of delivery {1}").format(
						b.seal_no, self.name),
				}).insert(ignore_permissions=True)

	def mark_stop_complete(self):
		rows = frappe.get_all("CIT Trip Stop",
		                      filters={"parent": self.cit_trip, "cit_job": self.cit_job},
		                      fields=["name"])
		for r in rows:
			frappe.db.set_value("CIT Trip Stop", r.name, {
				"stop_status": "Completed",
				"actual_departure": self.pod_datetime,
			})
		frappe.db.set_value("CIT Job", self.cit_job, "status", "Completed")

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

from alphax_cit.cit_utils import settings


class CITDiscrepancy(Document):
	def validate(self):
		self.apply_threshold()

	def apply_threshold(self):
		"""Route by value band. Bands are configured, never hard-coded."""
		amount = abs(flt(self.amount))
		band = None
		try:
			for row in settings().approval_thresholds or []:
				if flt(row.amount_from) <= amount <= flt(row.amount_to):
					band = row
					break
		except Exception:
			band = None
		if band:
			self.approval_band = band.band_label
			self.required_approver_role = band.approver_role
			if band.dual_approval:
				self.required_approver_role = f"{band.approver_role} (dual approval)"
		else:
			self.approval_band = _("Unbanded")
			self.required_approver_role = "CIT Manager"
		if self.status == "Open":
			self.status = "Pending Approval"

	def on_submit(self):
		frappe.publish_realtime("cit_discrepancy", {"name": self.name, "amount": self.amount})

	@frappe.whitelist()
	def approve(self, responsible_party=None, recoverable=0, explanation=None):
		role = (self.required_approver_role or "").replace(" (dual approval)", "")
		if role and role not in frappe.get_roles():
			frappe.throw(_("Only {0} may approve a discrepancy in band {1}").format(
				role, self.approval_band))
		if responsible_party:
			self.db_set("responsible_party", responsible_party)
		self.db_set("recoverable", int(recoverable or 0))
		if explanation:
			self.db_set("explanation", explanation)
		je = self.post_journal_entry()
		self.db_set({"status": "Approved", "approved_by": frappe.session.user,
		             "approved_on": now_datetime(), "journal_entry": je})
		return je

	def post_journal_entry(self):
		"""Post the variance to the configured account. Skipped when unconfigured."""
		if self.journal_entry or not flt(self.amount):
			return self.journal_entry
		st = settings()
		is_shortage = self.discrepancy_type in ("Shortage", "Counterfeit", "Damaged Note", "Missing Bag")
		account = self.expense_account or (
			st.discrepancy_expense_account if is_shortage else st.discrepancy_income_account)
		cash_account = frappe.db.get_value("CIT Vault", {"company": self.company}, "cash_account") \
			if frappe.db.has_column("CIT Vault", "company") else None
		if not account or not cash_account:
			frappe.msgprint(_("Discrepancy accounts are not configured — no journal entry posted."),
			                indicator="orange", alert=True)
			return None
		je = frappe.get_doc({
			"doctype": "Journal Entry", "voucher_type": "Journal Entry",
			"company": self.company, "posting_date": self.discrepancy_date,
			"user_remark": _("CIT discrepancy {0} ({1})").format(self.name, self.discrepancy_type),
			"accounts": [
				{"account": account, "debit_in_account_currency": flt(self.amount) if is_shortage else 0,
				 "credit_in_account_currency": 0 if is_shortage else flt(self.amount)},
				{"account": cash_account, "credit_in_account_currency": flt(self.amount) if is_shortage else 0,
				 "debit_in_account_currency": 0 if is_shortage else flt(self.amount)},
			],
		})
		je.flags.ignore_permissions = True
		je.insert(ignore_permissions=True)
		je.submit()
		return je.name


@frappe.whitelist()
def open_discrepancy_value(trip):
	rows = frappe.get_all("CIT Discrepancy",
	                      filters={"cit_trip": trip, "docstatus": 1,
	                               "status": ["in", ["Open", "Pending Approval"]]},
	                      fields=["sum(amount) as total"])
	return flt(rows[0].total) if rows else 0

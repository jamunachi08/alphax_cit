import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class CountingSession(Document):
	def validate(self):
		if self.counter and self.counter == self.witness:
			frappe.throw(_("The counter and the witness must be different people"))
		total_dec = total_cnt = total_cf = total_dm = 0.0
		for b in self.bags or []:
			if b.denominations:
				b.counted_amount = sum(flt(d.amount) for d in b.denominations)
			b.declared_amount = b.declared_amount or flt(
				frappe.db.get_value("Cash Bag", b.cash_bag, "declared_amount"))
			b.seal_no = b.seal_no or frappe.db.get_value("Cash Bag", b.cash_bag, "seal_no")
			b.variance = flt(b.counted_amount) - flt(b.declared_amount)
			total_dec += flt(b.declared_amount)
			total_cnt += flt(b.counted_amount)
			total_cf += flt(b.counterfeit_amount)
			total_dm += flt(b.damaged_amount)
		self.total_declared = total_dec
		self.total_counted = total_cnt
		self.total_variance = total_cnt - total_dec
		self.counterfeit_amount = total_cf
		self.damaged_amount = total_dm
		self.status = "Variance" if abs(self.total_variance) > 0.005 else "Balanced"

	def on_submit(self):
		for b in self.bags or []:
			frappe.db.set_value("Cash Bag", b.cash_bag, {
				"counted_amount": b.counted_amount,
				"variance_amount": b.variance,
				"bag_status": "Counted",
				"counting_session": self.name,
			})
			if abs(flt(b.variance)) > 0.005:
				self.create_discrepancy(b, "Shortage" if b.variance < 0 else "Excess", abs(b.variance))
			if flt(b.counterfeit_amount):
				self.create_discrepancy(b, "Counterfeit", flt(b.counterfeit_amount))
			if flt(b.damaged_amount):
				self.create_discrepancy(b, "Damaged Note", flt(b.damaged_amount))
			if not b.seal_intact:
				self.create_discrepancy(b, "Seal Broken", 0)
		if self.cit_trip:
			status = "Variance" if self.status == "Variance" else "Balanced"
			frappe.db.set_value("CIT Trip", self.cit_trip, "reconciliation_status", status)

	def create_discrepancy(self, bag_row, dtype, amount):
		doc = frappe.get_doc({
			"doctype": "CIT Discrepancy",
			"discrepancy_date": self.session_date,
			"discrepancy_type": dtype,
			"amount": amount,
			"cash_bag": bag_row.cash_bag,
			"counting_session": self.name,
			"cit_trip": self.cit_trip,
			"customer": frappe.db.get_value("Cash Bag", bag_row.cash_bag, "customer"),
			"company": self.company,
		})
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc.name

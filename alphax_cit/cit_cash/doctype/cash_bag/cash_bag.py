import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class CashBag(Document):
	def validate(self):
		if self.counted_amount:
			self.variance_amount = flt(self.counted_amount) - flt(self.declared_amount)
		if self.seal_no:
			used = frappe.db.exists("Cash Bag", {"seal_no": self.seal_no, "name": ["!=", self.name],
			                                     "bag_status": ["not in", ["Deposited", "Returned"]]})
			if used:
				frappe.throw(_("Seal {0} is already applied to bag {1}").format(self.seal_no, used))

	def on_update(self):
		if self.seal_no:
			rows = frappe.get_all("Seal Entry", filters={"seal_no": self.seal_no}, fields=["name"])
			for r in rows:
				frappe.db.set_value("Seal Entry", r.name,
				                    {"seal_status": "Applied", "cash_bag": self.name})

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from alphax_cit.cit_utils import s_value


class SealRegister(Document):
	def validate(self):
		if cint(self.to_no) < cint(self.from_no):
			frappe.throw(_("Seal range end cannot be lower than the start"))
		self.total_seals = cint(self.to_no) - cint(self.from_no) + 1
		if self.total_seals > 5000:
			frappe.throw(_("A single register is limited to 5000 seals"))
		if not self.seals:
			prefix = self.seal_prefix or s_value("seal_prefix", "SL")
			for n in range(cint(self.from_no), cint(self.to_no) + 1):
				self.append("seals", {"seal_no": f"{prefix}{n:08d}", "seal_status": "Issued"})

	def on_submit(self):
		for row in self.seals:
			if frappe.db.exists("Seal Entry", {"seal_no": row.seal_no, "docstatus": 1,
			                                   "parent": ["!=", self.name]}):
				frappe.throw(_("Seal {0} already exists in another register").format(row.seal_no))

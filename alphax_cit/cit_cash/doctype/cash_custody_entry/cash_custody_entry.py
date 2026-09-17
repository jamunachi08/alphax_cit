import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from alphax_cit.cit_utils import content_hash, s_flag


class CashCustodyEntry(Document):
	"""Append-only, hash-chained record of who held which value when.

	Cancellation and deletion are blocked by design. A mistake is corrected by a
	reversing entry that references the original.
	"""

	def before_insert(self):
		self.entry_datetime = self.entry_datetime or now_datetime()
		self.recorded_by = frappe.session.user

	def validate(self):
		if self.from_party_type == self.to_party_type and self.from_party == self.to_party:
			frappe.throw(_("Custody cannot transfer to the same party"))

	def before_submit(self):
		if s_flag("enable_hash_chain", 1):
			self.build_chain()

	def build_chain(self):
		prev = frappe.db.sql(
			"""select name, content_hash from `tabCash Custody Entry`
			   where docstatus = 1 and company = %s
			   order by creation desc limit 1""",
			(self.company,), as_dict=True)
		self.previous_entry = prev[0].name if prev else None
		self.previous_hash = prev[0].content_hash if prev else ""
		self.content_hash = content_hash(
			{
				"bag": self.cash_bag, "amount": str(self.amount), "seal": self.seal_no,
				"from": f"{self.from_party_type}:{self.from_party}",
				"to": f"{self.to_party_type}:{self.to_party}",
				"at": str(self.entry_datetime), "ref": f"{self.reference_doctype}:{self.reference_name}",
				"by": self.recorded_by,
			},
			self.previous_hash or "",
		)

	def on_submit(self):
		bag_status = {
			"Employee": "In Transit", "Vault": "At Vault",
			"Bank": "Deposited", "Customer": "Returned",
		}.get(self.to_party_type)
		frappe.db.set_value("Cash Bag", self.cash_bag, {
			"current_custodian_type": self.to_party_type,
			"current_custodian": self.to_party,
			"bag_status": bag_status or "In Transit",
		})

	def on_cancel(self):
		frappe.throw(_(
			"Custody entries cannot be cancelled. Post a reversing entry instead — "
			"the chain of custody is an audit record."))

	def on_trash(self):
		frappe.throw(_("Custody entries cannot be deleted."))


def record_custody(**kwargs):
	doc = frappe.get_doc(dict(doctype="Cash Custody Entry", **kwargs))
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


@frappe.whitelist()
def reverse(entry, reason):
	src = frappe.get_doc("Cash Custody Entry", entry)
	src.check_permission("submit")
	rev = frappe.get_doc({
		"doctype": "Cash Custody Entry", "cash_bag": src.cash_bag, "amount": src.amount,
		"seal_no": src.seal_no, "from_party_type": src.to_party_type, "from_party": src.to_party,
		"to_party_type": src.from_party_type, "to_party": src.from_party,
		"reference_doctype": src.doctype, "reference_name": src.name,
		"cit_trip": src.cit_trip, "company": src.company,
		"is_reversal": 1, "reverses_entry": src.name,
	})
	rev.insert(ignore_permissions=True)
	rev.add_comment("Comment", _("Reversal reason: {0}").format(reason))
	rev.submit()
	return rev.name


@frappe.whitelist()
def verify_chain(company=None, limit=5000):
	"""Re-compute the hash chain and report the first broken link, if any."""
	filters = {"docstatus": 1}
	if company:
		filters["company"] = company
	rows = frappe.get_all(
		"Cash Custody Entry", filters=filters, order_by="creation asc",
		limit_page_length=int(limit),
		fields=["name", "cash_bag", "amount", "seal_no", "from_party_type", "from_party",
		        "to_party_type", "to_party", "entry_datetime", "reference_doctype",
		        "reference_name", "recorded_by", "previous_hash", "content_hash"])
	prev_hash = ""
	for r in rows:
		expected = content_hash(
			{
				"bag": r.cash_bag, "amount": str(r.amount), "seal": r.seal_no,
				"from": f"{r.from_party_type}:{r.from_party}",
				"to": f"{r.to_party_type}:{r.to_party}",
				"at": str(r.entry_datetime),
				"ref": f"{r.reference_doctype}:{r.reference_name}",
				"by": r.recorded_by,
			},
			r.previous_hash or "",
		)
		if expected != r.content_hash:
			return {"ok": False, "broken_at": r.name, "checked": len(rows)}
		prev_hash = r.content_hash
	return {"ok": True, "checked": len(rows), "head": prev_hash}

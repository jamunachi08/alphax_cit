import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from alphax_cit.cit_utils import s_flag, s_value


class CITBillingRun(Document):
	def validate(self):
		self.total_amount = sum(flt(l.amount) for l in (self.lines or []))
		self.trips_billed = len({l.cit_trip for l in (self.lines or []) if l.cit_trip and not l.held})
		self.trips_held = len({l.cit_trip for l in (self.lines or []) if l.held})

	@frappe.whitelist()
	def rate_trips(self):
		"""Select completed, reconciled trips in the period and price them."""
		from alphax_cit.cit_cash.doctype.cit_discrepancy.cit_discrepancy import open_discrepancy_value

		self.set("lines", [])
		hold_threshold = flt(s_value("discrepancy_hold_threshold", 500))
		hold_enabled = s_flag("hold_billing_on_discrepancy", 1)

		trips = frappe.get_all(
			"CIT Trip",
			filters={
				"docstatus": 1, "trip_date": ["between", [self.from_date, self.to_date]],
				"status": ["in", ["Reconciled", "Closed"]],
				"billing_status": ["!=", "Billed"],
			},
			fields=["name", "distance_km", "trip_date"])

		for t in trips:
			held = False
			hold_reason = None
			if hold_enabled:
				open_value = open_discrepancy_value(t.name)
				if open_value > hold_threshold:
					held = True
					hold_reason = _("Open discrepancy of {0}").format(open_value)
			for stop in frappe.get_all(
				"CIT Trip Stop", filters={"parent": t.name, "stop_status": "Completed"},
				fields=["cit_job", "customer_site", "declared_value", "bags_count",
				        "dwell_minutes", "actual_arrival", "planned_arrival"]):
				job = frappe.db.get_value(
					"CIT Job", stop.cit_job,
					["customer", "service_type", "service_contract"], as_dict=True)
				if not job:
					continue
				if self.customer and job.customer != self.customer:
					continue
				if self.service_contract and job.service_contract != self.service_contract:
					continue
				for line in self.price_stop(job, stop, t):
					line.update({"held": int(held), "hold_reason": hold_reason})
					self.append("lines", line)
		self.status = "Rated"
		self.validate()
		self.save()
		return {"lines": len(self.lines), "total": self.total_amount}

	def price_stop(self, job, stop, trip):
		out = []
		contract = frappe.get_doc("CIT Service Contract", job.service_contract) \
			if job.service_contract else None
		if not contract:
			return out
		for tl in contract.tariff:
			if tl.service_type != job.service_type:
				continue
			qty = rate = 0.0
			if tl.charge_basis == "Per Stop":
				qty, rate = 1, flt(tl.rate)
			elif tl.charge_basis == "Per Bag":
				qty, rate = cint(stop.bags_count), flt(tl.rate)
			elif tl.charge_basis == "Ad Valorem":
				value = flt(stop.declared_value)
				if tl.value_band_from and value < flt(tl.value_band_from):
					continue
				if tl.value_band_to and value > flt(tl.value_band_to):
					continue
				qty, rate = 1, value * flt(tl.rate_percent) / 100.0
			elif tl.charge_basis == "Per KM":
				qty, rate = flt(trip.distance_km), flt(tl.rate)
			elif tl.charge_basis == "Waiting Time":
				billable = max(0.0, flt(stop.dwell_minutes) - flt(tl.free_units))
				qty, rate = billable, flt(tl.rate)
			elif tl.charge_basis == "Per Trip":
				qty, rate = 1, flt(tl.rate)
			else:
				continue
			amount = flt(qty) * flt(rate)
			if tl.minimum_charge and amount < flt(tl.minimum_charge):
				amount = flt(tl.minimum_charge)
			if not amount:
				continue
			out.append({
				"customer": job.customer, "cit_trip": trip.name, "cit_job": stop.cit_job,
				"service_type": job.service_type, "charge_basis": tl.charge_basis,
				"billing_item": tl.billing_item, "qty": qty or 1, "rate": rate,
				"amount": amount,
			})
		return out

	def on_submit(self):
		self.create_invoices()
		self.db_set("status", "Invoiced")

	def create_invoices(self):
		by_customer = {}
		for line in self.lines:
			if line.held:
				continue
			by_customer.setdefault(line.customer, []).append(line)
		for customer, lines in by_customer.items():
			si = frappe.get_doc({
				"doctype": "Sales Invoice", "customer": customer, "company": self.company,
				"posting_date": self.posting_date, "cit_billing_run": self.name,
				"items": [{
					"item_code": l.billing_item, "qty": l.qty or 1, "rate": l.rate,
					"amount": l.amount, "cit_trip": l.cit_trip,
					"description": _("{0} — trip {1}").format(l.charge_basis, l.cit_trip),
				} for l in lines],
			})
			si.flags.ignore_permissions = True
			si.insert(ignore_permissions=True)
			for l in lines:
				frappe.db.set_value("CIT Billing Run Line", l.name, "sales_invoice", si.name)
				if l.cit_trip:
					frappe.db.set_value("CIT Trip", l.cit_trip, "billing_status", "Billed")
		for line in self.lines:
			if line.held and line.cit_trip:
				frappe.db.set_value("CIT Trip", line.cit_trip, "billing_status", "Held")

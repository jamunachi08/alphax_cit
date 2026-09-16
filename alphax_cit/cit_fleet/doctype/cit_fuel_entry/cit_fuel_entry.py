import frappe
from frappe.model.document import Document
from frappe.utils import flt


class CITFuelEntry(Document):
	def validate(self):
		self.amount = flt(self.litres) * flt(self.rate)
		last = frappe.db.sql(
			"""select odometer from `tabCIT Fuel Entry`
			   where vehicle = %s and docstatus = 1 and odometer < %s
			   order by odometer desc limit 1""",
			(self.vehicle, flt(self.odometer)))
		if last and flt(self.litres):
			self.km_per_litre = (flt(self.odometer) - flt(last[0][0])) / flt(self.litres)

	def on_submit(self):
		"""Mirror into the standard ERPNext Vehicle Log so fleet cost stays in one place."""
		log = frappe.get_doc({
			"doctype": "Vehicle Log", "license_plate": self.vehicle, "employee": None,
			"date": self.fuel_date, "odometer": self.odometer,
			"fuel_qty": self.litres, "price": self.rate,
		})
		log.flags.ignore_permissions = True
		try:
			log.insert(ignore_permissions=True)
			log.submit()
			self.db_set("vehicle_log", log.name)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "CIT Fuel Entry -> Vehicle Log")

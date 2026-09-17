import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, now_datetime

from alphax_cit import cit_utils as u

TRANSITIONS = {
	"Draft": ["Planned", "Cancelled"],
	"Planned": ["Dispatched", "Cancelled"],
	"Dispatched": ["In Transit", "Cancelled"],
	"In Transit": ["Returned to Vault"],
	"Returned to Vault": ["Reconciled"],
	"Reconciled": ["Closed"],
	"Closed": [],
	"Cancelled": [],
}


class CITTrip(Document):
	def validate(self):
		self.set_totals()
		self.validate_crew_composition()
		self.pull_checklist()
		if self.odometer_in and self.odometer_out:
			self.distance_km = flt(self.odometer_in) - flt(self.odometer_out)
			if self.distance_km < 0:
				frappe.throw(_("Closing odometer cannot be lower than the opening odometer"))

	def set_totals(self):
		self.total_declared_value = sum(flt(s.declared_value) for s in (self.stops or []))
		for i, s in enumerate(self.stops or [], start=1):
			s.idx_seq = i

	def validate_crew_composition(self):
		minimum = cint(u.s_value("minimum_crew_size", 3))
		if len(self.crew or []) < minimum:
			frappe.throw(_("A trip requires at least {0} crew members").format(minimum))
		roles = [c.crew_role for c in self.crew]
		if "Driver" not in roles:
			frappe.throw(_("A driver must be assigned"))
		seen = set()
		for c in self.crew:
			if c.employee in seen:
				frappe.throw(_("Employee {0} is listed twice in the crew").format(c.employee))
			seen.add(c.employee)
			c.employee_name = frappe.db.get_value("Employee", c.employee, "employee_name")

	def pull_checklist(self):
		if not self.checklist_template or self.checklist:
			return
		tmpl = frappe.get_doc("CIT Checklist Template", self.checklist_template)
		for row in tmpl.items:
			self.append("checklist", {
				"item_label": row.item_label,
				"mandatory": row.mandatory,
				"blocks_dispatch": row.blocks_dispatch,
			})

	# ---------------------------------------------------------- dispatch gate
	def dispatch_blockers(self):
		"""Return a list of reasons the trip may not be dispatched."""
		blockers = []
		if u.s_flag("block_expired_vehicle_documents", 1) and self.vehicle:
			ok, reasons = u.vehicle_document_status(self.vehicle)
			blockers += [_("Vehicle {0}: {1}").format(self.vehicle, r) for r in reasons]
		for c in self.crew or []:
			if u.s_flag("block_expired_crew_documents", 1):
				ok, reasons = u.employee_document_status(c.employee)
				c.licence_ok = 1 if ok else 0
				c.clearance_ok = 1 if ok else 0
				blockers += [_("Crew {0}: {1}").format(c.employee_name or c.employee, r) for r in reasons]
			if u.s_flag("block_overlapping_assignment", 1):
				clash = self.overlapping_assignment(c.employee)
				if clash:
					blockers.append(_("Crew {0} is already assigned to trip {1}").format(
						c.employee_name or c.employee, clash))
			ok_rest, gap = u.rest_hours_ok(c.employee, self.planned_start)
			if not ok_rest:
				blockers.append(_("Crew {0} has had only {1} hours rest").format(
					c.employee_name or c.employee, round(gap, 1)))
		for row in self.checklist or []:
			if row.blocks_dispatch and not row.checked:
				blockers.append(_("Pre-trip check not completed: {0}").format(row.item_label))
		return blockers

	def overlapping_assignment(self, employee):
		if not self.planned_start:
			return None
		rows = frappe.db.sql(
			"""
			select t.name from `tabCIT Trip` t
			inner join `tabCIT Trip Crew` c on c.parent = t.name
			where c.employee = %(emp)s and t.name != %(self)s and t.docstatus < 2
			  and t.status in ('Planned','Dispatched','In Transit')
			  and t.trip_date = %(d)s
			limit 1
			""",
			{"emp": employee, "self": self.name or "new", "d": self.trip_date},
		)
		return rows[0][0] if rows else None

	def on_submit(self):
		self.db_set("status", "Planned")
		for s in self.stops or []:
			if s.cit_job:
				frappe.db.set_value("CIT Job", s.cit_job, {"status": "Planned", "trip": self.name})

	def on_cancel(self):
		if frappe.db.exists("Cash Custody Entry", {"cit_trip": self.name, "docstatus": 1}):
			frappe.throw(_("Custody entries exist against this trip. It cannot be cancelled."))
		self.db_set("status", "Cancelled")
		for s in self.stops or []:
			if s.cit_job:
				frappe.db.set_value("CIT Job", s.cit_job, {"status": "Open", "trip": None})

	def move_to(self, new_status, ignore_blockers=False, override_reason=None):
		allowed = TRANSITIONS.get(self.status, [])
		if new_status not in allowed:
			frappe.throw(_("Cannot move a trip from {0} to {1}").format(self.status, new_status))
		if new_status == "Dispatched":
			blockers = self.dispatch_blockers()
			if blockers and not ignore_blockers:
				frappe.throw(_("Dispatch blocked:") + "<br>" + "<br>".join(blockers))
			if blockers and ignore_blockers:
				if not u.s_flag("allow_dispatch_override", 1):
					frappe.throw(_("Dispatch override is disabled"))
				role = u.s_value("override_role")
				if role and role not in frappe.get_roles():
					frappe.throw(_("Only {0} may override a dispatch block").format(role))
				if not override_reason:
					frappe.throw(_("An override reason is required"))
				self.db_set("dispatch_override_reason", override_reason)
				self.db_set("dispatch_override_by", frappe.session.user)
				u.raise_alert("Geofence Breach", _("Dispatch overridden on {0}: {1}").format(
					self.name, override_reason), severity="Critical",
					vehicle=self.vehicle, cit_trip=self.name)
		if new_status == "In Transit" and not self.actual_start:
			self.db_set("actual_start", now_datetime())
		if new_status == "Returned to Vault" and not self.actual_end:
			self.db_set("actual_end", now_datetime())
		self.db_set("status", new_status)
		frappe.publish_realtime("cit_trip_update", {"trip": self.name, "status": new_status})
		return new_status


@frappe.whitelist()
def dispatch(trip, ignore_blockers=0, override_reason=None):
	doc = frappe.get_doc("CIT Trip", trip)
	doc.check_permission("write")
	return doc.move_to("Dispatched", cint(ignore_blockers), override_reason)


@frappe.whitelist()
def advance(trip, status):
	doc = frappe.get_doc("CIT Trip", trip)
	doc.check_permission("write")
	return doc.move_to(status)


@frappe.whitelist()
def check_dispatch(trip):
	doc = frappe.get_doc("CIT Trip", trip)
	return {"blockers": doc.dispatch_blockers()}


@frappe.whitelist()
def board(trip_date=None):
	"""Control-room board: trips of the day with live position."""
	filters = {"docstatus": 1}
	if trip_date:
		filters["trip_date"] = trip_date
	trips = frappe.get_all(
		"CIT Trip", filters=filters,
		fields=["name", "trip_date", "vehicle", "vault", "status", "reconciliation_status",
		        "total_declared_value", "actual_start", "actual_end"],
		order_by="trip_date desc, name desc", limit_page_length=100)
	for t in trips:
		pos = frappe.get_all(
			"GPS Position Event", filters={"vehicle": t.vehicle},
			fields=["latitude", "longitude", "event_time", "speed_kmh"],
			order_by="event_time desc", limit_page_length=1)
		t["position"] = pos[0] if pos else None
		t["open_stops"] = frappe.db.count("CIT Trip Stop", {"parent": t.name, "stop_status": "Pending"})
	return trips

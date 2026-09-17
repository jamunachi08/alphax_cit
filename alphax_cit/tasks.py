"""Scheduled jobs: expiry ladders, SLA measurement, alerting and retention."""

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, getdate, nowdate

from alphax_cit.cit_utils import expiry_ladder, raise_alert, s_value


def check_document_expiry():
	"""Vehicle and crew documents, escalating at each configured day mark."""
	ladder = expiry_ladder()
	today = getdate()

	for row in frappe.get_all(
		"Vehicle Compliance Document",
		filters={"status": ["!=", "Renewed"]},
		fields=["name", "vehicle", "document_type", "expiry_date"]):
		if not row.expiry_date:
			continue
		days = date_diff(getdate(row.expiry_date), today)
		frappe.db.set_value("Vehicle Compliance Document", row.name, {
			"days_to_expiry": days,
			"status": "Expired" if days < 0 else ("Expiring" if days <= max(ladder) else "Valid"),
		}, update_modified=False)
		if days in ladder or days < 0:
			raise_alert(
				"Document Expiry",
				_("{0} for vehicle {1} expires in {2} days").format(
					row.document_type, row.vehicle, days) if days >= 0
				else _("{0} for vehicle {1} expired {2} days ago").format(
					row.document_type, row.vehicle, abs(days)),
				severity="Critical" if days < 0 else "Warning",
				vehicle=row.vehicle, reference_doctype="Vehicle Compliance Document",
				reference_name=row.name)

	crew_fields = {
		"cit_licence_expiry": _("Driving licence"),
		"cit_security_clearance_expiry": _("Security clearance"),
		"cit_weapon_permit_expiry": _("Weapon permit"),
		"cit_medical_fitness_expiry": _("Medical fitness"),
		"iqama_expiry_date": _("Iqama"),
	}
	for emp in frappe.get_all("Employee", filters={"status": "Active", "cit_is_crew": 1},
	                          fields=["name", "employee_name"] + list(crew_fields)):
		for field, label in crew_fields.items():
			val = emp.get(field)
			if not val:
				continue
			days = date_diff(getdate(val), today)
			if days in ladder or days < 0:
				raise_alert(
					"Document Expiry",
					_("{0} for {1} {2}").format(
						label, emp.employee_name,
						_("expires in {0} days").format(days) if days >= 0
						else _("expired {0} days ago").format(abs(days))),
					severity="Critical" if days < 0 else "Warning",
					employee=emp.name, reference_doctype="Employee", reference_name=emp.name)


def check_maintenance_due():
	for req in frappe.get_all(
		"CIT Maintenance Request",
		filters={"status": ["in", ["Open", "Scheduled"]]},
		fields=["name", "vehicle", "due_date", "due_odometer", "maintenance_type"]):
		if req.due_date and date_diff(getdate(req.due_date), getdate()) <= 7:
			raise_alert("Maintenance Due",
			            _("{0} due for vehicle {1} on {2}").format(
				            req.maintenance_type, req.vehicle, req.due_date),
			            severity="Warning", vehicle=req.vehicle,
			            reference_doctype="CIT Maintenance Request", reference_name=req.name)


def evaluate_sla():
	"""Measure arrival and POD service levels from operational timestamps."""
	trips = frappe.get_all(
		"CIT Trip",
		filters={"docstatus": 1, "trip_date": [">=", add_days(nowdate(), -7)]},
		fields=["name", "company"])
	for t in trips:
		for stop in frappe.get_all(
			"CIT Trip Stop",
			filters={"parent": t.name, "stop_status": "Completed"},
			fields=["name", "cit_job", "planned_arrival", "actual_arrival"]):
			if not (stop.planned_arrival and stop.actual_arrival):
				continue
			job = frappe.db.get_value("CIT Job", stop.cit_job,
			                          ["customer", "service_contract"], as_dict=True)
			if not job or not job.service_contract:
				continue
			targets = frappe.get_all(
				"CIT SLA Target",
				filters={"parent": job.service_contract, "sla_metric": "Arrival Window"},
				fields=["target_minutes", "penalty_type", "penalty_value"])
			if not targets:
				continue
			target = targets[0]
			late = (frappe.utils.time_diff_in_seconds(
				stop.actual_arrival, stop.planned_arrival) / 60.0)
			if late <= cint(target.target_minutes):
				continue
			if frappe.db.exists("CIT SLA Breach", {"cit_trip": t.name, "cit_job": stop.cit_job,
			                                       "sla_metric": "Arrival Window"}):
				continue
			penalty = flt(target.penalty_value) if target.penalty_type == "Fixed" else 0
			frappe.get_doc({
				"doctype": "CIT SLA Breach", "service_contract": job.service_contract,
				"customer": job.customer, "cit_trip": t.name, "cit_job": stop.cit_job,
				"sla_metric": "Arrival Window", "breach_date": nowdate(),
				"target_minutes": target.target_minutes, "actual_minutes": int(late),
				"penalty_amount": penalty, "company": t.company,
			}).insert(ignore_permissions=True)


def detect_operational_alerts():
	from alphax_cit.api.gps import detect_prolonged_halts

	detect_prolonged_halts()


def refresh_contract_status():
	for c in frappe.get_all("CIT Service Contract", filters={"docstatus": 1},
	                        fields=["name", "end_date", "notice_days", "status", "customer"]):
		days = date_diff(getdate(c.end_date), getdate())
		status = "Expired" if days < 0 else (
			"Expiring" if days <= cint(c.notice_days or 90) else "Active")
		if status != c.status:
			frappe.db.set_value("CIT Service Contract", c.name, "status", status)
			if status == "Expiring":
				raise_alert("Document Expiry",
				            _("Contract {0} for {1} expires in {2} days").format(
					            c.name, c.customer, days),
				            severity="Warning", reference_doctype="CIT Service Contract",
				            reference_name=c.name)


def snapshot_fleet_availability():
	today = nowdate()
	for v in frappe.get_all("Vehicle", fields=["name", "cit_availability"]):
		key = f"FAL-{v.name}-{today}"
		if frappe.db.exists("Fleet Availability Log", key):
			continue
		frappe.get_doc({
			"doctype": "Fleet Availability Log", "vehicle": v.name, "log_date": today,
			"availability_status": v.cit_availability or "In Service",
		}).insert(ignore_permissions=True)


def purge_old_positions():
	days = cint(s_value("position_retention_days", 180))
	if not days:
		return
	cutoff = add_days(nowdate(), -days)
	frappe.db.sql("delete from `tabGPS Position Event` where event_time < %s", (cutoff,))

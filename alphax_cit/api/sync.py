"""Offline-first synchronisation endpoint for the crew mobile application.

Contract: every event carries a client-generated `client_event_id`. Replaying an
event that was already applied returns `duplicate` without side effects, so a
partially completed sync can always be retried safely.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

HANDLERS = {}


def handler(event_type):
	def wrap(fn):
		HANDLERS[event_type] = fn
		return fn
	return wrap


@frappe.whitelist()
def push(events, device_id=None):
	"""events: JSON list of {client_event_id, seq, event_type, payload}"""
	if isinstance(events, str):
		events = json.loads(events)
	results = []
	for ev in sorted(events, key=lambda e: cint(e.get("seq"))):
		results.append(_apply_one(ev, device_id or ev.get("device_id")))
	if device_id:
		_touch_device(device_id)
	return {"results": results, "server_time": str(now_datetime())}


def _touch_device(device_id):
	if frappe.db.exists("CIT Device", device_id):
		frappe.db.set_value("CIT Device", device_id, "last_sync", now_datetime())


def _apply_one(ev, device_id):
	cid = ev.get("client_event_id")
	if not cid:
		return {"client_event_id": None, "status": "Failed", "error": _("Missing client_event_id")}

	existing = frappe.db.get_value(
		"CIT Sync Event", {"client_event_id": cid},
		["name", "status", "result_doctype", "result_name"], as_dict=True)
	if existing:
		return {"client_event_id": cid, "status": "Duplicate",
		        "result_doctype": existing.result_doctype, "result_name": existing.result_name}

	log = frappe.get_doc({
		"doctype": "CIT Sync Event",
		"client_event_id": cid,
		"device_id": device_id or ev.get("device_id") or "unknown",
		"employee": ev.get("employee"),
		"sequence_no": cint(ev.get("seq")),
		"event_type": ev.get("event_type"),
		"received_on": now_datetime(),
		"payload": json.dumps(ev.get("payload") or {}),
		"status": "Received",
	})
	log.flags.ignore_permissions = True
	log.insert(ignore_permissions=True)
	frappe.db.commit()

	fn = HANDLERS.get(ev.get("event_type"))
	if not fn:
		log.db_set({"status": "Quarantined", "error_message": _("Unknown event type")})
		return {"client_event_id": cid, "status": "Quarantined"}

	savepoint = "sync_event"
	frappe.db.savepoint(savepoint)
	try:
		dt, dn = fn(ev.get("payload") or {}, log)
		log.db_set({"status": "Applied", "applied_on": now_datetime(),
		            "result_doctype": dt, "result_name": dn})
		return {"client_event_id": cid, "status": "Applied", "result_doctype": dt, "result_name": dn}
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		log.db_set({"status": "Quarantined", "error_message": frappe.get_traceback()[-800:]})
		frappe.log_error(frappe.get_traceback(), f"CIT sync {cid}")
		return {"client_event_id": cid, "status": "Quarantined"}


# --------------------------------------------------------------- handlers
@handler("trip_start")
def _trip_start(payload, log):
	trip = frappe.get_doc("CIT Trip", payload["trip"])
	if trip.status == "Dispatched":
		trip.move_to("In Transit")
	if payload.get("odometer"):
		trip.db_set("odometer_out", payload["odometer"])
	return "CIT Trip", trip.name


@handler("stop_arrive")
def _stop_arrive(payload, log):
	rows = frappe.get_all("CIT Trip Stop",
	                      filters={"parent": payload["trip"], "cit_job": payload["job"]},
	                      fields=["name"])
	for r in rows:
		frappe.db.set_value("CIT Trip Stop", r.name, {
			"actual_arrival": payload.get("timestamp") or now_datetime(),
			"stop_status": "Arrived",
		})
	return "CIT Trip", payload["trip"]


@handler("stop_complete")
def _stop_complete(payload, log):
	rows = frappe.get_all("CIT Trip Stop",
	                      filters={"parent": payload["trip"], "cit_job": payload["job"]},
	                      fields=["name", "actual_arrival"])
	for r in rows:
		vals = {"actual_departure": payload.get("timestamp") or now_datetime(),
		        "stop_status": payload.get("status") or "Completed"}
		if r.actual_arrival and vals["actual_departure"]:
			from frappe.utils import time_diff_in_seconds
			vals["dwell_minutes"] = time_diff_in_seconds(
				vals["actual_departure"], r.actual_arrival) / 60.0
		frappe.db.set_value("CIT Trip Stop", r.name, vals)
	return "CIT Trip", payload["trip"]


@handler("pod_capture")
def _pod_capture(payload, log):
	doc = frappe.get_doc({
		"doctype": "CIT POD",
		"cit_trip": payload["trip"],
		"cit_job": payload["job"],
		"customer_site": payload.get("customer_site"),
		"pod_type": payload.get("pod_type") or "Collection",
		"pod_datetime": payload.get("timestamp") or now_datetime(),
		"signatory_name": payload.get("signatory_name"),
		"signatory_id": payload.get("signatory_id"),
		"signature": payload.get("signature"),
		"otp_verified": cint(payload.get("otp_verified")),
		"latitude": payload.get("latitude"),
		"longitude": payload.get("longitude"),
		"captured_by": payload.get("employee"),
		"device_id": log.device_id,
		"sync_event": log.name,
		"company": payload.get("company") or frappe.defaults.get_user_default("Company"),
		"bags": payload.get("bags") or [],
	})
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	doc.submit()
	return "CIT POD", doc.name


@handler("incident")
def _incident(payload, log):
	doc = frappe.get_doc({
		"doctype": "CIT Incident",
		"incident_datetime": payload.get("timestamp") or now_datetime(),
		"incident_category": payload.get("category") or "Other",
		"severity": payload.get("severity") or "Medium",
		"cit_trip": payload.get("trip"),
		"cit_job": payload.get("job"),
		"employee": payload.get("employee"),
		"description": payload.get("description") or "",
		"company": payload.get("company") or frappe.defaults.get_user_default("Company"),
	})
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	return "CIT Incident", doc.name


@handler("panic")
def _panic(payload, log):
	from alphax_cit.cit_utils import raise_alert
	name = raise_alert(
		"Panic", _("Panic raised by {0} on trip {1}").format(
			payload.get("employee"), payload.get("trip")),
		severity="Critical", vehicle=payload.get("vehicle"), cit_trip=payload.get("trip"),
		employee=payload.get("employee"))
	return "CIT Alert", name


@handler("checklist")
def _checklist(payload, log):
	for row in payload.get("items") or []:
		rows = frappe.get_all("CIT Trip Checklist Item",
		                      filters={"parent": payload["trip"], "item_label": row.get("label")},
		                      fields=["name"])
		for r in rows:
			frappe.db.set_value("CIT Trip Checklist Item", r.name,
			                    {"checked": cint(row.get("checked")), "remarks": row.get("remarks")})
	return "CIT Trip", payload["trip"]


@handler("trip_complete")
def _trip_complete(payload, log):
	trip = frappe.get_doc("CIT Trip", payload["trip"])
	if payload.get("odometer"):
		trip.db_set("odometer_in", payload["odometer"])
	if trip.status == "In Transit":
		trip.move_to("Returned to Vault")
	return "CIT Trip", trip.name


# --------------------------------------------------------------- pull
@frappe.whitelist()
def pull(employee, since=None):
	"""Everything a crew member needs to work offline for the day."""
	filters = {"docstatus": 1, "status": ["in", ["Planned", "Dispatched", "In Transit"]]}
	trips = frappe.db.sql(
		"""
		select distinct t.name from `tabCIT Trip` t
		inner join `tabCIT Trip Crew` c on c.parent = t.name
		where c.employee = %s and t.docstatus = 1
		  and t.status in ('Planned','Dispatched','In Transit')
		""",
		(employee,), as_dict=True)
	out = []
	for t in trips:
		doc = frappe.get_doc("CIT Trip", t.name)
		out.append({
			"trip": doc.name, "status": doc.status, "vehicle": doc.vehicle,
			"trip_date": str(doc.trip_date), "vault": doc.vault,
			"checklist": [{"label": r.item_label, "mandatory": r.mandatory,
			               "checked": r.checked} for r in doc.checklist],
			"stops": [{
				"seq": s.idx_seq, "job": s.cit_job, "site": s.customer_site,
				"stop_type": s.stop_type, "planned_arrival": str(s.planned_arrival or ""),
				"declared_value": s.declared_value, "bags": s.bags_count,
				"status": s.stop_status,
				"site_detail": _site_detail(s.customer_site),
			} for s in doc.stops],
		})
	return {"employee": employee, "trips": out, "server_time": str(now_datetime())}


def _site_detail(site):
	if not site:
		return {}
	d = frappe.db.get_value(
		"Customer Site", site,
		["site_name", "latitude", "longitude", "access_protocol", "special_instructions",
		 "service_window_from", "service_window_to"], as_dict=True) or {}
	d["contacts"] = frappe.get_all(
		"CIT Site Contact", filters={"parent": site},
		fields=["contact_name", "designation", "id_number", "mobile", "authorised_to_receive"])
	return d

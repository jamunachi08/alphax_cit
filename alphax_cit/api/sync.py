"""Offline-first synchronisation engine for the crew mobile application.

NOT A PUBLIC ENDPOINT. Nothing here is whitelisted. The only way in is
`alphax_cit.api.mobile`, which authorises the handset against the CIT Device
register first. Whitelisting `push` or `pull` again re-opens the bypass: a
plain API session could then write custody records from an unregistered
device, which is precisely the hole the device register exists to close.

Contract: every event carries a client-generated `client_event_id`. Replaying
an event that was already *applied* returns `Duplicate` without side effects.
Replaying one that was quarantined or left half-finished re-runs it on the
same log row, so Retry in the crew's outbox actually retries.
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


def push(events, device_id=None, employee=None):
	"""events: JSON list of {client_event_id, seq, event_type, payload}"""
	if isinstance(events, str):
		events = json.loads(events)
	results = []
	for ev in sorted(events, key=lambda e: cint(e.get("seq"))):
		results.append(_apply_one(ev, device_id or ev.get("device_id"),
		                          employee or ev.get("employee")))
	if device_id:
		_touch_device(device_id)
	return {"results": results, "server_time": str(now_datetime())}


def _touch_device(device_id):
	if frappe.db.exists("CIT Device", device_id):
		frappe.db.set_value("CIT Device", device_id, "last_sync", now_datetime())


def assert_own_trip(trip, employee):
	"""A crew member may only act on a trip they are rostered to.

	Dispatchers and control room staff are exempt because they legitimately
	correct other people's work from the desk. Everyone else is checked against
	`CIT Trip Crew`, so a valid session plus a guessed trip name is not enough
	to write a POD or move a trip.
	"""
	if not trip:
		return
	roles = set(frappe.get_roles())
	if roles.intersection({"CIT Dispatcher", "CIT Control Room", "CIT Manager", "System Manager"}):
		return
	if not employee:
		frappe.throw(_("No employee is attached to this session."), frappe.PermissionError)
	rostered = frappe.db.exists("CIT Trip Crew", {"parent": trip, "employee": employee})
	if not rostered:
		frappe.throw(
			_("You are not assigned to trip {0}.").format(trip), frappe.PermissionError)


def _trip_of(payload):
	if payload.get("trip"):
		return payload["trip"]
	if payload.get("job"):
		return frappe.db.get_value("CIT Job", payload["job"], "cit_trip")
	return None


def _run(fn, ev, log):
	"""Execute one handler inside a savepoint and record the outcome."""
	cid = log.client_event_id
	savepoint = "sync_event"
	frappe.db.savepoint(savepoint)
	try:
		dt, dn = fn(ev.get("payload") or {}, log)
		log.db_set({"status": "Applied", "applied_on": now_datetime(),
		            "error_message": None, "result_doctype": dt, "result_name": dn})
		return {"client_event_id": cid, "status": "Applied", "result_doctype": dt, "result_name": dn}
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		log.db_set({"status": "Quarantined", "error_message": frappe.get_traceback()[-800:]})
		frappe.log_error(frappe.get_traceback(), f"CIT sync {cid}")
		return {"client_event_id": cid, "status": "Quarantined",
		        "error": _("The server rejected this record. It is held for review.")}


def _apply_one(ev, device_id, employee=None):
	cid = ev.get("client_event_id")
	if not cid:
		return {"client_event_id": None, "status": "Failed", "error": _("Missing client_event_id")}

	fn = HANDLERS.get(ev.get("event_type"))

	try:
		assert_own_trip(_trip_of(ev.get("payload") or {}), employee)
	except frappe.PermissionError as e:
		# An attempt to write against someone else's trip is a security event,
		# not a validation error. It is recorded even though nothing is applied.
		frappe.log_error(
			"Device {0} / employee {1} attempted {2} on trip {3}: {4}".format(
				device_id, employee, ev.get("event_type"),
				_trip_of(ev.get("payload") or {}), e),
			"CIT sync authorisation")
		return {"client_event_id": cid, "status": "Rejected", "error": str(e)}

	existing = frappe.db.get_value(
		"CIT Sync Event", {"client_event_id": cid},
		["name", "status", "result_doctype", "result_name"], as_dict=True)

	if existing:
		# Only an event that actually reached the database is a duplicate. One
		# that was quarantined, or that died between the log row and the
		# handler, is re-attempted here — otherwise the handset would delete
		# work from its outbox that the server never applied.
		if existing.status == "Applied":
			return {"client_event_id": cid, "status": "Duplicate",
			        "result_doctype": existing.result_doctype, "result_name": existing.result_name}

		if not fn:
			return {"client_event_id": cid, "status": "Quarantined",
			        "error": _("Unknown event type")}

		log = frappe.get_doc("CIT Sync Event", existing.name)
		log.db_set({"payload": json.dumps(ev.get("payload") or {}),
		            "status": "Received", "received_on": now_datetime(),
		            "retry_count": cint(log.get("retry_count")) + 1})
		return _run(fn, ev, log)

	log = frappe.get_doc({
		"doctype": "CIT Sync Event",
		"client_event_id": cid,
		"device_id": device_id or ev.get("device_id") or "unknown",
		"employee": employee or ev.get("employee"),
		"sequence_no": cint(ev.get("seq")),
		"event_type": ev.get("event_type"),
		"received_on": now_datetime(),
		"payload": json.dumps(ev.get("payload") or {}),
		"status": "Received",
	})
	log.flags.ignore_permissions = True
	log.insert(ignore_permissions=True)
	frappe.db.commit()

	if not fn:
		log.db_set({"status": "Quarantined", "error_message": _("Unknown event type")})
		return {"client_event_id": cid, "status": "Quarantined",
		        "error": _("Unknown event type")}

	return _run(fn, ev, log)


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
		# Seal and damage photographs are part of the proof, not decoration.
		# Losing them here would leave a POD that cannot support a claim.
		"photos": [
			{"photo": ph.get("photo") if isinstance(ph, dict) else ph,
			 "caption": (ph.get("caption") if isinstance(ph, dict) else "") or ""}
			for ph in (payload.get("photos") or [])
			if (ph.get("photo") if isinstance(ph, dict) else ph)
		],
		"remarks": payload.get("remarks") or "",
	})
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	doc.submit()
	_claim_files(doc, payload)
	return "CIT POD", doc.name


def _claim_files(doc, payload):
	"""Bind the uploaded signature and photos to the POD.

	They are uploaded before the POD exists so that a failed image upload does
	not cost the crew the whole capture. That leaves them unattached, which
	means Frappe's orphan-file cleanup would eventually delete evidence. This
	re-parents them the moment the POD is saved.
	"""
	urls = [payload.get("signature")]
	for ph in payload.get("photos") or []:
		urls.append(ph.get("photo") if isinstance(ph, dict) else ph)
	for url in [u for u in urls if u]:
		for name in frappe.get_all("File", filters={"file_url": url}, pluck="name"):
			frappe.db.set_value("File", name, {
				"attached_to_doctype": "CIT POD",
				"attached_to_name": doc.name,
				"attached_to_field": "signature" if url == payload.get("signature") else None,
			})


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

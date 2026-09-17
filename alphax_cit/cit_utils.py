"""Shared helpers for AlphaX CIT. No server scripts: all logic is versioned here."""

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, getdate, now_datetime, time_diff_in_hours


def settings():
	return frappe.get_cached_doc("AlphaX CIT Settings")


def s_flag(fieldname, default=0):
	try:
		return cint(settings().get(fieldname))
	except Exception:
		return cint(default)


def s_value(fieldname, default=None):
	try:
		val = settings().get(fieldname)
		return val if val not in (None, "") else default
	except Exception:
		return default


def content_hash(payload: dict, previous_hash: str = "") -> str:
	"""Deterministic SHA-256 over the canonical payload plus the previous link."""
	canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
	return hashlib.sha256((previous_hash + "|" + canonical).encode("utf-8")).hexdigest()


def expiry_ladder():
	raw = s_value("expiry_alert_days", "90,60,30,7")
	out = []
	for part in str(raw).split(","):
		part = part.strip()
		if part.isdigit():
			out.append(int(part))
	return sorted(out, reverse=True) or [90, 60, 30, 7]


def haversine_metres(lat1, lon1, lat2, lon2):
	import math

	r = 6371000.0
	p1, p2 = math.radians(flt(lat1)), math.radians(flt(lat2))
	dp = math.radians(flt(lat2) - flt(lat1))
	dl = math.radians(flt(lon2) - flt(lon1))
	a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
	return 2 * r * math.asin(math.sqrt(a))


def point_in_polygon(lat, lng, polygon):
	"""Ray casting. polygon = [[lat, lng], ...]"""
	inside = False
	n = len(polygon)
	if n < 3:
		return False
	j = n - 1
	for i in range(n):
		yi, xi = flt(polygon[i][0]), flt(polygon[i][1])
		yj, xj = flt(polygon[j][0]), flt(polygon[j][1])
		if ((yi > lat) != (yj > lat)) and (lng < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi):
			inside = not inside
		j = i
	return inside


def raise_alert(alert_type, message, severity="Warning", **kwargs):
	"""Create a CIT Alert. Deduplicates an identical open alert within the hour."""
	existing = frappe.db.exists(
		"CIT Alert",
		{
			"alert_type": alert_type,
			"message": message,
			"status": "Open",
			"alert_time": [">", frappe.utils.add_to_date(now_datetime(), hours=-1)],
		},
	)
	if existing:
		return existing
	doc = frappe.get_doc(
		dict(doctype="CIT Alert", alert_type=alert_type, severity=severity,
		     alert_time=now_datetime(), message=message, status="Open", **kwargs)
	)
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	return doc.name


def employee_document_status(employee):
	"""Return (ok, [reasons]) for crew compliance, driven by Employee custom fields."""
	reasons = []
	row = frappe.db.get_value(
		"Employee",
		employee,
		[
			"employee_name", "iqama_expiry_date", "cit_licence_expiry",
			"cit_security_clearance_expiry", "cit_weapon_permit_expiry",
			"cit_medical_fitness_expiry", "status",
		],
		as_dict=True,
	)
	if not row:
		return False, [_("Employee record not found")]
	if row.status != "Active":
		reasons.append(_("Employee is not active"))
	today = getdate()
	checks = {
		"iqama_expiry_date": _("Iqama"),
		"cit_licence_expiry": _("Driving licence"),
		"cit_security_clearance_expiry": _("Security clearance"),
		"cit_weapon_permit_expiry": _("Weapon permit"),
		"cit_medical_fitness_expiry": _("Medical fitness"),
	}
	for field, label in checks.items():
		val = row.get(field)
		if val and getdate(val) < today:
			reasons.append(_("{0} expired on {1}").format(label, val))
	return (not reasons), reasons


def vehicle_document_status(vehicle):
	reasons = []
	today = getdate()
	rows = frappe.get_all(
		"Vehicle Compliance Document",
		filters={"vehicle": vehicle},
		fields=["document_type", "expiry_date", "status"],
	)
	for r in rows:
		if r.expiry_date and getdate(r.expiry_date) < today and r.status != "Renewed":
			reasons.append(_("{0} expired on {1}").format(r.document_type, r.expiry_date))
	return (not reasons), reasons


def last_trip_end(employee, before_dt):
	row = frappe.db.sql(
		"""
		select max(t.actual_end) as ended
		from `tabCIT Trip` t
		inner join `tabCIT Trip Crew` c on c.parent = t.name
		where c.employee = %s and t.docstatus = 1 and t.actual_end is not null
		  and t.actual_end <= %s
		""",
		(employee, before_dt),
		as_dict=True,
	)
	return row[0].ended if row and row[0].ended else None


def rest_hours_ok(employee, planned_start):
	minimum = flt(s_value("minimum_rest_hours", 8))
	if not minimum or not planned_start:
		return True, 0
	ended = last_trip_end(employee, planned_start)
	if not ended:
		return True, 0
	gap = time_diff_in_hours(get_datetime(planned_start), get_datetime(ended))
	return (gap >= minimum), gap

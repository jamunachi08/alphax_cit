"""GPS ingestion behind a provider adapter, plus geofence evaluation.

Changing telematics vendor is an adapter change, not a redesign.
"""

import json

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, flt, get_datetime, now_datetime

from alphax_cit.cit_utils import (haversine_metres, point_in_polygon, raise_alert,
                                  s_value)


# ------------------------------------------------------------------ adapters
class BaseAdapter:
	def __init__(self, provider):
		self.provider = provider

	def fetch(self):
		"""Return [{vehicle, event_time, latitude, longitude, speed_kmh, heading, ignition}]"""
		raise NotImplementedError

	def parse_webhook(self, body):
		raise NotImplementedError


class GenericRestAdapter(BaseAdapter):
	"""Expects a JSON array of positions from `base_url`."""

	def fetch(self):
		import requests

		if not self.provider.base_url:
			return []
		headers = {}
		key = self.provider.get_password("api_key", raise_exception=False)
		if key:
			headers["Authorization"] = f"Bearer {key}"
		resp = requests.get(self.provider.base_url, headers=headers, timeout=20)
		resp.raise_for_status()
		return [self._normalise(r) for r in (resp.json() or [])]

	def parse_webhook(self, body):
		data = body if isinstance(body, list) else [body]
		return [self._normalise(r) for r in data]

	def _normalise(self, r):
		return {
			"vehicle": r.get("vehicle") or r.get("plate") or r.get("device_name"),
			"event_time": r.get("timestamp") or r.get("time") or now_datetime(),
			"latitude": flt(r.get("lat") or r.get("latitude")),
			"longitude": flt(r.get("lng") or r.get("lon") or r.get("longitude")),
			"speed_kmh": flt(r.get("speed")),
			"heading": flt(r.get("heading") or r.get("course")),
			"ignition": cint(r.get("ignition")),
			"raw": r,
		}


ADAPTERS = {"generic_rest": GenericRestAdapter, "webhook": GenericRestAdapter}


def get_adapter(provider_doc):
	cls = ADAPTERS.get(provider_doc.provider_key, GenericRestAdapter)
	return cls(provider_doc)


# ------------------------------------------------------------------ ingestion
def poll_providers():
	for name in frappe.get_all("GPS Provider", filters={"enabled": 1}, pluck="name"):
		doc = frappe.get_doc("GPS Provider", name)
		try:
			positions = get_adapter(doc).fetch()
			ingest(positions, doc.name)
			doc.db_set({"last_sync": now_datetime(), "last_error": None})
		except Exception:
			doc.db_set("last_error", frappe.get_traceback()[-500:])
			frappe.log_error(frappe.get_traceback(), f"GPS poll {name}")


@frappe.whitelist(allow_guest=True)
def webhook(provider=None):
	"""Inbound webhook. Shared secret is checked before anything is written."""
	doc = frappe.get_doc("GPS Provider", provider)
	secret = doc.get_password("webhook_secret", raise_exception=False)
	if secret:
		supplied = frappe.get_request_header("X-CIT-Secret")
		if supplied != secret:
			frappe.throw(_("Invalid webhook secret"), frappe.PermissionError)
	body = frappe.request.get_json(silent=True) or {}
	positions = get_adapter(doc).parse_webhook(body)
	return {"ingested": ingest(positions, doc.name)}


def ingest(positions, provider):
	count = 0
	for p in positions or []:
		vehicle = _resolve_vehicle(p.get("vehicle"))
		if not vehicle or not p.get("latitude"):
			continue
		trip = active_trip(vehicle)
		doc = frappe.get_doc({
			"doctype": "GPS Position Event", "vehicle": vehicle,
			"event_time": get_datetime(p.get("event_time")),
			"latitude": p["latitude"], "longitude": p["longitude"],
			"speed_kmh": p.get("speed_kmh"), "heading": p.get("heading"),
			"ignition": cint(p.get("ignition")), "gps_provider": provider,
			"cit_trip": trip, "raw_payload": json.dumps(p.get("raw") or {}, default=str),
		})
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
		evaluate_position(doc)
		count += 1
	frappe.db.commit()
	return count


def _resolve_vehicle(key):
	if not key:
		return None
	if frappe.db.exists("Vehicle", key):
		return key
	return frappe.db.get_value("Vehicle", {"cit_tracker_id": key}, "name")


def active_trip(vehicle):
	return frappe.db.get_value(
		"CIT Trip",
		{"vehicle": vehicle, "docstatus": 1, "status": ["in", ["Dispatched", "In Transit"]]},
		"name")


# ------------------------------------------------------------------ geofence
def evaluate_position(pos):
	inside_now = set()
	for gf in frappe.get_all(
		"Geofence", filters={"disabled": 0},
		fields=["name", "shape", "latitude", "longitude", "radius_metres", "polygon_json",
		        "alert_on_entry", "alert_on_exit", "prohibited", "customer_site", "geofence_type"]):
		if _inside(pos, gf):
			inside_now.add(gf.name)
			if not _last_state(pos.vehicle, gf.name):
				_write_event(pos, gf, "Entry")
		else:
			if _last_state(pos.vehicle, gf.name):
				_write_event(pos, gf, "Exit")
	_speed_check(pos)
	return inside_now


def _inside(pos, gf):
	if gf.shape == "Polygon" and gf.polygon_json:
		try:
			poly = json.loads(gf.polygon_json)
		except ValueError:
			return False
		return point_in_polygon(pos.latitude, pos.longitude, poly)
	if not gf.latitude:
		return False
	radius = flt(gf.radius_metres) or flt(s_value("default_geofence_radius", 150))
	return haversine_metres(pos.latitude, pos.longitude, gf.latitude, gf.longitude) <= radius


def _last_state(vehicle, geofence):
	last = frappe.get_all(
		"Geofence Event", filters={"vehicle": vehicle, "geofence": geofence},
		fields=["event_type"], order_by="event_time desc", limit_page_length=1)
	return bool(last and last[0].event_type == "Entry")


def _write_event(pos, gf, event_type):
	ev = frappe.get_doc({
		"doctype": "Geofence Event", "vehicle": pos.vehicle, "geofence": gf.name,
		"event_type": event_type, "event_time": pos.event_time, "cit_trip": pos.cit_trip,
	})
	ev.flags.ignore_permissions = True
	ev.insert(ignore_permissions=True)

	if gf.prohibited and event_type == "Entry":
		raise_alert("Geofence Breach",
		            _("Vehicle {0} entered prohibited zone {1}").format(pos.vehicle, gf.name),
		            severity="Critical", vehicle=pos.vehicle, cit_trip=pos.cit_trip)
	if gf.customer_site and pos.cit_trip:
		_stamp_stop(pos, gf, event_type)
	if (event_type == "Entry" and gf.alert_on_entry) or (event_type == "Exit" and gf.alert_on_exit):
		raise_alert("Geofence Breach",
		            _("Vehicle {0} {1} {2}").format(pos.vehicle, event_type.lower(), gf.name),
		            severity="Info", vehicle=pos.vehicle, cit_trip=pos.cit_trip)


def _stamp_stop(pos, gf, event_type):
	"""Arrival and departure are measured, not typed in by the crew."""
	rows = frappe.get_all("CIT Trip Stop",
	                      filters={"parent": pos.cit_trip, "customer_site": gf.customer_site},
	                      fields=["name", "actual_arrival", "stop_status"])
	for r in rows:
		if event_type == "Entry" and not r.actual_arrival:
			frappe.db.set_value("CIT Trip Stop", r.name,
			                    {"actual_arrival": pos.event_time, "stop_status": "Arrived"})
		elif event_type == "Exit" and r.actual_arrival:
			from frappe.utils import time_diff_in_seconds
			dwell = time_diff_in_seconds(pos.event_time, r.actual_arrival) / 60.0
			frappe.db.set_value("CIT Trip Stop", r.name,
			                    {"actual_departure": pos.event_time, "dwell_minutes": dwell})


def _speed_check(pos):
	limit = flt(s_value("speeding_threshold_kmh", 120))
	if limit and flt(pos.speed_kmh) > limit:
		raise_alert("Speeding",
		            _("Vehicle {0} recorded {1} km/h").format(pos.vehicle, int(flt(pos.speed_kmh))),
		            severity="Warning", vehicle=pos.vehicle, cit_trip=pos.cit_trip)


def detect_prolonged_halts():
	minutes = cint(s_value("prolonged_halt_minutes", 15))
	if not minutes:
		return
	cutoff = add_to_date(now_datetime(), minutes=-minutes)
	trips = frappe.get_all("CIT Trip", filters={"docstatus": 1, "status": "In Transit"},
	                       fields=["name", "vehicle"])
	for t in trips:
		last = frappe.get_all("GPS Position Event", filters={"vehicle": t.vehicle},
		                      fields=["event_time", "speed_kmh", "latitude", "longitude"],
		                      order_by="event_time desc", limit_page_length=1)
		if not last:
			continue
		if get_datetime(last[0].event_time) < cutoff:
			raise_alert("Signal Lost",
			            _("No position from vehicle {0} for more than {1} minutes").format(
				            t.vehicle, minutes),
			            severity="Critical", vehicle=t.vehicle, cit_trip=t.name)
			continue
		recent = frappe.get_all(
			"GPS Position Event",
			filters={"vehicle": t.vehicle, "event_time": [">=", cutoff]},
			fields=["speed_kmh"])
		if recent and all(flt(r.speed_kmh) < 2 for r in recent):
			inside_site = frappe.db.exists(
				"Geofence Event",
				{"vehicle": t.vehicle, "event_type": "Entry",
				 "event_time": [">=", cutoff]})
			if not inside_site:
				raise_alert("Prolonged Halt",
				            _("Vehicle {0} stationary for more than {1} minutes off site").format(
					            t.vehicle, minutes),
				            severity="Critical", vehicle=t.vehicle, cit_trip=t.name)

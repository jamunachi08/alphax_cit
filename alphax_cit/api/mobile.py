"""Mobile edge for the crew application.

Everything the crew app touches goes through here rather than calling
`alphax_cit.api.sync` directly, for one reason: Frappe's two-factor
authentication does not apply to API logins, so a leaked password or a stolen
handset is a complete bypass of the second factor. `require_device()` turns the
`CIT Device` register into a second factor that *does* apply to API sessions —
an unknown or deactivated handset is refused before any business logic runs,
and dispatch can revoke a lost device from the desk in one click.

Contract with the client (see public/crew/api.js):
    header  X-CIT-Device: <device_id>
    login   /api/method/login                      (standard Frappe)
    then    /api/method/alphax_cit.api.mobile.bootstrap
    read    .../mobile.pull
    write   .../mobile.push          -> alphax_cit.api.sync.push
    files   .../mobile.upload_photo
"""

import base64
import json

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from alphax_cit.api import sync as sync_api
from alphax_cit.cit_utils import s_flag, s_value

CREW_ROLES = ("CIT Crew", "CIT Dispatcher", "CIT Control Room", "CIT Manager")
MAX_UPLOAD_BYTES = 6 * 1024 * 1024


# --------------------------------------------------------------- guards
def _device_id():
    return (frappe.get_request_header("X-CIT-Device") or frappe.form_dict.get("device_id") or "").strip()


def require_device(register=False):
    """Resolve and authorise the calling handset. Returns the CIT Device name.

    A device that has never been seen is created *inactive* unless
    `AlphaX CIT Settings.auto_enrol_devices` is ticked, so the default posture
    is that a new handset cannot post anything until a human enables it.
    """
    if not s_flag("enable_mobile_api", 1):
        frappe.throw(_("The mobile API is disabled for this site."), frappe.PermissionError)

    device_id = _device_id()
    if not device_id:
        frappe.throw(_("Missing X-CIT-Device header."), frappe.PermissionError)

    row = frappe.db.get_value(
        "CIT Device", {"device_id": device_id}, ["name", "active", "employee"], as_dict=True)

    if not row:
        if not register:
            frappe.throw(_("This device is not registered. Contact the control room."),
                         frappe.PermissionError)
        active = cint(s_flag("auto_enrol_devices", 0))
        doc = frappe.get_doc({
            "doctype": "CIT Device",
            "device_id": device_id,
            "employee": _employee_for(frappe.session.user, quiet=True),
            "device_label": (frappe.form_dict.get("label") or "")[:140],
            "platform": frappe.form_dict.get("platform") or "Other",
            "app_version": frappe.form_dict.get("app_version") or "",
            "active": active,
        })
        doc.flags.ignore_permissions = True
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        if not active:
            _notify_enrolment(doc)
            frappe.throw(
                _("This device has been submitted for approval. The control room must enable it."),
                frappe.PermissionError)
        return doc.name

    if not cint(row.active):
        frappe.throw(_("This device has been deactivated. Contact the control room."),
                     frappe.PermissionError)

    # A handset is bound to one employee. Re-use by another user is an
    # incident, not a convenience — log it and refuse.
    emp = _employee_for(frappe.session.user, quiet=True)
    if row.employee and emp and row.employee != emp:
        frappe.log_error(
            "Device {0} is registered to {1} but was used by {2} ({3})".format(
                device_id, row.employee, emp, frappe.session.user),
            "CIT device binding")
        frappe.throw(_("This device is registered to another crew member."), frappe.PermissionError)

    return row.name


def _notify_enrolment(doc):
    try:
        recipients = [
            u.parent for u in frappe.get_all(
                "Has Role", filters={"role": "CIT Dispatcher", "parenttype": "User"},
                fields=["parent"])
        ]
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=_("New CIT device awaiting approval"),
                message=_("Device {0} was enrolled by {1} and is waiting to be activated.").format(
                    doc.device_id, frappe.session.user),
                reference_doctype="CIT Device", reference_name=doc.name)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "CIT device enrolment notice")


def _employee_for(user, quiet=False):
    emp = frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "name")
    if not emp and not quiet:
        frappe.throw(_("No active Employee record is linked to {0}.").format(user))
    return emp


def _touch(device_name, **extra):
    vals = {"last_sync": now_datetime()}
    vals.update({k: v for k, v in extra.items() if v})
    frappe.db.set_value("CIT Device", device_name, vals)


# ------------------------------------------------------------ endpoints
@frappe.whitelist()
def bootstrap(device_id=None, platform=None, app_version=None, label=None):
    """First call after login. Enrols or authorises the handset, returns identity."""
    device = require_device(register=True)
    employee = _employee_for(frappe.session.user)

    roles = set(frappe.get_roles())
    if not roles.intersection(CREW_ROLES):
        frappe.throw(_("Your user does not have a CIT crew role."), frappe.PermissionError)

    _touch(device, app_version=app_version, platform=platform, employee=employee)

    return {
        "user": frappe.session.user,
        "employee": employee,
        "employee_name": frappe.db.get_value("Employee", employee, "employee_name"),
        "company": s_value("default_company") or frappe.defaults.get_user_default("Company"),
        "device": device,
        "roles": sorted(roles.intersection(CREW_ROLES)),
        "server_time": str(now_datetime()),
        "min_app_version": s_value("minimum_app_version", "0.0.0"),
    }


@frappe.whitelist()
def pull(employee=None, since=None):
    """Trips for the signed-in crew member. The employee argument is ignored
    unless the caller is a dispatcher: a driver may only pull their own work."""
    device = require_device()
    me = _employee_for(frappe.session.user)
    if employee and employee != me and "CIT Dispatcher" not in frappe.get_roles():
        frappe.throw(_("You may only download your own trips."), frappe.PermissionError)
    _touch(device)
    return sync_api.pull(employee if (employee and "CIT Dispatcher" in frappe.get_roles()) else me,
                         since=since)


@frappe.whitelist()
def push(events, device_id=None):
    """Hand the event batch to the existing sync engine once the device passes."""
    device = require_device()

    if isinstance(events, str):
        events = json.loads(events)
    limit = cint(s_value("mobile_max_events_per_push", 200)) or 200
    if len(events) > limit:
        frappe.throw(_("Too many events in one push (limit {0}).").format(limit))

    me = _employee_for(frappe.session.user)
    for ev in events:
        # The server decides who the actor is. A client-supplied employee is
        # advisory only; it never widens what the session may write.
        (ev.setdefault("payload", {}))["employee"] = me
        ev["employee"] = me

    result = sync_api.push(
        events,
        device_id=frappe.db.get_value("CIT Device", device, "device_id"),
        employee=me)
    _touch(device)
    return result


@frappe.whitelist()
def upload_photo(filename, data, is_private=1, attached_to_doctype=None, attached_to_name=None):
    """Store a base64 data URL as a File and return its URL.

    POD photos and signatures are uploaded before the event that references
    them, so a failed upload never costs the crew the whole capture.
    """
    require_device()

    if "," in data and data.strip().startswith("data:"):
        data = data.split(",", 1)[1]
    try:
        content = base64.b64decode(data)
    except Exception:
        frappe.throw(_("Attachment is not valid base64."))

    if len(content) > MAX_UPLOAD_BYTES:
        frappe.throw(_("Attachment is larger than the {0} MB limit.").format(
            MAX_UPLOAD_BYTES // (1024 * 1024)))

    doc = frappe.get_doc({
        "doctype": "File",
        "file_name": (filename or "cit-upload")[:140],
        "is_private": cint(is_private),
        "content": content,
        "attached_to_doctype": attached_to_doctype,
        "attached_to_name": attached_to_name,
    })
    doc.flags.ignore_permissions = True
    doc.save(ignore_permissions=True)
    return {"file_url": doc.file_url, "name": doc.name}


@frappe.whitelist()
def heartbeat(latitude=None, longitude=None, battery=None, app_version=None):
    """Optional position beacon from the handset, for vehicles with no tracker
    or when the tracker has dropped. Written through the same GPS pipeline as
    every other provider, so geofencing and dwell measurement behave identically."""
    device = require_device()
    _touch(device, app_version=app_version)

    if latitude in (None, "") or longitude in (None, ""):
        return {"ok": True}

    employee = _employee_for(frappe.session.user)
    vehicle = frappe.db.sql(
        """select t.vehicle from `tabCIT Trip` t
           inner join `tabCIT Trip Crew` c on c.parent = t.name
           where c.employee = %s and t.status = 'In Transit' and t.docstatus = 1
           order by t.modified desc limit 1""",
        (employee,))
    if not vehicle:
        return {"ok": True, "note": "no active trip"}

    from alphax_cit.api.gps import ingest
    ingest([{
        "vehicle": vehicle[0][0],
        "latitude": latitude,
        "longitude": longitude,
        "event_time": str(now_datetime()),
        "raw": {"source": "handset", "battery": battery, "device": _device_id()},
    }], provider=_handset_provider())
    return {"ok": True}


def _handset_provider():
    """The handset feed is a GPS provider like any other, so geofence
    evaluation, dwell measurement and retention all apply to it unchanged."""
    name = "AlphaX Handset"
    if not frappe.db.exists("GPS Provider", name):
        doc = frappe.get_doc({
            "doctype": "GPS Provider",
            "provider_name": name,
            "provider_key": "custom",
            "enabled": 1,
            "poll_interval_minutes": 0,
        })
        doc.flags.ignore_permissions = True
        doc.insert(ignore_permissions=True)
    return name

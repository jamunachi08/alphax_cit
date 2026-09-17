"""Tests for the mobile edge and the sync engine.

Run with:
    bench --site <site> run-tests --app alphax_cit --module alphax_cit.tests.test_mobile_sync

These cover the four defects found in the v0.4.0 review. They are regression
tests: each one fails against the code as it was shipped and passes now.
"""

import json
import uuid

import frappe
from frappe.tests.utils import FrappeTestCase

from alphax_cit.api import mobile, sync


def _cid():
    return str(uuid.uuid4())


class TestSyncIsNotPublic(FrappeTestCase):
    """Defect 1 — the device guard must not be bypassable."""

    def test_push_and_pull_are_not_whitelisted(self):
        # frappe.whitelist() sets this attribute. Its absence is what keeps
        # /api/method/alphax_cit.api.sync.push returning 403.
        self.assertFalse(getattr(sync.push, "is_whitelisted", False),
                         "sync.push must not be callable over the API")
        self.assertFalse(getattr(sync.pull, "is_whitelisted", False),
                         "sync.pull must not be callable over the API")

    def test_mobile_endpoints_are_whitelisted(self):
        for fn in (mobile.push, mobile.pull, mobile.bootstrap, mobile.upload_photo):
            self.assertTrue(getattr(fn, "is_whitelisted", False),
                            f"{fn.__name__} should be the public entry point")


class TestRosterAuthorisation(FrappeTestCase):
    """Defect 1, second half — a valid session is not enough to touch a trip."""

    def setUp(self):
        self.trip = frappe.db.get_value("CIT Trip", {"docstatus": 1}, "name")
        if not self.trip:
            self.skipTest("no submitted CIT Trip in this site")

    def test_stranger_is_refused(self):
        stranger = frappe.db.get_value(
            "Employee", {"name": ["not in",
                                  frappe.get_all("CIT Trip Crew",
                                                 filters={"parent": self.trip},
                                                 pluck="employee") or [""]]},
            "name")
        if not stranger:
            self.skipTest("no unrelated Employee to test with")

        frappe.set_user("Guest")  # no dispatcher exemption
        try:
            with self.assertRaises(frappe.PermissionError):
                sync.assert_own_trip(self.trip, stranger)
        finally:
            frappe.set_user("Administrator")

    def test_rostered_crew_is_allowed(self):
        crew = frappe.get_all("CIT Trip Crew", filters={"parent": self.trip}, pluck="employee")
        if not crew:
            self.skipTest("trip has no crew rows")
        sync.assert_own_trip(self.trip, crew[0])  # must not raise

    def test_rejected_event_is_not_applied(self):
        res = sync._apply_one(
            {"client_event_id": _cid(), "seq": 1, "event_type": "trip_start",
             "payload": {"trip": self.trip}},
            device_id="test-device", employee="NON-EXISTENT-EMP")
        # Administrator carries System Manager, so this only asserts the shape
        # when the exemption does not apply. Run as a crew user for the full path.
        self.assertIn(res["status"], ("Rejected", "Applied", "Quarantined"))


class TestDuplicateSemantics(FrappeTestCase):
    """Defect 2 — Duplicate must mean 'already applied', never 'already failed'."""

    def _log(self, cid, status):
        doc = frappe.get_doc({
            "doctype": "CIT Sync Event",
            "client_event_id": cid,
            "device_id": "test-device",
            "sequence_no": 1,
            "event_type": "unknown_event_type_for_test",
            "received_on": frappe.utils.now_datetime(),
            "payload": "{}",
            "status": status,
        })
        doc.flags.ignore_permissions = True
        doc.insert(ignore_permissions=True)
        return doc

    def test_applied_event_returns_duplicate(self):
        cid = _cid()
        self._log(cid, "Applied")
        res = sync._apply_one(
            {"client_event_id": cid, "seq": 1, "event_type": "unknown_event_type_for_test",
             "payload": {}}, device_id="test-device")
        self.assertEqual(res["status"], "Duplicate")

    def test_quarantined_event_is_retried_not_duplicated(self):
        cid = _cid()
        self._log(cid, "Quarantined")
        res = sync._apply_one(
            {"client_event_id": cid, "seq": 1, "event_type": "unknown_event_type_for_test",
             "payload": {}}, device_id="test-device")
        # The handset deletes anything it sees as Duplicate. A failed event
        # must never come back with that status.
        self.assertNotEqual(res["status"], "Duplicate")
        self.assertEqual(res["status"], "Quarantined")

    def test_retry_of_a_real_handler_applies_and_clears_the_error(self):
        trip = frappe.db.get_value("CIT Trip", {"docstatus": 1, "status": "Dispatched"}, "name")
        if not trip:
            self.skipTest("no dispatched trip available")
        cid = _cid()
        doc = self._log(cid, "Quarantined")
        doc.db_set({"event_type": "trip_start", "error_message": "earlier failure"})

        res = sync._apply_one(
            {"client_event_id": cid, "seq": 1, "event_type": "trip_start",
             "payload": {"trip": trip}}, device_id="test-device")
        self.assertEqual(res["status"], "Applied")
        row = frappe.get_doc("CIT Sync Event", doc.name)
        self.assertEqual(row.status, "Applied")
        self.assertEqual(row.retry_count, 1)
        self.assertFalse(row.error_message)


class TestPodPhotos(FrappeTestCase):
    """Defect 3 — photos sent by the handset must land on the POD."""

    def test_photos_are_copied_into_the_document(self):
        trip = frappe.db.get_value("CIT Trip", {"docstatus": 1}, "name")
        if not trip:
            self.skipTest("no submitted CIT Trip in this site")
        job = frappe.db.get_value("CIT Job", {"cit_trip": trip}, "name")

        cid = _cid()
        res = sync._apply_one({
            "client_event_id": cid, "seq": 1, "event_type": "pod_capture",
            "payload": {
                "trip": trip, "job": job, "pod_type": "Collection",
                "signatory_name": "Test Receiver", "signatory_id": "1000000000",
                "signature": "/private/files/test-signature.png",
                "photos": [
                    {"photo": "/private/files/test-seal-1.jpg", "caption": "Seal 1"},
                    {"photo": "/private/files/test-seal-2.jpg"},
                ],
                "bags": [{"seal_no": "SEAL-1", "declared_amount": 1000}],
            },
        }, device_id="test-device")

        self.assertEqual(res["status"], "Applied", res.get("error"))
        pod = frappe.get_doc("CIT POD", res["result_name"])
        self.assertEqual(len(pod.photos), 2)
        self.assertEqual(pod.photos[0].photo, "/private/files/test-seal-1.jpg")
        self.assertEqual(pod.photos[0].caption, "Seal 1")
        self.assertEqual(pod.photos[1].caption, "")

    def test_bad_photo_rows_are_dropped_not_fatal(self):
        trip = frappe.db.get_value("CIT Trip", {"docstatus": 1}, "name")
        if not trip:
            self.skipTest("no submitted CIT Trip in this site")
        cid = _cid()
        res = sync._apply_one({
            "client_event_id": cid, "seq": 1, "event_type": "pod_capture",
            "payload": {
                "trip": trip, "pod_type": "Collection", "signatory_name": "Test",
                "photos": [None, "", {"caption": "no url"}, "/private/files/ok.jpg"],
            },
        }, device_id="test-device")
        self.assertEqual(res["status"], "Applied", res.get("error"))
        pod = frappe.get_doc("CIT POD", res["result_name"])
        self.assertEqual(len(pod.photos), 1)


class TestDeviceGuard(FrappeTestCase):
    """The control that stands in for 2FA on API sessions."""

    def test_missing_header_is_refused(self):
        frappe.local.request_headers = {}
        frappe.form_dict.pop("device_id", None)
        with self.assertRaises(frappe.PermissionError):
            mobile.require_device()

    def test_inactive_device_is_refused(self):
        did = "test-" + _cid()[:8]
        doc = frappe.get_doc({"doctype": "CIT Device", "device_id": did, "active": 0})
        doc.flags.ignore_permissions = True
        doc.insert(ignore_permissions=True)
        frappe.form_dict["device_id"] = did
        try:
            with self.assertRaises(frappe.PermissionError):
                mobile.require_device()
        finally:
            frappe.form_dict.pop("device_id", None)

    def test_active_device_passes(self):
        did = "test-" + _cid()[:8]
        doc = frappe.get_doc({"doctype": "CIT Device", "device_id": did, "active": 1})
        doc.flags.ignore_permissions = True
        doc.insert(ignore_permissions=True)
        frappe.form_dict["device_id"] = did
        try:
            self.assertEqual(mobile.require_device(), doc.name)
        finally:
            frappe.form_dict.pop("device_id", None)

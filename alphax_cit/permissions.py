"""Row-level visibility.

A crew member sees only the trips they are assigned to. Everyone else is
governed by the standard role permission model.
"""

import frappe


def _crew_only():
	roles = set(frappe.get_roles())
	return "CIT Crew" in roles and not (roles & {
		"CIT Manager", "CIT Dispatcher", "CIT Control Room", "CIT Auditor", "System Manager"})


def _employee_for_user():
	return frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")


def trip_query_conditions(user=None):
	if not _crew_only():
		return ""
	employee = _employee_for_user()
	if not employee:
		return "1=0"
	return f"""`tabCIT Trip`.name in (
		select parent from `tabCIT Trip Crew` where employee = {frappe.db.escape(employee)}
	)"""


def pod_query_conditions(user=None):
	if not _crew_only():
		return ""
	employee = _employee_for_user()
	if not employee:
		return "1=0"
	return f"`tabCIT POD`.captured_by = {frappe.db.escape(employee)}"


def trip_has_permission(doc, ptype="read", user=None):
	if not _crew_only():
		return True
	employee = _employee_for_user()
	if not employee:
		return False
	return any(c.employee == employee for c in (doc.crew or []))

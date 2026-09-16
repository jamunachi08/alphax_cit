"""Serves the interactive process flow board.

Every node points at a real document type — AlphaX CIT documents and the
standard ERPNext documents the process depends on — so the flow chart is a
navigation surface, not a picture.
"""

import json

import frappe
from frappe import _


def _parse_filters(raw):
	if not raw:
		return {}
	try:
		val = json.loads(raw)
		return val if isinstance(val, dict) else {}
	except ValueError:
		return {}


@frappe.whitelist()
def get_flow(flow=None, with_counts=1):
	if not flow:
		flow = frappe.db.get_value("CIT Process Flow", {"is_default": 1, "disabled": 0}, "name") \
			or frappe.db.get_value("CIT Process Flow", {"disabled": 0}, "name")
	if not flow:
		return {}

	doc = frappe.get_doc("CIT Process Flow", flow)
	nodes = frappe.get_all(
		"CIT Process Node",
		filters={"process_flow": flow, "disabled": 0},
		fields=["name", "node_label", "node_label_ar", "stage_key", "sequence", "node_type",
		        "document_type", "is_erpnext_standard", "default_view", "report_name",
		        "route_override", "filters_json", "description", "icon", "show_count"],
		order_by="sequence asc, node_label asc",
	)

	user_roles = set(frappe.get_roles())
	visible = []
	for n in nodes:
		allowed = [r.role for r in frappe.get_all(
			"CIT Node Role", filters={"parent": n.name}, fields=["role"])]
		if allowed and not (user_roles & set(allowed)):
			continue
		if n.node_type == "DocType" and n.document_type:
			if not frappe.has_permission(n.document_type, "read"):
				continue
			n["can_create"] = frappe.has_permission(n.document_type, "create")
		else:
			n["can_create"] = False
		n["filters"] = _parse_filters(n.filters_json)
		n["count"] = None
		if int(with_counts or 0) and n.show_count and n.node_type == "DocType" and n.document_type:
			try:
				n["count"] = frappe.db.count(n.document_type, n["filters"])
			except Exception:
				n["count"] = None
		visible.append(n)

	stages = []
	for st in sorted(doc.stages, key=lambda s: s.sequence or 0):
		stages.append({
			"stage_key": st.stage_key,
			"stage_label": st.stage_label,
			"stage_label_ar": st.stage_label_ar,
			"lane": st.lane,
			"sequence": st.sequence,
			"colour": st.colour,
			"nodes": [n for n in visible if n.stage_key == st.stage_key],
		})

	return {
		"flow": doc.name,
		"flow_name": doc.flow_name,
		"description": doc.description,
		"stages": stages,
	}


@frappe.whitelist()
def node_summary(flow=None):
	"""Counts of CIT versus standard ERPNext documents exposed by the flow."""
	filters = {"disabled": 0}
	if flow:
		filters["process_flow"] = flow
	rows = frappe.get_all("CIT Process Node", filters=filters,
	                      fields=["is_erpnext_standard", "count(name) as total"],
	                      group_by="is_erpnext_standard")
	out = {"erpnext_standard": 0, "alphax_cit": 0}
	for r in rows:
		if r.is_erpnext_standard:
			out["erpnext_standard"] = r.total
		else:
			out["alphax_cit"] = r.total
	return out

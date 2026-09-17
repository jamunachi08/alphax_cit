"""Public-facing journey page at /cit-journey.

Rendered from the same `CIT Journey — Start to End` flow that drives the desk
page, so the customer-facing chart and the operator's view can never drift.

Access is controlled by AlphaX CIT Settings > "Publish journey page publicly".
When that is off, the page requires a login.
"""

import frappe
from frappe import _

FLOW_NAME = "CIT Journey — Start to End"

PHASE_COLOURS = {
	"Commercial": "#2E75B6",
	"Operations": "#1F3864",
	"Field": "#1F7A6C",
	"Vault & Cash": "#B07C00",
	"Finance": "#0F766E",
}

PHASE_CAPTIONS = {
	"Commercial": _("set up once"),
	"Operations": _("plan and send"),
	"Field": _("on the road"),
	"Vault & Cash": _("prove the money"),
	"Finance": _("get paid"),
}

no_cache = 1


def get_context(context):
	settings = frappe.get_cached_doc("AlphaX CIT Settings")
	if not settings.get("publish_journey_page") and frappe.session.user == "Guest":
		frappe.throw(_("Please log in to view this page."), frappe.PermissionError)

	context.no_cache = 1
	context.show_sidebar = False
	lang = frappe.form_dict.get("lang")
	if not lang and frappe.session.user != "Guest":
		lang = frappe.db.get_value("User", frappe.session.user, "language") or "en"
	context.arabic = str(lang or "en").startswith("ar")

	direction = frappe.form_dict.get("dir")
	if direction not in ("ltr", "rtl"):
		setting = settings.get("interface_direction") or "Automatic"
		if setting == "Left to Right":
			direction = "ltr"
		elif setting == "Right to Left":
			direction = "rtl"
		else:
			direction = "rtl" if context.arabic else "ltr"
	context.direction = direction

	flow = frappe.db.exists("CIT Process Flow", FLOW_NAME) or frappe.db.get_value(
		"CIT Process Flow", {"flow_type": "Journey", "disabled": 0}, "name")
	if not flow:
		context.phases = []
		context.title = _("CIT Journey")
		return context

	doc = frappe.get_doc("CIT Process Flow", flow)
	context.title = doc.flow_name_ar if (context.arabic and doc.flow_name_ar) else doc.flow_name
	context.subtitle = doc.description
	context.company = (
		settings.get("default_company")
		or frappe.defaults.get_global_default("company")
		or "")

	nodes = frappe.get_all(
		"CIT Process Node",
		filters={"process_flow": flow, "disabled": 0},
		fields=["node_label", "node_label_ar", "stage_key", "sequence",
		        "document_type", "is_erpnext_standard", "node_type"],
		order_by="sequence asc", ignore_permissions=True)

	phases = []
	total = len(doc.stages)
	for st in sorted(doc.stages, key=lambda s: s.sequence or 0):
		colour = st.colour or PHASE_COLOURS.get(st.lane, "#1F3864")
		if not phases or phases[-1]["name"] != st.lane:
			phases.append({
				"name": st.lane,
				"caption": PHASE_CAPTIONS.get(st.lane, ""),
				"colour": colour,
				"steps": [],
			})
		phases[-1]["steps"].append({
			"sequence": st.sequence,
			"label": st.stage_label_ar if (context.arabic and st.stage_label_ar) else st.stage_label,
			"label_alt": st.stage_label_ar if not context.arabic else st.stage_label,
			"actor": st.get("actor"),
			"duration": st.get("duration_hint"),
			"what": (st.get("what_happens_ar") if context.arabic and st.get("what_happens_ar")
			         else st.get("what_happens")),
			"guarantee": st.get("guarantee"),
			"is_last": st.sequence == total,
			"colour": colour,
			"docs": [{
				"label": n.node_label_ar if (context.arabic and n.node_label_ar) else n.node_label,
				"standard": n.is_erpnext_standard,
			} for n in nodes if n.stage_key == st.stage_key],
		})

	context.phases = phases
	context.step_count = total
	context.lang_toggle = "?lang={0}&dir={1}".format(
		"en" if context.arabic else "ar", context.direction)
	context.lang_label = "English" if context.arabic else "العربية"
	context.dir_toggle = "?lang={0}&dir={1}".format(
		"ar" if context.arabic else "en", "ltr" if context.direction == "rtl" else "rtl")
	context.dir_label = _("Left to right") if context.direction == "rtl" else _("Right to left")
	return context

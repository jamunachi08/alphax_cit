import frappe


def execute():
	"""The desk page used to share a route with the CIT Process Flow DocType.

	Frappe resolves the DocType list first, so /app/cit-process-flow opened the
	list instead of the board. The page is now /app/cit-flow. This removes the
	shadowed page record, repoints the workspace shortcut, and corrects the
	flow_type that the field default wrote onto the detailed board.
	"""
	if frappe.db.exists("Page", "cit-process-flow"):
		frappe.delete_doc("Page", "cit-process-flow", force=True, ignore_permissions=True)

	for row in frappe.get_all("Workspace Shortcut",
	                          filters={"link_to": "cit-process-flow"}, pluck="name"):
		frappe.db.set_value("Workspace Shortcut", row, "link_to", "cit-flow")

	journey = frappe.db.get_value("CIT Process Flow", {"flow_type": "Journey", "is_default": 1},
	                              "name")
	for flow in frappe.get_all("CIT Process Flow", pluck="name"):
		if journey and flow == journey:
			continue
		frappe.db.set_value("CIT Process Flow", flow,
		                    {"flow_type": "Detailed", "is_default": 0})
	frappe.db.commit()

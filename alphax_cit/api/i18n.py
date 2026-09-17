"""Language and reading-direction helpers.

Frappe already flips the desk to RTL when the user's language is Arabic. These
helpers give the user a one-click switch instead of a trip to My Settings, and
let a site force left-to-right reading even while showing Arabic text — which
some finance teams prefer for numeric screens.
"""

import frappe
from frappe import _

SUPPORTED = ("en", "ar")


@frappe.whitelist()
def set_language(lang):
	"""Switch the signed-in user's interface language."""
	if lang not in SUPPORTED:
		frappe.throw(_("Unsupported language"))
	frappe.db.set_value("User", frappe.session.user, "language", lang)
	frappe.local.lang = lang
	frappe.clear_cache(user=frappe.session.user)
	return lang


@frappe.whitelist()
def get_direction():
	"""Resolve the reading direction for the current user.

	AlphaX CIT Settings > Interface Direction:
	  Automatic  — follow the language (Arabic = rtl)
	  Left to Right / Right to Left — force it for everyone
	The user's own choice on the flow page overrides this per browser.
	"""
	setting = frappe.db.get_single_value("AlphaX CIT Settings", "interface_direction") \
		or "Automatic"
	lang = frappe.db.get_value("User", frappe.session.user, "language") or \
		frappe.local.lang or "en"
	if setting == "Left to Right":
		direction = "ltr"
	elif setting == "Right to Left":
		direction = "rtl"
	else:
		direction = "rtl" if str(lang).startswith("ar") else "ltr"
	return {"direction": direction, "language": lang, "setting": setting}


@frappe.whitelist()
def bilingual_label(doctype, name, field, field_ar):
	"""Return the Arabic value when the user reads Arabic, else the English one."""
	lang = frappe.local.lang or "en"
	row = frappe.db.get_value(doctype, name, [field, field_ar], as_dict=True) or {}
	if str(lang).startswith("ar") and row.get(field_ar):
		return row[field_ar]
	return row.get(field)

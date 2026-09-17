"""Idempotent installers. Safe to run on every migrate — nothing is duplicated."""

import frappe

from alphax_cit.seed import (custom_fields, defaults, journey_flow, process_flow,
                             roles, workspace)


def before_install():
	"""Runs before the DocType JSONs are imported.

	DocType permission rows, the desk page and the reports all link to the CIT
	roles, so the roles have to exist first or the import fails on a link
	validation error.
	"""
	roles.seed_roles()
	frappe.db.commit()


def after_install():
	after_migrate()


def after_migrate():
	roles.seed_roles()
	custom_fields.seed_custom_fields()
	defaults.seed_service_types()
	defaults.seed_checklist_template()
	defaults.seed_settings()
	process_flow.seed_process_flow()
	journey_flow.seed_journey_flow()
	workspace.seed_workspace()
	frappe.db.commit()


def before_uninstall():
	"""Leave data intact; only remove the custom fields we own."""
	custom_fields.remove_custom_fields()

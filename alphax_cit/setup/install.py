"""Idempotent installers. Safe to run on every migrate — nothing is duplicated."""

import frappe

from alphax_cit.seed import (custom_fields, defaults, process_flow, roles, workspace)


def after_install():
	after_migrate()


def after_migrate():
	roles.seed_roles()
	custom_fields.seed_custom_fields()
	defaults.seed_service_types()
	defaults.seed_checklist_template()
	defaults.seed_settings()
	process_flow.seed_process_flow()
	workspace.seed_workspace()
	frappe.db.commit()


def before_uninstall():
	"""Leave data intact; only remove the custom fields we own."""
	custom_fields.remove_custom_fields()

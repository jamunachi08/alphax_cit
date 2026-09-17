import frappe
from alphax_cit.setup.install import after_migrate


def execute():
	"""Idempotent baseline: roles, custom fields, settings, process flow."""
	after_migrate()

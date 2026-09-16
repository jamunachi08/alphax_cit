import click
import frappe
from frappe.commands import get_site, pass_context


@click.command("cit-demo")
@click.option("--clear", is_flag=True, default=False, help="Remove the demo dataset instead")
@pass_context
def cit_demo(context, clear=False):
	"""Seed (or clear) the AlphaX CIT demo dataset."""
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	try:
		from alphax_cit.demo import demo_data

		if clear:
			demo_data.clear_demo_data()
		else:
			demo_data.create_demo_data()
	finally:
		frappe.destroy()


commands = [cit_demo]

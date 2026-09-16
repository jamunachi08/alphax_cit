"""Pulls the standard ERPNext documents into the CIT process.

Nothing in ERPNext core is modified — these are Custom Fields owned by
alphax_cit, created idempotently and removed cleanly on uninstall.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

FIELDS = {
	"Vehicle": [
		{"fieldname": "cit_section", "fieldtype": "Section Break", "label": "CIT Armoured Fleet",
		 "insert_after": "vehicle_value"},
		{"fieldname": "cit_is_armoured", "fieldtype": "Check", "label": "Armoured Vehicle",
		 "insert_after": "cit_section", "default": "1"},
		{"fieldname": "cit_armour_level", "fieldtype": "Select", "label": "Armour Level",
		 "options": "\nB4\nB6\nB7\nOther", "insert_after": "cit_is_armoured"},
		{"fieldname": "cit_compartments", "fieldtype": "Int", "label": "Cash Compartments",
		 "insert_after": "cit_armour_level"},
		{"fieldname": "cit_crew_capacity", "fieldtype": "Int", "label": "Crew Capacity",
		 "insert_after": "cit_compartments", "default": "3"},
		{"fieldname": "cit_col_1", "fieldtype": "Column Break", "insert_after": "cit_crew_capacity"},
		{"fieldname": "cit_tracker_id", "fieldtype": "Data", "label": "GPS Tracker ID",
		 "insert_after": "cit_col_1", "unique": 1},
		{"fieldname": "cit_radio_call_sign", "fieldtype": "Data", "label": "Radio Call Sign",
		 "insert_after": "cit_tracker_id"},
		{"fieldname": "cit_weapon_locker", "fieldtype": "Check", "label": "Weapon Locker Fitted",
		 "insert_after": "cit_radio_call_sign"},
		{"fieldname": "cit_asset", "fieldtype": "Link", "label": "Linked Asset", "options": "Asset",
		 "insert_after": "cit_weapon_locker"},
		{"fieldname": "cit_availability", "fieldtype": "Select", "label": "Availability",
		 "options": "In Service\nOn Trip\nWorkshop\nReserved\nOff Road\nAccident",
		 "default": "In Service", "insert_after": "cit_asset", "in_standard_filter": 1},
	],
	"Employee": [
		{"fieldname": "cit_section", "fieldtype": "Section Break", "label": "CIT Crew Qualification",
		 "insert_after": "employment_details", "collapsible": 1},
		{"fieldname": "cit_is_crew", "fieldtype": "Check", "label": "CIT Crew Member",
		 "insert_after": "cit_section"},
		{"fieldname": "cit_crew_role", "fieldtype": "Select", "label": "Default Crew Role",
		 "options": "\nDriver\nTeam Leader\nCustodian\nGuard", "insert_after": "cit_is_crew"},
		{"fieldname": "cit_licence_class", "fieldtype": "Data", "label": "Driving Licence Class",
		 "insert_after": "cit_crew_role"},
		{"fieldname": "cit_licence_expiry", "fieldtype": "Date", "label": "Driving Licence Expiry",
		 "insert_after": "cit_licence_class"},
		{"fieldname": "cit_col_1", "fieldtype": "Column Break", "insert_after": "cit_licence_expiry"},
		{"fieldname": "cit_security_clearance_no", "fieldtype": "Data", "label": "Security Clearance No",
		 "insert_after": "cit_col_1"},
		{"fieldname": "cit_security_clearance_expiry", "fieldtype": "Date",
		 "label": "Security Clearance Expiry", "insert_after": "cit_security_clearance_no"},
		{"fieldname": "cit_weapon_permit_no", "fieldtype": "Data", "label": "Weapon Permit No",
		 "insert_after": "cit_security_clearance_expiry"},
		{"fieldname": "cit_weapon_permit_expiry", "fieldtype": "Date", "label": "Weapon Permit Expiry",
		 "insert_after": "cit_weapon_permit_no"},
		{"fieldname": "cit_medical_fitness_expiry", "fieldtype": "Date", "label": "Medical Fitness Expiry",
		 "insert_after": "cit_weapon_permit_expiry"},
		{"fieldname": "iqama_expiry_date", "fieldtype": "Date", "label": "Iqama Expiry Date",
		 "insert_after": "cit_medical_fitness_expiry"},
	],
	"Customer": [
		{"fieldname": "cit_section", "fieldtype": "Section Break", "label": "CIT Service Profile",
		 "insert_after": "credit_limit_section", "collapsible": 1},
		{"fieldname": "cit_is_cit_customer", "fieldtype": "Check", "label": "CIT Customer",
		 "insert_after": "cit_section"},
		{"fieldname": "cit_risk_class", "fieldtype": "Select", "label": "Risk Classification",
		 "options": "\nStandard\nElevated\nHigh", "insert_after": "cit_is_cit_customer"},
		{"fieldname": "cit_col_1", "fieldtype": "Column Break", "insert_after": "cit_risk_class"},
		{"fieldname": "cit_active_contract", "fieldtype": "Link", "label": "Active Service Contract",
		 "options": "CIT Service Contract", "insert_after": "cit_col_1", "read_only": 1},
	],
	"Contract": [
		{"fieldname": "cit_service_contract", "fieldtype": "Link", "label": "CIT Service Contract",
		 "options": "CIT Service Contract", "insert_after": "document_name", "read_only": 1},
	],
	"Sales Invoice": [
		{"fieldname": "cit_billing_run", "fieldtype": "Link", "label": "CIT Billing Run",
		 "options": "CIT Billing Run", "insert_after": "project", "read_only": 1,
		 "in_standard_filter": 1},
	],
	"Sales Invoice Item": [
		{"fieldname": "cit_trip", "fieldtype": "Link", "label": "CIT Trip", "options": "CIT Trip",
		 "insert_after": "cost_center", "read_only": 1},
	],
	"Journal Entry": [
		{"fieldname": "cit_discrepancy", "fieldtype": "Link", "label": "CIT Discrepancy",
		 "options": "CIT Discrepancy", "insert_after": "user_remark", "read_only": 1},
	],
	"Address": [
		{"fieldname": "cit_customer_site", "fieldtype": "Link", "label": "CIT Customer Site",
		 "options": "Customer Site", "insert_after": "is_shipping_address", "read_only": 1},
	],
	"Item": [
		{"fieldname": "cit_charge_basis", "fieldtype": "Select", "label": "CIT Charge Basis",
		 "options": "\nPer Trip\nPer Stop\nPer Bag\nAd Valorem\nPer KM\nFixed Monthly\n"
		            "Waiting Time\nAfter Hours\nEmergency Call Out",
		 "insert_after": "item_group"},
	],
	"Asset": [
		{"fieldname": "cit_vehicle", "fieldtype": "Link", "label": "CIT Vehicle", "options": "Vehicle",
		 "insert_after": "asset_category"},
	],
}


def seed_custom_fields():
	create_custom_fields(FIELDS, ignore_validate=True, update=True)


def remove_custom_fields():
	for doctype, fields in FIELDS.items():
		for f in fields:
			name = f"{doctype}-{f['fieldname']}"
			if frappe.db.exists("Custom Field", name):
				frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)

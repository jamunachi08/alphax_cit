"""Demo dataset for AlphaX CIT — Wadi Secure Logistics.

Seeds a complete, believable operation and walks one trip end to end:
job → trip → dispatch → proof of collection → custody → vault-in →
counting session with a deliberate shortage → discrepancy → billing run.

Idempotent: every record is keyed and skipped if it already exists, so the
command can be run repeatedly. Nothing here is installed automatically —
run it explicitly:

    bench --site <site> execute alphax_cit.demo.demo_data.create_demo_data
    bench --site <site> execute alphax_cit.demo.demo_data.clear_demo_data
"""

import frappe
from frappe.utils import add_days, add_to_date, flt, getdate, nowdate, now_datetime

DEMO_TAG = "AlphaX CIT Demo"

CUSTOMERS = [
	("Wadi National Bank", "Elevated", "300012345600003"),
	("Riyadh Retail Group", "Standard", "300098765400003"),
	("Najd Fuel Stations", "Standard", "300055512300003"),
]

SITES = [
	("WNB Olaya Branch", "Wadi National Bank", 24.6944, 46.6853, "08:00:00", "14:00:00"),
	("WNB Malaz Branch", "Wadi National Bank", 24.6612, 46.7365, "08:00:00", "14:00:00"),
	("WNB ATM Cluster — Tahlia", "Wadi National Bank", 24.6900, 46.6820, "06:00:00", "22:00:00"),
	("RRG Panorama Mall", "Riyadh Retail Group", 24.6970, 46.6860, "20:00:00", "23:00:00"),
	("RRG Granada Centre", "Riyadh Retail Group", 24.7740, 46.7380, "20:00:00", "23:00:00"),
	("NFS Station 14 — Exit 9", "Najd Fuel Stations", 24.8100, 46.7600, "22:00:00", "23:59:00"),
]

VEHICLES = [
	("CIT-4101", "B6", "TRK-4101", 3, 48200),
	("CIT-4102", "B6", "TRK-4102", 3, 51900),
	("CIT-4103", "B7", "TRK-4103", 4, 33750),
	("CIT-4104", "B6", "TRK-4104", 3, 62400),
	("CIT-4105", "B4", "TRK-4105", 2, 18900),
]

# name, crew role, licence expiry offset (days), clearance offset, permit offset
CREW = [
	("Faisal Al Harbi", "Driver", 420, 300, 260),
	("Majed Al Otaibi", "Team Leader", 380, 210, 190),
	("Saleh Al Dosari", "Custodian", 500, 340, 310),
	("Turki Al Qahtani", "Guard", 260, 150, 120),
	("Nawaf Al Shammari", "Driver", 610, 400, 380),
	("Bandar Al Ghamdi", "Guard", 95, 88, 70),
	("Ahmed Al Zahrani", "Custodian", 240, 180, 160),
	("Khalid Al Mutairi", "Guard", -12, 210, 180),   # expired licence — demonstrates the dispatch block
]

BILLING_ITEMS = [
	("CIT-STOP", "CIT Collection Stop", "Per Stop"),
	("CIT-BAG", "CIT Bag Handling", "Per Bag"),
	("CIT-ADV", "CIT Ad Valorem Charge", "Ad Valorem"),
	("CIT-WAIT", "CIT Waiting Time", "Waiting Time"),
	("CIT-KM", "CIT Distance Charge", "Per KM"),
]


# ---------------------------------------------------------------- helpers
def _company():
	company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
	if not company:
		frappe.throw("Create a Company first — the demo data needs one.")
	return company


def _abbr(company):
	return frappe.db.get_value("Company", company, "abbr")


def _account(company, keywords, root_type=None):
	filters = {"company": company, "is_group": 0}
	if root_type:
		filters["root_type"] = root_type
	for kw in keywords:
		name = frappe.db.get_value("Account", dict(filters, account_name=("like", f"%{kw}%")), "name")
		if name:
			return name
	return frappe.db.get_value("Account", filters, "name")


def _insert(doc_dict, key_filters=None):
	"""Insert unless an equivalent record already exists."""
	doctype = doc_dict["doctype"]
	if key_filters and frappe.db.exists(doctype, key_filters):
		return frappe.db.get_value(doctype, key_filters, "name")
	doc = frappe.get_doc(doc_dict)
	doc.flags.ignore_permissions = True
	doc.flags.ignore_mandatory = False
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_uom(name="Litre"):
	if not frappe.db.exists("UOM", name):
		frappe.get_doc({"doctype": "UOM", "uom_name": name}).insert(ignore_permissions=True)
	return name


def _ensure_item_group():
	name = "CIT Services"
	if not frappe.db.exists("Item Group", name):
		parent = frappe.db.get_value("Item Group", {"is_group": 1, "parent_item_group": ""}, "name") \
			or "All Item Groups"
		frappe.get_doc({"doctype": "Item Group", "item_group_name": name,
		                "parent_item_group": parent, "is_group": 0}).insert(ignore_permissions=True)
	return name


# ---------------------------------------------------------------- masters
def seed_items():
	group = _ensure_item_group()
	for code, name, basis in BILLING_ITEMS:
		if frappe.db.exists("Item", code):
			continue
		frappe.get_doc({
			"doctype": "Item", "item_code": code, "item_name": name, "item_group": group,
			"stock_uom": "Nos", "is_stock_item": 0, "is_sales_item": 1, "is_purchase_item": 0,
			"cit_charge_basis": basis, "description": name,
		}).insert(ignore_permissions=True)


def seed_customers():
	for name, risk, vat in CUSTOMERS:
		if frappe.db.exists("Customer", name):
			continue
		frappe.get_doc({
			"doctype": "Customer", "customer_name": name, "customer_type": "Company",
			"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
			"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
			"tax_id": vat, "cit_is_cit_customer": 1, "cit_risk_class": risk,
		}).insert(ignore_permissions=True)


def seed_sites():
	for site, customer, lat, lng, w_from, w_to in SITES:
		if frappe.db.exists("Customer Site", {"site_name": site}):
			continue
		doc = frappe.get_doc({
			"doctype": "Customer Site", "site_name": site, "customer": customer,
			"city": "Riyadh", "latitude": lat, "longitude": lng,
			"service_window_from": w_from, "service_window_to": w_to,
			"min_crew": 3, "armed_escort_required": 1,
			"access_protocol": "Report to the branch manager. Two-person rule applies at the teller door.",
			"key_or_pin_custody": "Held by site manager",
			"special_instructions": "Reverse into the service bay. Do not leave the vehicle unattended.",
		})
		doc.append("contacts", {"contact_name": "Site Manager", "designation": "Branch Manager",
		                        "id_number": "1234567890", "mobile": "+966500000000",
		                        "authorised_to_receive": 1})
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)


def seed_vault(company):
	name = "Riyadh Main Vault"
	if not frappe.db.exists("CIT Vault", name):
		frappe.get_doc({
			"doctype": "CIT Vault", "vault_name": name, "company": company,
			"latitude": 24.7136, "longitude": 46.6753,
			"cash_account": _account(company, ["Cash", "Petty Cash"], "Asset"),
		}).insert(ignore_permissions=True)
	return name


def seed_vehicles(company):
	uom = _ensure_uom()
	for plate, armour, tracker, compartments, odo in VEHICLES:
		if not frappe.db.exists("Vehicle", plate):
			frappe.get_doc({
				"doctype": "Vehicle", "license_plate": plate, "make": "Mercedes-Benz",
				"model": "Sprinter Armoured", "fuel_type": "Diesel", "uom": uom,
				"vehicle_value": 480000, "last_odometer": odo, "acquisition_date": add_days(nowdate(), -900),
				"chassis_no": f"WDB{plate[-4:]}00000", "location": "Riyadh",
				"cit_is_armoured": 1, "cit_armour_level": armour, "cit_tracker_id": tracker,
				"cit_compartments": compartments, "cit_crew_capacity": 3,
				"cit_radio_call_sign": f"ALPHA-{plate[-2:]}", "cit_weapon_locker": 1,
				"cit_availability": "In Service",
			}).insert(ignore_permissions=True)
		seed_vehicle_documents(plate)


def seed_vehicle_documents(plate):
	# one vehicle deliberately carries an expiring and an expired document
	offsets = {"CIT-4104": {"Insurance": 18, "Periodic Inspection": -6}}
	default = {"Istimara": 400, "Insurance": 220, "Periodic Inspection": 150,
	           "Operating Permit": 300, "Armour Certificate": 600}
	for doc_type, days in default.items():
		days = offsets.get(plate, {}).get(doc_type, days)
		if frappe.db.exists("Vehicle Compliance Document",
		                    {"vehicle": plate, "document_type": doc_type}):
			continue
		frappe.get_doc({
			"doctype": "Vehicle Compliance Document", "vehicle": plate,
			"document_type": doc_type, "document_number": f"{doc_type[:3].upper()}-{plate[-4:]}",
			"issuing_authority": "Ministry of Interior", "issue_date": add_days(nowdate(), -365),
			"expiry_date": add_days(nowdate(), days),
		}).insert(ignore_permissions=True)


def seed_crew(company):
	names = []
	for full_name, role, lic, clear, permit in CREW:
		existing = frappe.db.get_value("Employee", {"employee_name": full_name}, "name")
		if existing:
			names.append(existing)
			continue
		emp = frappe.get_doc({
			"doctype": "Employee", "employee_name": full_name, "first_name": full_name.split()[0],
			"last_name": " ".join(full_name.split()[1:]), "gender": "Male",
			"date_of_birth": add_days(nowdate(), -365 * 34),
			"date_of_joining": add_days(nowdate(), -400),
			"company": company, "status": "Active",
			"cit_is_crew": 1, "cit_crew_role": role,
			"cit_licence_class": "Heavy Vehicle",
			"cit_licence_expiry": add_days(nowdate(), lic),
			"cit_security_clearance_no": f"SC-{abs(hash(full_name)) % 100000:05d}",
			"cit_security_clearance_expiry": add_days(nowdate(), clear),
			"cit_weapon_permit_no": f"WP-{abs(hash(role)) % 10000:04d}",
			"cit_weapon_permit_expiry": add_days(nowdate(), permit),
			"cit_medical_fitness_expiry": add_days(nowdate(), 200),
			"iqama_expiry_date": add_days(nowdate(), 500),
		})
		emp.flags.ignore_permissions = True
		emp.flags.ignore_mandatory = True
		emp.insert(ignore_permissions=True)
		names.append(emp.name)
	return names


def seed_geofences(vault):
	for site, customer, lat, lng, _f, _t in SITES:
		gf_name = f"GF — {site}"
		site_name = frappe.db.get_value("Customer Site", {"site_name": site}, "name")
		if not frappe.db.exists("Geofence", gf_name):
			frappe.get_doc({
				"doctype": "Geofence", "geofence_name": gf_name, "geofence_type": "Customer Site",
				"shape": "Circle", "latitude": lat, "longitude": lng, "radius_metres": 120,
				"customer_site": site_name,
			}).insert(ignore_permissions=True)
			if site_name:
				frappe.db.set_value("Customer Site", site_name, "geofence", gf_name)
	if not frappe.db.exists("Geofence", "GF — Riyadh Main Vault"):
		frappe.get_doc({
			"doctype": "Geofence", "geofence_name": "GF — Riyadh Main Vault",
			"geofence_type": "Vault", "shape": "Circle", "latitude": 24.7136,
			"longitude": 46.6753, "radius_metres": 200, "vault": vault,
		}).insert(ignore_permissions=True)
	if not frappe.db.exists("Geofence", "GF — Restricted Zone North"):
		frappe.get_doc({
			"doctype": "Geofence", "geofence_name": "GF — Restricted Zone North",
			"geofence_type": "Restricted Zone", "shape": "Circle", "latitude": 24.9000,
			"longitude": 46.9000, "radius_metres": 1500, "prohibited": 1, "alert_on_entry": 1,
		}).insert(ignore_permissions=True)


def seed_gps_provider():
	if not frappe.db.exists("GPS Provider", "Demo Telematics"):
		frappe.get_doc({
			"doctype": "GPS Provider", "provider_name": "Demo Telematics",
			"provider_key": "generic_rest", "base_url": "", "poll_interval_minutes": 2,
			"enabled": 0,
		}).insert(ignore_permissions=True)


def seed_devices(crew):
	for i, emp in enumerate(crew[:4], start=1):
		device_id = f"DEV-{i:03d}"
		if frappe.db.exists("CIT Device", device_id):
			continue
		frappe.get_doc({
			"doctype": "CIT Device", "device_id": device_id, "employee": emp,
			"device_label": f"Crew tablet {i}", "platform": "Android",
			"app_version": "0.1.0", "active": 1,
		}).insert(ignore_permissions=True)


def seed_contracts(company):
	contracts = {}
	tariffs = {
		"Wadi National Bank": [
			("Cash Collection", "Per Stop", "CIT-STOP", 450, 0, 0),
			("Cash Collection", "Per Bag", "CIT-BAG", 25, 0, 0),
			("Cash Collection", "Ad Valorem", "CIT-ADV", 0, 0.035, 0),
			("Cash Collection", "Waiting Time", "CIT-WAIT", 6, 0, 20),
		],
		"Riyadh Retail Group": [
			("Cash Collection", "Per Stop", "CIT-STOP", 380, 0, 0),
			("Cash Collection", "Per Bag", "CIT-BAG", 20, 0, 0),
		],
		"Najd Fuel Stations": [
			("Cash Collection", "Per Stop", "CIT-STOP", 300, 0, 0),
			("Cash Collection", "Per KM", "CIT-KM", 4.5, 0, 0),
		],
	}
	for customer, lines in tariffs.items():
		existing = frappe.db.get_value("CIT Service Contract",
		                               {"customer": customer, "docstatus": 1}, "name")
		if existing:
			contracts[customer] = existing
			continue
		doc = frappe.get_doc({
			"doctype": "CIT Service Contract", "customer": customer,
			"contract_reference": f"CTR-{customer.split()[0].upper()}-2026",
			"start_date": add_days(nowdate(), -180),
			"end_date": add_days(nowdate(), 185 if customer != "Najd Fuel Stations" else 45),
			"notice_days": 90, "billing_frequency": "Monthly", "currency": "SAR",
			"minimum_monthly_commitment": 15000 if customer == "Wadi National Bank" else 0,
			"penalty_cap_percent": 5, "company": company,
		})
		for site, cust, *_rest in SITES:
			if cust != customer:
				continue
			site_name = frappe.db.get_value("Customer Site", {"site_name": site}, "name")
			doc.append("sites", {"customer_site": site_name, "service_type": "Cash Collection",
			                     "frequency": "Weekly", "visits_per_period": 3})
		for service, basis, item, rate, pct, free in lines:
			doc.append("tariff", {"service_type": service, "charge_basis": basis,
			                      "billing_item": item, "rate": rate, "rate_percent": pct,
			                      "free_units": free, "minimum_charge": 0})
		doc.append("sla_targets", {"sla_metric": "Arrival Window", "target_minutes": 30,
		                           "penalty_type": "Fixed", "penalty_value": 250})
		doc.append("sla_targets", {"sla_metric": "POD Submission", "target_minutes": 60,
		                           "penalty_type": "None"})
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
		doc.submit()
		contracts[customer] = doc.name
		frappe.db.set_value("Customer", customer, "cit_active_contract", doc.name)
	return contracts


def seed_seals(vault, crew, company):
	existing = frappe.db.get_value("Seal Register", {"vault": vault, "docstatus": 1}, "name")
	if existing:
		return existing
	doc = frappe.get_doc({
		"doctype": "Seal Register", "issue_date": add_days(nowdate(), -10),
		"issued_to": crew[2], "vault": vault, "seal_prefix": "SL",
		"from_no": 100001, "to_no": 100200, "company": company,
	})
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


# ---------------------------------------------------------------- the cycle
def seed_operational_cycle(company, vault, contracts, crew):
	"""One completed trip walked all the way to an invoice, plus live traffic."""
	if frappe.db.exists("CIT Trip", {"docstatus": 1, "status": "Reconciled"}):
		return

	sites = {s: frappe.db.get_value("Customer Site", {"site_name": s}, "name")
	         for s, *_ in SITES}

	# --- completed trip (three days ago)
	trip_date = add_days(nowdate(), -3)
	jobs = []
	for site_label, customer, value, bags in [
		("WNB Olaya Branch", "Wadi National Bank", 1_250_000, 14),
		("WNB Malaz Branch", "Wadi National Bank", 880_000, 9),
		("RRG Panorama Mall", "Riyadh Retail Group", 310_000, 6),
	]:
		job = frappe.get_doc({
			"doctype": "CIT Job", "customer": customer, "customer_site": sites[site_label],
			"service_type": "Cash Collection", "service_contract": contracts[customer],
			"job_date": trip_date, "window_from": "08:00:00", "window_to": "12:00:00",
			"declared_value": value, "currency": "SAR", "expected_bags": bags,
			"priority": "Normal", "company": company,
		})
		job.flags.ignore_permissions = True
		job.insert(ignore_permissions=True)
		job.submit()
		jobs.append((job.name, sites[site_label], value, bags))

	trip = frappe.get_doc({
		"doctype": "CIT Trip", "trip_date": trip_date, "shift": "Morning",
		"vehicle": "CIT-4101", "vault": vault, "route": "Olaya — Malaz — Panorama",
		"planned_start": f"{trip_date} 07:30:00", "planned_end": f"{trip_date} 13:00:00",
		"odometer_out": 48200, "odometer_in": 48314, "fuel_issued_litres": 60,
		"checklist_template": "Standard Pre-Trip Check", "company": company,
	})
	for emp, role in [(crew[0], "Driver"), (crew[1], "Team Leader"),
	                  (crew[2], "Custodian"), (crew[3], "Guard")]:
		trip.append("crew", {"employee": emp, "crew_role": role,
		                     "armed": 1 if role == "Guard" else 0})
	for i, (job_name, site, value, bags) in enumerate(jobs, start=1):
		trip.append("stops", {
			"cit_job": job_name, "customer_site": site, "stop_type": "Pickup",
			"planned_arrival": f"{trip_date} {7 + i}:45:00",
			"actual_arrival": f"{trip_date} {7 + i}:52:00",
			"actual_departure": f"{trip_date} {8 + i}:18:00",
			"dwell_minutes": 26, "declared_value": value, "bags_count": bags,
			"stop_status": "Completed",
		})
	trip.flags.ignore_permissions = True
	trip.insert(ignore_permissions=True)
	trip.submit()
	for row in trip.checklist:
		frappe.db.set_value("CIT Trip Checklist Item", row.name, "checked", 1)
	frappe.db.set_value("CIT Trip", trip.name, {
		"actual_start": f"{trip_date} 07:40:00",
		"actual_end": f"{trip_date} 13:20:00",
		"status": "Returned to Vault",
	})

	# --- bags, proofs of collection and custody chain
	all_bags = []
	seal_no = 100001
	for job_name, site, value, bags in jobs:
		customer = frappe.db.get_value("CIT Job", job_name, "customer")
		pod = frappe.get_doc({
			"doctype": "CIT POD", "cit_trip": trip.name, "cit_job": job_name,
			"customer_site": site, "pod_type": "Collection",
			"pod_datetime": f"{trip_date} 09:10:00",
			"signatory_name": "Branch Manager", "signatory_id": "1098765432",
			"signatory_designation": "Manager", "otp_verified": 1,
			"latitude": 24.6944, "longitude": 46.6853,
			"captured_by": crew[2], "device_id": "DEV-001", "company": company,
		})
		per_bag = flt(value) / max(bags, 1)
		for b in range(bags):
			bag = frappe.get_doc({
				"doctype": "Cash Bag", "bag_no": f"BG-{job_name[-5:]}-{b + 1:02d}",
				"seal_no": f"SL{seal_no:08d}", "customer": customer, "cit_job": job_name,
				"declared_amount": round(per_bag, 2), "currency": "SAR",
				"bag_status": "Created", "company": company,
			})
			bag.flags.ignore_permissions = True
			bag.insert(ignore_permissions=True)
			pod.append("bags", {"cash_bag": bag.name, "seal_no": bag.seal_no,
			                    "declared_amount": bag.declared_amount, "seal_intact": 1})
			all_bags.append(bag.name)
			seal_no += 1
		pod.flags.ignore_permissions = True
		pod.insert(ignore_permissions=True)
		pod.submit()

	# --- vault-in: crew hands custody to the vault
	from alphax_cit.cit_cash.doctype.cash_custody_entry.cash_custody_entry import record_custody

	for bag in all_bags:
		amount = frappe.db.get_value("Cash Bag", bag, "declared_amount")
		record_custody(cash_bag=bag, amount=amount,
		               seal_no=frappe.db.get_value("Cash Bag", bag, "seal_no"),
		               from_party_type="Employee", from_party=crew[2],
		               to_party_type="Vault", to_party=vault,
		               reference_doctype="CIT Trip", reference_name=trip.name,
		               cit_trip=trip.name, company=company)

	# --- counting session with one deliberate shortage
	session = frappe.get_doc({
		"doctype": "Counting Session", "session_date": add_days(nowdate(), -2),
		"vault": vault, "cit_trip": trip.name, "counter": crew[6], "witness": crew[1],
		"started_at": f"{add_days(nowdate(), -2)} 09:00:00",
		"ended_at": f"{add_days(nowdate(), -2)} 12:30:00", "company": company,
	})
	for i, bag in enumerate(all_bags):
		declared = flt(frappe.db.get_value("Cash Bag", bag, "declared_amount"))
		counted = declared
		counterfeit = 0
		if i == 2:
			counted = declared - 2500          # shortage
		if i == 5:
			counterfeit = 500                  # counterfeit notes
		session.append("bags", {
			"cash_bag": bag, "seal_intact": 1, "declared_amount": declared,
			"counted_amount": counted, "counterfeit_amount": counterfeit,
		})
	session.flags.ignore_permissions = True
	session.insert(ignore_permissions=True)
	session.submit()

	frappe.db.set_value("CIT Trip", trip.name, "status", "Reconciled")
	approve_demo_shortage(trip.name)

	# --- SLA breach and an incident for realism
	frappe.get_doc({
		"doctype": "CIT Incident", "incident_datetime": f"{trip_date} 10:05:00",
		"incident_category": "Delay", "severity": "Low", "cit_trip": trip.name,
		"description": "Traffic diversion on King Fahd Road delayed arrival at the second stop.",
		"company": company, "status": "Closed",
		"root_cause": "Road closure", "corrective_action": "Alternate route added to the run sheet.",
	}).insert(ignore_permissions=True)

	# --- live trips for the control room
	today = nowdate()
	live_jobs = []
	for site_label, customer, value, bags in [
		("WNB ATM Cluster — Tahlia", "Wadi National Bank", 600_000, 8),
		("RRG Granada Centre", "Riyadh Retail Group", 265_000, 5),
		("NFS Station 14 — Exit 9", "Najd Fuel Stations", 120_000, 3),
	]:
		job = frappe.get_doc({
			"doctype": "CIT Job", "customer": customer, "customer_site": sites[site_label],
			"service_type": "Cash Collection", "service_contract": contracts[customer],
			"job_date": today, "window_from": "09:00:00", "window_to": "15:00:00",
			"declared_value": value, "expected_bags": bags, "company": company,
		})
		job.flags.ignore_permissions = True
		job.insert(ignore_permissions=True)
		job.submit()
		live_jobs.append((job.name, sites[site_label], value, bags))

	live = frappe.get_doc({
		"doctype": "CIT Trip", "trip_date": today, "shift": "Morning",
		"vehicle": "CIT-4103", "vault": vault, "route": "Tahlia — Granada — Exit 9",
		"planned_start": f"{today} 08:30:00", "planned_end": f"{today} 15:00:00",
		"odometer_out": 33750, "checklist_template": "Standard Pre-Trip Check",
		"company": company,
	})
	for emp, role in [(crew[4], "Driver"), (crew[1], "Team Leader"), (crew[6], "Custodian")]:
		live.append("crew", {"employee": emp, "crew_role": role})
	for i, (job_name, site, value, bags) in enumerate(live_jobs, start=1):
		live.append("stops", {
			"cit_job": job_name, "customer_site": site, "stop_type": "Pickup",
			"planned_arrival": f"{today} {8 + i}:30:00", "declared_value": value,
			"bags_count": bags, "stop_status": "Pending",
		})
	live.flags.ignore_permissions = True
	live.insert(ignore_permissions=True)
	live.submit()
	for row in live.checklist:
		frappe.db.set_value("CIT Trip Checklist Item", row.name, "checked", 1)

	# --- a trip that cannot be dispatched, so the gate can be demonstrated
	blocked = frappe.get_doc({
		"doctype": "CIT Trip", "trip_date": today, "shift": "Night",
		"vehicle": "CIT-4104", "vault": vault, "route": "Demonstration — blocked dispatch",
		"planned_start": f"{today} 20:00:00", "planned_end": f"{today} 23:30:00",
		"odometer_out": 62400, "checklist_template": "Standard Pre-Trip Check",
		"company": company,
	})
	for emp, role in [(crew[7], "Driver"), (crew[1], "Team Leader"), (crew[3], "Guard")]:
		blocked.append("crew", {"employee": emp, "crew_role": role})
	blocked.append("stops", {
		"cit_job": live_jobs[0][0], "customer_site": live_jobs[0][1], "stop_type": "Pickup",
		"planned_arrival": f"{today} 21:00:00", "declared_value": 0, "bags_count": 0,
	})
	blocked.flags.ignore_permissions = True
	blocked.insert(ignore_permissions=True)
	blocked.submit()

	return trip.name


def approve_demo_shortage(trip_name):
	"""Clear the large shortage, leave the counterfeit open.

	This is what makes the billing run interesting in a demonstration: the trip
	was held while the shortage was open, and releases once it is approved,
	while the smaller counterfeit item stays visible on the ageing report.
	"""
	name = frappe.db.get_value("CIT Discrepancy",
	                           {"cit_trip": trip_name, "discrepancy_type": "Shortage",
	                            "docstatus": 1}, "name")
	if not name:
		return
	doc = frappe.get_doc("CIT Discrepancy", name)
	if doc.status == "Approved":
		return
	je = None
	try:
		je = doc.post_journal_entry()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "CIT demo discrepancy posting")
	doc.db_set({
		"status": "Approved", "responsible_party": "Crew", "recoverable": 1,
		"explanation": "Counted short at the vault. Recovered from the crew float "
		               "under the shortage recovery policy.",
		"approved_by": "Administrator", "approved_on": now_datetime(),
		"journal_entry": je,
	})


def seed_fleet_activity(company):
	if frappe.db.exists("CIT Fuel Entry", {"docstatus": 1}):
		return
	for plate, odo in [("CIT-4101", 48314), ("CIT-4103", 33802)]:
		doc = frappe.get_doc({
			"doctype": "CIT Fuel Entry", "vehicle": plate, "fuel_date": add_days(nowdate(), -2),
			"litres": 58, "rate": 2.33, "odometer": odo, "fuel_card_no": f"FC-{plate[-4:]}",
			"station": "Aldrees Olaya", "company": company,
		})
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
		doc.submit()

	if not frappe.db.exists("CIT Maintenance Request", {"vehicle": "CIT-4104"}):
		frappe.get_doc({
			"doctype": "CIT Maintenance Request", "vehicle": "CIT-4104",
			"request_date": nowdate(), "maintenance_type": "Preventive", "trigger": "Odometer",
			"due_date": add_days(nowdate(), 5), "due_odometer": 63000, "priority": "Normal",
			"description": "60,000 km service — brakes, filters and armour inspection.",
			"estimated_cost": 4200, "status": "Scheduled", "company": company,
		}).insert(ignore_permissions=True)

	if not frappe.db.exists("Vehicle Incident", {"vehicle": "CIT-4105"}):
		doc = frappe.get_doc({
			"doctype": "Vehicle Incident", "vehicle": "CIT-4105",
			"incident_date": add_to_date(now_datetime(), days=-9),
			"incident_type": "Breakdown", "driver": None, "location": "Exit 10, Eastern Ring Road",
			"description": "Alternator failure. Vehicle recovered to the workshop; no cash on board.",
			"downtime_hours": 26, "repair_cost": 3150, "claim_status": "Not Claimed",
			"company": company, "status": "Closed",
		})
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
		doc.submit()


def seed_billing(company, trip_name):
	if frappe.db.exists("CIT Billing Run", {"docstatus": ["<", 2]}):
		return
	run = frappe.get_doc({
		"doctype": "CIT Billing Run", "from_date": add_days(nowdate(), -30),
		"to_date": nowdate(), "posting_date": nowdate(),
		"hold_on_open_discrepancy": 1, "company": company,
	})
	run.flags.ignore_permissions = True
	run.insert(ignore_permissions=True)
	try:
		run.rate_trips()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "CIT demo billing run")
	return run.name


def seed_settings_accounts(company, vault):
	st = frappe.get_single("AlphaX CIT Settings")
	st.default_company = company
	st.default_vault = vault
	if not st.discrepancy_expense_account:
		st.discrepancy_expense_account = _account(company, ["Write Off", "Miscellaneous Expenses",
		                                                    "Indirect Expenses"], "Expense")
	if not st.discrepancy_income_account:
		st.discrepancy_income_account = _account(company, ["Other Income", "Indirect Income"],
		                                         "Income")
	if not st.default_billing_item:
		st.default_billing_item = "CIT-STOP"
	st.flags.ignore_permissions = True
	st.save(ignore_permissions=True)


# ---------------------------------------------------------------- entry points
def create_demo_data():
	"""Seed the full demo dataset. Idempotent."""
	company = _company()
	frappe.flags.in_demo = True

	seed_items()
	seed_customers()
	seed_sites()
	vault = seed_vault(company)
	seed_vehicles(company)
	crew = seed_crew(company)
	seed_geofences(vault)
	seed_gps_provider()
	seed_devices(crew)
	seed_settings_accounts(company, vault)
	contracts = seed_contracts(company)
	seed_seals(vault, crew, company)
	trip = seed_operational_cycle(company, vault, contracts, crew)
	seed_fleet_activity(company)
	seed_billing(company, trip)

	frappe.db.commit()
	summary = {dt: frappe.db.count(dt) for dt in [
		"Customer Site", "CIT Service Contract", "CIT Job", "CIT Trip", "CIT POD",
		"Cash Bag", "Cash Custody Entry", "Counting Session", "CIT Discrepancy",
		"Vehicle Compliance Document", "Geofence", "CIT Billing Run"]}
	print("AlphaX CIT demo data ready:")
	for k, v in summary.items():
		print(f"  {k:<30} {v}")
	return summary


def clear_demo_data():
	"""Remove the demo dataset. Order matters — children before parents."""
	frappe.flags.in_demo = True
	order = [
		"CIT Billing Run", "CIT SLA Breach", "CIT Discrepancy", "Counting Session",
		"CIT Alert", "Geofence Event", "GPS Position Event", "CIT Sync Event",
		"CIT POD", "CIT Incident", "Vehicle Incident", "CIT Fuel Entry",
		"CIT Maintenance Request", "Fleet Availability Log", "CIT Trip", "CIT Job",
		"Cash Custody Entry", "Cash Bag", "Seal Register", "CIT Service Contract",
		"Customer Site", "Geofence", "CIT Device", "GPS Provider", "Vehicle Compliance Document",
	]
	for doctype in order:
		for name in frappe.get_all(doctype, pluck="name"):
			try:
				frappe.delete_doc(doctype, name, force=True, ignore_permissions=True,
				                  delete_permanently=True)
			except Exception:
				pass
	for plate, *_ in VEHICLES:
		if frappe.db.exists("Vehicle", plate):
			frappe.delete_doc("Vehicle", plate, force=True, ignore_permissions=True)
	for full_name, *_ in CREW:
		emp = frappe.db.get_value("Employee", {"employee_name": full_name}, "name")
		if emp:
			frappe.delete_doc("Employee", emp, force=True, ignore_permissions=True)
	if frappe.db.exists("CIT Vault", "Riyadh Main Vault"):
		frappe.delete_doc("CIT Vault", "Riyadh Main Vault", force=True, ignore_permissions=True)
	frappe.db.commit()
	print("AlphaX CIT demo data removed.")

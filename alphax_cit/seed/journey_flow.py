"""The global start-to-end journey — the view a customer or a new user sees first.

Twelve steps on one spine, grouped into five phases. The detailed 26-stage
swimlane board still exists for operators; this is the map above it.
"""

import json

import frappe

FLOW_NAME = "CIT Journey — Start to End"

# key, label, label_ar, phase(lane), seq, colour, actor, what happens, what happens (ar),
# what the system guarantees, typical duration
STEPS = [
	("J1", "Register Customer & Sites", "تسجيل العميل والمواقع", "Commercial", 1, "#2E75B6",
	 "Commercial team",
	 "Each customer and every branch, mall or ATM you serve is recorded once, with its "
	 "location, access rules and who is allowed to hand over cash.",
	 "يتم تسجيل كل عميل وكل موقع مرة واحدة مع الموقع الجغرافي وقواعد الدخول والمخوّلين بالتسليم.",
	 "A site can only be served by a crew that knows its access protocol, and only an "
	 "authorised receiver can sign.",
	 "Once, at onboarding"),

	("J2", "Sign Contract & Set Tariff", "توقيع العقد وتحديد التسعيرة", "Commercial", 2, "#2E75B6",
	 "Commercial team",
	 "The signed contract, the sites it covers, how you charge and the service levels you "
	 "promise are captured together.",
	 "يتم إدخال العقد الموقّع والمواقع المشمولة وطريقة التسعير ومستويات الخدمة في مكان واحد.",
	 "Every completed trip is later priced from this tariff automatically — nobody types a "
	 "rate again.",
	 "Once per contract"),

	("J3", "Receive the Job", "استلام الطلب", "Operations", 3, "#1F3864",
	 "Operations desk",
	 "A customer asks for a collection, a delivery or an ATM replenishment on a date. "
	 "Scheduled work is raised the same way.",
	 "يطلب العميل استلاماً أو تسليماً أو تغذية صراف في تاريخ محدد.",
	 "A job cannot be raised against an expired contract or a site that belongs to another "
	 "customer.",
	 "Minutes"),

	("J4", "Plan the Trip", "تخطيط الرحلة", "Operations", 4, "#1F3864",
	 "Dispatcher",
	 "Jobs are grouped into a trip, a route is sequenced, and an armoured vehicle and crew "
	 "are assigned.",
	 "تُجمع الطلبات في رحلة ويتم ترتيب المسار وتعيين المركبة المصفحة والطاقم.",
	 "The same crew member cannot be booked on two trips at once, and a trip cannot run "
	 "below the minimum crew size.",
	 "15 minutes per shift"),

	("J5", "Pass the Dispatch Gate", "اجتياز بوابة الإرسال", "Operations", 5, "#1F3864",
	 "Dispatcher + system",
	 "Before the vehicle leaves, the system checks vehicle papers, crew permits, rest hours "
	 "and the pre-trip checklist.",
	 "قبل خروج المركبة يتحقق النظام من أوراق المركبة وتصاريح الطاقم وساعات الراحة وقائمة الفحص.",
	 "A vehicle with expired insurance or inspection, or a crew member with an expired "
	 "licence, clearance or weapon permit, cannot leave the yard. Overriding requires a "
	 "named approver and a written reason.",
	 "Seconds"),

	("J6", "Collect at the Site", "الاستلام من الموقع", "Field", 6, "#1F7A6C",
	 "Crew, on the mobile app",
	 "The crew scans each sealed bag, the customer confirms by signature or one-time code, "
	 "and photographs are attached.",
	 "يمسح الطاقم كل كيس مختوم ويؤكد العميل بالتوقيع أو برمز لمرة واحدة مع إرفاق الصور.",
	 "The proof of delivery carries the signatory's name and ID, the GPS position and the "
	 "exact time. It works with no network and syncs later without duplicating anything.",
	 "10 to 30 minutes per stop"),

	("J7", "Move Under Watch", "النقل تحت المراقبة", "Field", 7, "#1F7A6C",
	 "Control room",
	 "The control room sees the vehicle live against its planned route, with arrival and "
	 "departure timed automatically at each site.",
	 "تتابع غرفة التحكم المركبة مباشرة مقابل المسار المخطط مع تسجيل الوصول والمغادرة آلياً.",
	 "Route deviation, an unscheduled stop, a prolonged halt, speeding, a panic press or "
	 "loss of signal each raise an alert within minutes.",
	 "Duration of the trip"),

	("J8", "Hand Over at the Vault", "التسليم في الخزنة", "Vault & Cash", 8, "#C08A00",
	 "Vault controller",
	 "Bags are received back at the vault, seals are verified, and responsibility moves "
	 "from the crew to the vault.",
	 "تُستلم الأكياس في الخزنة ويتم التحقق من الأختام وتنتقل المسؤولية من الطاقم إلى الخزنة.",
	 "Every riyal has a named custodian at every moment. The custody record is append-only "
	 "and hash-chained — it can be reversed but never edited or deleted.",
	 "20 minutes per trip"),

	("J9", "Count and Reconcile", "العد والمطابقة", "Vault & Cash", 9, "#C08A00",
	 "Counter + witness",
	 "Each bag is counted by denomination in front of a witness, and the counted amount is "
	 "compared with what was declared.",
	 "يُعد كل كيس حسب الفئات بحضور شاهد وتتم مقارنة المبلغ المعدود بالمبلغ المصرّح به.",
	 "The counter and the witness must be two different people. Any difference, counterfeit "
	 "or damaged note is raised automatically — it cannot be absorbed quietly.",
	 "Same day"),

	("J10", "Settle Any Difference", "تسوية الفروقات", "Vault & Cash", 10, "#C08A00",
	 "Finance + management",
	 "Shortages and excesses are investigated, attributed and approved according to how "
	 "large they are.",
	 "يتم التحقق من العجز والزيادة وتحديد المسؤولية والاعتماد حسب قيمة الفرق.",
	 "Small differences clear at supervisor level; large ones require dual approval. The "
	 "approved amount posts to the ledger automatically, and nothing ages out of sight.",
	 "1 to 3 days"),

	("J11", "Price the Work", "تسعير العمل", "Finance", 11, "#0F766E",
	 "Finance",
	 "Completed and reconciled trips are priced against the contract tariff — per stop, per "
	 "bag, on value carried, per kilometre and waiting time.",
	 "تُسعَّر الرحلات المكتملة والمطابقة وفق تسعيرة العقد: لكل محطة أو كيس أو حسب القيمة أو "
	 "المسافة أو وقت الانتظار.",
	 "A trip with an unresolved cash difference is held back from billing, so you never "
	 "invoice a customer while you are still arguing about the same consignment.",
	 "Monthly, minutes"),

	("J12", "Invoice and Collect", "الفوترة والتحصيل", "Finance", 12, "#0F766E",
	 "Finance",
	 "A ZATCA-compliant invoice is issued with the backing trip detail, then receipts are "
	 "matched to the bank.",
	 "تصدر فاتورة متوافقة مع هيئة الزكاة والضريبة مع تفاصيل الرحلات ثم تُطابق المقبوضات بالبنك.",
	 "The invoice can be traced back to the trip, the stop, the bag and the signature that "
	 "started it.",
	 "Monthly"),
]

# label, label_ar, step, seq, node_type, target, view, filters, is_erpnext_standard
NODES = [
	("Customers", "العملاء", "J1", 1, "DocType", "Customer", "List", {"cit_is_cit_customer": 1}, 1),
	("Customer Sites", "مواقع العملاء", "J1", 2, "DocType", "Customer Site", "List", {}, 0),

	("Service Contracts", "عقود الخدمة", "J2", 1, "DocType", "CIT Service Contract", "List", {}, 0),
	("Expiring Soon", "قاربت الانتهاء", "J2", 2, "DocType", "CIT Service Contract", "List",
	 {"status": "Expiring"}, 0),
	("Billing Items", "أصناف الفوترة", "J2", 3, "DocType", "Item", "List", {"is_stock_item": 0}, 1),

	("New Job", "طلب جديد", "J3", 1, "DocType", "CIT Job", "New", {}, 0),
	("Open Jobs", "الطلبات المفتوحة", "J3", 2, "DocType", "CIT Job", "List", {"status": "Open"}, 0),

	("New Trip", "رحلة جديدة", "J4", 1, "DocType", "CIT Trip", "New", {}, 0),
	("Planned Trips", "الرحلات المخططة", "J4", 2, "DocType", "CIT Trip", "List",
	 {"status": "Planned"}, 0),
	("Vehicles Ready", "المركبات الجاهزة", "J4", 3, "DocType", "Vehicle", "List",
	 {"cit_availability": "In Service"}, 1),
	("Crew Available", "الطاقم المتاح", "J4", 4, "DocType", "Employee", "List",
	 {"cit_is_crew": 1, "status": "Active"}, 1),

	("Dispatched", "تم الإرسال", "J5", 1, "DocType", "CIT Trip", "List", {"status": "Dispatched"}, 0),
	("Expired Vehicle Papers", "أوراق منتهية", "J5", 2, "DocType", "Vehicle Compliance Document",
	 "List", {"status": "Expired"}, 0),
	("Expiring Papers", "قاربت الانتهاء", "J5", 3, "DocType", "Vehicle Compliance Document",
	 "List", {"status": "Expiring"}, 0),

	("Proof of Collection", "إثبات الاستلام", "J6", 1, "DocType", "CIT POD", "List",
	 {"pod_type": "Collection"}, 0),
	("Cash Bags", "أكياس النقد", "J6", 2, "DocType", "Cash Bag", "List", {}, 0),
	("Mobile Sync", "مزامنة الأجهزة", "J6", 3, "DocType", "CIT Sync Event", "List", {}, 0),

	("Live Trips", "الرحلات الجارية", "J7", 1, "DocType", "CIT Trip", "List",
	 {"status": "In Transit"}, 0),
	("Open Alerts", "التنبيهات المفتوحة", "J7", 2, "DocType", "CIT Alert", "List",
	 {"status": "Open"}, 0),
	("Incidents", "الحوادث", "J7", 3, "DocType", "CIT Incident", "List", {"status": "Open"}, 0),

	("Custody Ledger", "سجل العهدة", "J8", 1, "DocType", "Cash Custody Entry", "List",
	 {"docstatus": 1}, 0),
	("Trips at Vault", "رحلات في الخزنة", "J8", 2, "DocType", "CIT Trip", "List",
	 {"status": "Returned to Vault"}, 0),
	("Seal Register", "سجل الأختام", "J8", 3, "DocType", "Seal Register", "List", {}, 0),

	("Counting Sessions", "جلسات العد", "J9", 1, "DocType", "Counting Session", "List", {}, 0),
	("With Variance", "بها فروقات", "J9", 2, "DocType", "Counting Session", "List",
	 {"status": "Variance"}, 0),

	("Awaiting Approval", "بانتظار الاعتماد", "J10", 1, "DocType", "CIT Discrepancy", "List",
	 {"status": "Pending Approval"}, 0),
	("Discrepancy Ageing", "أعمار الفروقات", "J10", 2, "Report", "CIT Cash Discrepancy Ageing",
	 "Report", {}, 0),
	("Ledger Postings", "القيود المحاسبية", "J10", 3, "DocType", "Journal Entry", "List", {}, 1),

	("New Billing Run", "دورة فوترة جديدة", "J11", 1, "DocType", "CIT Billing Run", "New", {}, 0),
	("Billing Runs", "دورات الفوترة", "J11", 2, "DocType", "CIT Billing Run", "List", {}, 0),
	("Held Trips", "رحلات معلقة", "J11", 3, "DocType", "CIT Trip", "List",
	 {"billing_status": "Held"}, 0),

	("Sales Invoices", "فواتير المبيعات", "J12", 1, "DocType", "Sales Invoice", "List", {}, 1),
	("Payments", "المقبوضات", "J12", 2, "DocType", "Payment Entry", "List",
	 {"payment_type": "Receive"}, 1),
	("Receivables", "الذمم المدينة", "J12", 3, "Report", "Accounts Receivable", "Report", {}, 1),
]


def seed_journey_flow():
	flow = _ensure_flow()
	_ensure_nodes(flow)
	_make_default(flow)


def _ensure_flow():
	if frappe.db.exists("CIT Process Flow", FLOW_NAME):
		doc = frappe.get_doc("CIT Process Flow", FLOW_NAME)
	else:
		doc = frappe.new_doc("CIT Process Flow")
		doc.flow_name = FLOW_NAME
		doc.flow_name_ar = "رحلة نقل الأموال من البداية إلى النهاية"
		doc.description = (
			"Twelve steps from registering a customer to collecting the invoice. "
			"Each step opens the documents behind it."
		)
	doc.flow_type = "Journey"
	doc.is_default = 1

	existing = {s.stage_key for s in doc.stages}
	for (key, label, label_ar, phase, seq, colour, actor, what, what_ar,
	     guarantee, duration) in STEPS:
		if key in existing:
			continue
		doc.append("stages", {
			"stage_key": key, "stage_label": label, "stage_label_ar": label_ar,
			"lane": phase, "sequence": seq, "colour": colour, "actor": actor,
			"what_happens": what, "what_happens_ar": what_ar,
			"guarantee": guarantee, "duration_hint": duration,
		})
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	return doc.name


def _ensure_nodes(flow):
	for (label, label_ar, step, seq, ntype, target, view, filters, std) in NODES:
		if ntype == "DocType" and not frappe.db.exists("DocType", target):
			continue
		if ntype == "Report" and not frappe.db.exists("Report", target):
			continue
		if frappe.db.exists("CIT Process Node",
		                    {"process_flow": flow, "stage_key": step, "node_label": label}):
			continue
		doc = frappe.new_doc("CIT Process Node")
		doc.update({
			"node_label": label, "node_label_ar": label_ar, "process_flow": flow,
			"stage_key": step, "sequence": seq, "node_type": ntype, "default_view": view,
			"filters_json": json.dumps(filters, ensure_ascii=False) if filters else None,
			"is_erpnext_standard": std,
		})
		if ntype == "DocType":
			doc.document_type = target
		else:
			doc.report_name = target
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)


def _make_default(flow):
	"""Only the journey is the default — the detailed board stays available."""
	for other in frappe.get_all("CIT Process Flow",
	                            filters={"name": ["!=", flow], "is_default": 1}, pluck="name"):
		frappe.db.set_value("CIT Process Flow", other, "is_default", 0)
	for other in frappe.get_all("CIT Process Flow", filters={"name": ["!=", flow]}, pluck="name"):
		if not frappe.db.get_value("CIT Process Flow", other, "flow_type"):
			frappe.db.set_value("CIT Process Flow", other, "flow_type", "Detailed")

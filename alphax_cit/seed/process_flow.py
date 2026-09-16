"""Seeds the interactive process flow: 7 lanes, 26 stages, 76 document nodes.

Nodes deliberately mix AlphaX CIT documents with the standard ERPNext
documents the process depends on, so the flow chart is the operator's
navigation surface rather than a diagram kept in a separate file.
"""

import json

import frappe

FLOW_NAME = "CIT End-to-End Process"

STAGES = [
	('C1', 'Customer & Site Onboarding', 'تسجيل العميل والموقع', 'Commercial', 1, '#2E75B6'),
	('C2', 'Contract & Tariff', 'العقد والتسعيرة', 'Commercial', 2, '#2E75B6'),
	('C3', 'Service Levels & Renewal', 'مستوى الخدمة والتجديد', 'Commercial', 3, '#2E75B6'),
	('O1', 'Job Intake', 'استلام الطلب', 'Operations', 1, '#1F3864'),
	('O2', 'Trip Planning', 'تخطيط الرحلة', 'Operations', 2, '#1F3864'),
	('O3', 'Dispatch Gate', 'بوابة الإرسال', 'Operations', 3, '#1F3864'),
	('O4', 'Control Room', 'غرفة التحكم', 'Operations', 4, '#1F3864'),
	('F1', 'Pickup at Site', 'الاستلام من الموقع', 'Field', 1, '#1F7A6C'),
	('F2', 'In Transit', 'أثناء النقل', 'Field', 2, '#1F7A6C'),
	('F3', 'Delivery / Vault-in', 'التسليم / إدخال الخزنة', 'Field', 3, '#1F7A6C'),
	('V1', 'Seal & Bag Control', 'ضبط الأختام والأكياس', 'Vault & Cash', 1, '#C08A00'),
	('V2', 'Custody Chain', 'سلسلة العهدة', 'Vault & Cash', 2, '#C08A00'),
	('V3', 'Counting & Reconciliation', 'العد والمطابقة', 'Vault & Cash', 3, '#C08A00'),
	('V4', 'Discrepancy Approval', 'اعتماد الفروقات', 'Vault & Cash', 4, '#C08A00'),
	('V5', 'Bank Deposit', 'الإيداع البنكي', 'Vault & Cash', 5, '#C08A00'),
	('FL1', 'Vehicle Master', 'بيانات المركبات', 'Fleet', 1, '#7A4F9E'),
	('FL2', 'Compliance Documents', 'وثائق المركبة', 'Fleet', 2, '#7A4F9E'),
	('FL3', 'Maintenance & Fuel', 'الصيانة والوقود', 'Fleet', 3, '#7A4F9E'),
	('FL4', 'Incidents & Downtime', 'الحوادث والتوقف', 'Fleet', 4, '#7A4F9E'),
	('FI1', 'Billing Run', 'دورة الفوترة', 'Finance', 1, '#0F766E'),
	('FI2', 'Invoicing & ZATCA', 'الفوترة والهيئة', 'Finance', 2, '#0F766E'),
	('FI3', 'Collections', 'التحصيل', 'Finance', 3, '#0F766E'),
	('FI4', 'Cost & Profitability', 'التكلفة والربحية', 'Finance', 4, '#0F766E'),
	('G1', 'People & Payroll', 'الموظفون والرواتب', 'Governance', 1, '#6B7280'),
	('G2', 'Audit & Assurance', 'التدقيق والضمان', 'Governance', 2, '#6B7280'),
	('G3', 'Configuration', 'الإعدادات', 'Governance', 3, '#6B7280'),
]

NODES = [
	('Customer', 'العميل', 'C1', 1, 'DocType', 'Customer', 'List', '{"cit_is_cit_customer": 1}', 1, 'Standard ERPNext customer master, flagged for CIT service.'),
	('Customer Site', 'موقع العميل', 'C1', 2, 'DocType', 'Customer Site', 'List', '{}', 0, 'Site master: geo position, access protocol, authorised receivers, service window.'),
	('Address', 'العنوان', 'C1', 3, 'DocType', 'Address', 'List', '{}', 1, 'Standard ERPNext address linked to the site.'),
	('Contact', 'جهة الاتصال', 'C1', 4, 'DocType', 'Contact', 'List', '{}', 1, ''),
	('CIT Service Contract', 'عقد الخدمة', 'C2', 1, 'DocType', 'CIT Service Contract', 'List', '{}', 0, 'Sites, tariff lines and service levels for one customer.'),
	('Contract (legal)', 'العقد القانوني', 'C2', 2, 'DocType', 'Contract', 'List', '{}', 1, 'Standard ERPNext contract holding the signed legal document.'),
	('Service Type', 'نوع الخدمة', 'C2', 3, 'DocType', 'CIT Service Type', 'List', '{}', 0, ''),
	('Billing Item', 'صنف الفوترة', 'C2', 4, 'DocType', 'Item', 'List', '{"is_stock_item": 0}', 1, 'Standard ERPNext service items used by the tariff.'),
	('Expiring Contracts', 'عقود قاربت الانتهاء', 'C3', 1, 'DocType', 'CIT Service Contract', 'List', '{"status": "Expiring"}', 0, 'Contracts inside the notice period.'),
	('SLA Breaches', 'مخالفات مستوى الخدمة', 'C3', 2, 'DocType', 'CIT SLA Breach', 'List', '{"status": "Open"}', 0, 'Measured automatically from operational timestamps.'),
	('New Job', 'طلب جديد', 'O1', 1, 'DocType', 'CIT Job', 'New', '{}', 0, 'Raise a customer requirement for a service on a date.'),
	('Open Jobs', 'الطلبات المفتوحة', 'O1', 2, 'DocType', 'CIT Job', 'List', '{"status": "Open"}', 0, 'Jobs awaiting assignment to a trip.'),
	('Plan Trip', 'تخطيط رحلة', 'O2', 1, 'DocType', 'CIT Trip', 'New', '{}', 0, ''),
	('Planned Trips', 'الرحلات المخططة', 'O2', 2, 'DocType', 'CIT Trip', 'List', '{"status": "Planned"}', 0, ''),
	('Pre-Trip Checklist', 'قائمة الفحص', 'O2', 3, 'DocType', 'CIT Checklist Template', 'List', '{}', 0, ''),
	('Vehicles Available', 'المركبات المتاحة', 'O3', 1, 'DocType', 'Vehicle', 'List', '{"cit_availability": "In Service"}', 1, 'Standard ERPNext vehicle master extended with CIT fields.'),
	('Crew Available', 'الطاقم المتاح', 'O3', 2, 'DocType', 'Employee', 'List', '{"cit_is_crew": 1, "status": "Active"}', 1, 'Standard ERPNext employee master.'),
	('Dispatched Trips', 'الرحلات المرسلة', 'O3', 3, 'DocType', 'CIT Trip', 'List', '{"status": "Dispatched"}', 0, 'Dispatch is blocked on expired documents or crew conflicts.'),
	('Live Trips', 'الرحلات الجارية', 'O4', 1, 'DocType', 'CIT Trip', 'List', '{"status": "In Transit"}', 0, ''),
	('Open Alerts', 'التنبيهات المفتوحة', 'O4', 2, 'DocType', 'CIT Alert', 'List', '{"status": "Open"}', 0, 'Route deviation, prolonged halt, speeding, panic, signal loss.'),
	('Geofence Events', 'أحداث السياج', 'O4', 3, 'DocType', 'Geofence Event', 'List', '{}', 0, ''),
	('Position Feed', 'تغذية المواقع', 'O4', 4, 'DocType', 'GPS Position Event', 'List', '{}', 0, ''),
	('Proof of Collection', 'إثبات الاستلام', 'F1', 1, 'DocType', 'CIT POD', 'List', '{"pod_type": "Collection"}', 0, 'Signature, photos, seal numbers, GPS stamp.'),
	('Cash Bags', 'أكياس النقد', 'F1', 2, 'DocType', 'Cash Bag', 'List', '{}', 0, ''),
	('Mobile Sync Queue', 'قائمة المزامنة', 'F2', 1, 'DocType', 'CIT Sync Event', 'List', '{}', 0, 'Offline events replayed from crew devices; duplicates are rejected by design.'),
	('Quarantined Events', 'أحداث محجوزة', 'F2', 2, 'DocType', 'CIT Sync Event', 'List', '{"status": "Quarantined"}', 0, 'Events that could not be applied — resolved, never discarded.'),
	('Field Incidents', 'حوادث ميدانية', 'F2', 3, 'DocType', 'CIT Incident', 'List', '{"status": "Open"}', 0, ''),
	('Proof of Delivery', 'إثبات التسليم', 'F3', 1, 'DocType', 'CIT POD', 'List', '{"pod_type": "Delivery"}', 0, ''),
	('Trips at Vault', 'رحلات في الخزنة', 'F3', 2, 'DocType', 'CIT Trip', 'List', '{"status": "Returned to Vault"}', 0, ''),
	('Seal Register', 'سجل الأختام', 'V1', 1, 'DocType', 'Seal Register', 'List', '{}', 0, ''),
	('Vaults', 'الخزائن', 'V1', 2, 'DocType', 'CIT Vault', 'List', '{}', 0, ''),
	('Custody Ledger', 'سجل العهدة', 'V2', 1, 'DocType', 'Cash Custody Entry', 'List', '{"docstatus": 1}', 0, 'Append-only and hash-chained. Entries are reversed, never deleted.'),
	('Bags in Transit', 'أكياس قيد النقل', 'V2', 2, 'DocType', 'Cash Bag', 'List', '{"bag_status": "In Transit"}', 0, ''),
	('Counting Sessions', 'جلسات العد', 'V3', 1, 'DocType', 'Counting Session', 'List', '{}', 0, ''),
	('Sessions with Variance', 'جلسات بفروقات', 'V3', 2, 'DocType', 'Counting Session', 'List', '{"status": "Variance"}', 0, ''),
	('Open Discrepancies', 'الفروقات المفتوحة', 'V4', 1, 'DocType', 'CIT Discrepancy', 'List', '{"status": "Pending Approval"}', 0, 'Routed by value band to the configured approver role.'),
	('Discrepancy Postings', 'قيود الفروقات', 'V4', 2, 'DocType', 'Journal Entry', 'List', '{}', 1, 'Standard ERPNext journal entries created on approval.'),
	('Payment Entry', 'سند القبض', 'V5', 1, 'DocType', 'Payment Entry', 'List', '{}', 1, 'Standard ERPNext deposit and receipt posting.'),
	('Bank Transactions', 'حركات البنك', 'V5', 2, 'DocType', 'Bank Transaction', 'List', '{}', 1, ''),
	('Bank Reconciliation', 'التسوية البنكية', 'V5', 3, 'DocType', 'Bank Reconciliation Tool', 'List', '{}', 1, 'Standard ERPNext reconciliation tool.'),
	('Armoured Fleet', 'الأسطول المصفح', 'FL1', 1, 'DocType', 'Vehicle', 'List', '{}', 1, ''),
	('Vehicle Assets', 'أصول المركبات', 'FL1', 2, 'DocType', 'Asset', 'List', '{}', 1, 'Standard ERPNext asset record carrying depreciation and book value.'),
	('Availability Log', 'سجل الجاهزية', 'FL1', 3, 'DocType', 'Fleet Availability Log', 'List', '{}', 0, ''),
	('Expiring Documents', 'وثائق قاربت الانتهاء', 'FL2', 1, 'DocType', 'Vehicle Compliance Document', 'List', '{"status": "Expiring"}', 0, 'Istimara, insurance, periodic inspection, operating permit.'),
	('Expired Documents', 'وثائق منتهية', 'FL2', 2, 'DocType', 'Vehicle Compliance Document', 'List', '{"status": "Expired"}', 0, 'Vehicles with an expired document cannot be dispatched.'),
	('Maintenance Requests', 'طلبات الصيانة', 'FL3', 1, 'DocType', 'CIT Maintenance Request', 'List', '{"status": "Open"}', 0, ''),
	('Fuel Entries', 'إدخالات الوقود', 'FL3', 2, 'DocType', 'CIT Fuel Entry', 'List', '{}', 0, ''),
	('Vehicle Log', 'سجل المركبة', 'FL3', 3, 'DocType', 'Vehicle Log', 'List', '{}', 1, 'Standard ERPNext vehicle log — fuel and odometer history.'),
	('Asset Maintenance Log', 'سجل صيانة الأصل', 'FL3', 4, 'DocType', 'Asset Maintenance Log', 'List', '{}', 1, 'Standard ERPNext maintenance log.'),
	('Vehicle Incidents', 'حوادث المركبات', 'FL4', 1, 'DocType', 'Vehicle Incident', 'List', '{}', 0, ''),
	('Insurance Claims', 'مطالبات التأمين', 'FL4', 2, 'DocType', 'Vehicle Incident', 'List', '{"claim_status": "Submitted"}', 0, ''),
	('New Billing Run', 'دورة فوترة جديدة', 'FI1', 1, 'DocType', 'CIT Billing Run', 'New', '{}', 0, 'Rates completed and reconciled trips against the contract tariff.'),
	('Billing Runs', 'دورات الفوترة', 'FI1', 2, 'DocType', 'CIT Billing Run', 'List', '{}', 0, ''),
	('Held Trips', 'رحلات معلقة', 'FI1', 3, 'DocType', 'CIT Trip', 'List', '{"billing_status": "Held"}', 0, 'Held back from billing while a discrepancy is open.'),
	('Sales Invoices', 'فواتير المبيعات', 'FI2', 1, 'DocType', 'Sales Invoice', 'List', '{}', 1, 'Standard ERPNext invoice, cleared or reported to ZATCA by the compliance module.'),
	('Draft Invoices', 'فواتير مسودة', 'FI2', 2, 'DocType', 'Sales Invoice', 'List', '{"docstatus": 0}', 1, ''),
	('Accounts Receivable', 'ذمم مدينة', 'FI3', 1, 'Report', 'Accounts Receivable', 'Report', '{}', 0, 'Standard ERPNext receivables ageing.'),
	('Payments Received', 'المدفوعات المستلمة', 'FI3', 2, 'DocType', 'Payment Entry', 'List', '{"payment_type": "Receive"}', 1, ''),
	('Purchase Invoices', 'فواتير المشتريات', 'FI4', 1, 'DocType', 'Purchase Invoice', 'List', '{}', 1, 'Workshop, fuel and subcontract cost.'),
	('Expense Claims', 'مطالبات المصروفات', 'FI4', 2, 'DocType', 'Expense Claim', 'List', '{}', 1, ''),
	('Profitability Analysis', 'تحليل الربحية', 'FI4', 3, 'Report', 'Profitability Analysis', 'Report', '{}', 0, 'By cost centre and accounting dimension — vehicle, route, contract.'),
	('Employees', 'الموظفون', 'G1', 1, 'DocType', 'Employee', 'List', '{}', 1, ''),
	('Attendance', 'الحضور', 'G1', 2, 'DocType', 'Attendance', 'List', '{}', 1, ''),
	('Leave Applications', 'طلبات الإجازة', 'G1', 3, 'DocType', 'Leave Application', 'List', '{}', 1, ''),
	('Training Events', 'الدورات التدريبية', 'G1', 4, 'DocType', 'Training Event', 'List', '{}', 1, ''),
	('Payroll Entry', 'مسير الرواتب', 'G1', 5, 'DocType', 'Payroll Entry', 'List', '{}', 1, 'Standard ERPNext payroll with GOSI and WPS/Mudad file output.'),
	('Salary Slips', 'قسائم الرواتب', 'G1', 6, 'DocType', 'Salary Slip', 'List', '{}', 1, ''),
	('Custody Chain Audit', 'تدقيق سلسلة العهدة', 'G2', 1, 'DocType', 'Cash Custody Entry', 'Report', '{"docstatus": 1}', 0, 'Use the page menu to verify the hash chain end to end.'),
	('All Incidents', 'كل الحوادث', 'G2', 2, 'DocType', 'CIT Incident', 'List', '{}', 0, ''),
	('Activity Log', 'سجل النشاط', 'G2', 3, 'DocType', 'Activity Log', 'List', '{}', 1, 'Standard Frappe activity and login history.'),
	('Access Log', 'سجل الوصول', 'G2', 4, 'DocType', 'Access Log', 'List', '{}', 1, 'Document access, report execution and export events.'),
	('CIT Settings', 'إعدادات النظام', 'G3', 1, 'DocType', 'AlphaX CIT Settings', 'List', '{}', 0, 'Dispatch controls, approval bands, alert thresholds, billing holds.'),
	('Process Flow', 'خريطة العملية', 'G3', 2, 'DocType', 'CIT Process Flow', 'List', '{}', 0, ''),
	('Process Nodes', 'عقد العملية', 'G3', 3, 'DocType', 'CIT Process Node', 'List', '{}', 0, 'Every card on this board is one of these records.'),
	('Roles', 'الصلاحيات', 'G3', 4, 'DocType', 'Role', 'List', '{"role_name": ["like", "CIT%"]}', 1, ''),
	('Workflows', 'مسارات الاعتماد', 'G3', 5, 'DocType', 'Workflow', 'List', '{}', 1, 'Standard Frappe maker-checker workflow engine.'),
]


def seed_process_flow():
	flow = _ensure_flow()
	_ensure_nodes(flow)


def _ensure_flow():
	if frappe.db.exists("CIT Process Flow", FLOW_NAME):
		doc = frappe.get_doc("CIT Process Flow", FLOW_NAME)
	else:
		doc = frappe.new_doc("CIT Process Flow")
		doc.flow_name = FLOW_NAME
		doc.flow_name_ar = "دورة العمل الكاملة لنقل الأموال"
		doc.description = (
			"From customer onboarding to a reconciled, invoiced trip. "
			"Every card opens the document behind it."
		)
		doc.is_default = 1

	existing = {s.stage_key for s in doc.stages}
	for key, label, label_ar, lane, seq, colour in STAGES:
		if key in existing:
			continue
		doc.append("stages", {
			"stage_key": key, "stage_label": label, "stage_label_ar": label_ar,
			"lane": lane, "sequence": seq, "colour": colour,
		})
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	return doc.name


def _ensure_nodes(flow):
	for (label, label_ar, stage, seq, ntype, target, view, filters, std, desc) in NODES:
		if ntype == "DocType" and not frappe.db.exists("DocType", target):
			continue
		if ntype == "Report" and not frappe.db.exists("Report", target):
			continue
		if frappe.db.exists("CIT Process Node",
		                    {"process_flow": flow, "stage_key": stage, "node_label": label}):
			continue
		doc = frappe.new_doc("CIT Process Node")
		doc.update({
			"node_label": label, "node_label_ar": label_ar, "process_flow": flow,
			"stage_key": stage, "sequence": seq, "node_type": ntype,
			"default_view": view, "filters_json": filters if filters != "{}" else None,
			"description": desc, "is_erpnext_standard": std,
		})
		if ntype == "DocType":
			doc.document_type = target
		elif ntype == "Report":
			doc.report_name = target
		else:
			doc.route_override = target
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)

#!/usr/bin/env python3
"""Structural guard for alphax_cit.

Run before every commit and before packaging:

    python3 verify_tree.py

It catches the failures that only show up on a Frappe Cloud install: a DocType
JSON whose module folder does not exist, a controller class that does not match
its DocType name, a link field pointing at a DocType that is neither in this app
nor in Frappe/ERPNext core, a child table used but never defined, and a hook
target that does not resolve to a real function.
"""

import ast
import json
import os
import re
import sys

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alphax_cit")
ERRORS = []
WARNINGS = []

CORE_DOCTYPES = {
	# Frappe
	"DocType", "User", "Role", "File", "Company", "Currency", "Address", "Contact",
	"Workflow", "Workflow State", "Activity Log", "Access Log", "Custom Field", "Report",
	"Print Format", "Workspace", "Note", "ToDo", "Comment", "Version", "Email Account",
	# ERPNext
	"Customer", "Supplier", "Item", "Contract", "Sales Invoice", "Sales Invoice Item",
	"Purchase Invoice", "Payment Entry", "Journal Entry", "Bank Transaction",
	"Bank Reconciliation Tool", "Account", "Cost Center", "Branch", "Employee",
	"Attendance", "Leave Application", "Training Event", "Payroll Entry", "Salary Slip",
	"Expense Claim", "Vehicle", "Vehicle Log", "Asset", "Asset Maintenance Log",
	"Warehouse", "UOM", "Project", "Task", "Item Group", "Customer Group", "Territory",
	"Department", "Designation", "Holiday List",
}

LINK_TYPES = {"Link", "Table", "Table MultiSelect", "Dynamic Link"}


def load_doctypes():
	found = {}
	for root, _dirs, files in os.walk(APP):
		if os.sep + "doctype" + os.sep not in root:
			continue
		for f in files:
			if not f.endswith(".json"):
				continue
			path = os.path.join(root, f)
			try:
				data = json.load(open(path))
			except ValueError as e:
				ERRORS.append(f"{path}: invalid JSON ({e})")
				continue
			if data.get("doctype") != "DocType":
				continue
			found[data["name"]] = (path, data)
	return found


def check_module_folders(doctypes):
	modules_file = os.path.join(APP, "modules.txt")
	modules = [m.strip() for m in open(modules_file).read().splitlines() if m.strip()]
	slugs = {m.lower().replace(" ", "_") for m in modules}
	for name, (path, data) in doctypes.items():
		module = data.get("module")
		if module not in modules:
			ERRORS.append(f"{name}: module '{module}' is not listed in modules.txt")
		expected = module.lower().replace(" ", "_")
		if f"{os.sep}{expected}{os.sep}" not in path:
			ERRORS.append(f"{name}: JSON sits outside its module folder '{expected}'")
	for slug in slugs:
		folder = os.path.join(APP, slug)
		if not os.path.isdir(folder):
			ERRORS.append(f"modules.txt lists '{slug}' but the folder does not exist")
		elif not os.path.isfile(os.path.join(folder, "__init__.py")):
			ERRORS.append(f"module folder '{slug}' has no __init__.py")


def check_links(doctypes):
	known = set(doctypes) | CORE_DOCTYPES
	for name, (path, data) in doctypes.items():
		for f in data.get("fields", []):
			ft = f.get("fieldtype")
			if ft not in LINK_TYPES:
				continue
			if ft == "Dynamic Link":
				target = f.get("options")
				fieldnames = {x.get("fieldname") for x in data.get("fields", [])}
				if target not in fieldnames:
					ERRORS.append(
						f"{name}.{f['fieldname']}: dynamic link points at missing field '{target}'")
				continue
			opts = (f.get("options") or "").strip()
			if not opts:
				ERRORS.append(f"{name}.{f['fieldname']}: {ft} field has no options")
				continue
			if opts not in known:
				ERRORS.append(f"{name}.{f['fieldname']}: links to unknown DocType '{opts}'")
			if ft in ("Table", "Table MultiSelect"):
				child = doctypes.get(opts)
				if child and not child[1].get("istable"):
					ERRORS.append(f"{name}.{f['fieldname']}: '{opts}' is not a child table")


def check_field_order(doctypes):
	for name, (path, data) in doctypes.items():
		order = data.get("field_order") or []
		fields = [f["fieldname"] for f in data.get("fields", [])]
		if sorted(order) != sorted(fields):
			ERRORS.append(f"{name}: field_order does not match the field list")
		dupes = {f for f in fields if fields.count(f) > 1}
		if dupes:
			ERRORS.append(f"{name}: duplicate fieldnames {sorted(dupes)}")


def check_controllers(doctypes):
	"""Every DocType needs a controller module — child tables included.

	Frappe calls load_doctype_module() on import for every DocType, so a missing
	<slug>.py fails the install with "Module import failed ... No module named".
	"""
	for name, (path, data) in doctypes.items():
		folder = os.path.dirname(path)
		slug = os.path.basename(folder)
		py = os.path.join(folder, f"{slug}.py")
		if not os.path.isfile(py):
			ERRORS.append(f"{name}: controller {slug}.py is missing")
			continue
		tree = ast.parse(open(py).read())
		classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
		expected = name.replace(" ", "").replace("-", "")
		if expected not in classes:
			ERRORS.append(f"{name}: controller class '{expected}' not found in {slug}.py "
			              f"(found {classes})")
		if not os.path.isfile(os.path.join(folder, "__init__.py")):
			ERRORS.append(f"{name}: doctype folder has no __init__.py")


def check_naming(doctypes):
	"""A naming_series field with no autoname rule silently yields hash names."""
	for name, (path, data) in doctypes.items():
		fields = {f["fieldname"] for f in data.get("fields", [])}
		autoname = (data.get("autoname") or "").strip()
		if "naming_series" in fields and not autoname.startswith("naming_series"):
			ERRORS.append(f"{name}: has a naming_series field but autoname is empty")
		if autoname.startswith("naming_series") and "naming_series" not in fields:
			ERRORS.append(f"{name}: autoname uses naming_series but the field is missing")
		if data.get("istable") and autoname:
			WARNINGS.append(f"{name}: child table has an autoname rule")


def check_package_inits(doctypes):
	"""Missing __init__.py breaks the import path on a clean install."""
	for root, dirs, files in os.walk(APP):
		rel = os.path.relpath(root, APP)
		if rel.startswith(("public", "templates", ".")) or "__pycache__" in root:
			continue
		has_py = any(f.endswith(".py") for f in files)
		is_pkg_parent = os.path.basename(root) in ("doctype", "report", "page")
		if (has_py or is_pkg_parent) and "__init__.py" not in files:
			ERRORS.append(f"{os.path.join(rel)}: missing __init__.py")


def check_demo_references(doctypes):
	demo = os.path.join(APP, "demo", "demo_data.py")
	if not os.path.isfile(demo):
		return
	known = set(doctypes) | CORE_DOCTYPES
	src = open(demo).read()
	for dt in set(re.findall(r'"doctype":\s*"([^"]+)"', src)):
		if dt not in known:
			ERRORS.append(f"demo_data.py: references unknown DocType '{dt}'")


def check_submittable_fields(doctypes):
	for name, (path, data) in doctypes.items():
		if not data.get("is_submittable"):
			continue
		fields = {f["fieldname"] for f in data.get("fields", [])}
		if "amended_from" not in fields:
			WARNINGS.append(f"{name}: submittable DocType has no amended_from field")


def check_hooks():
	hooks_path = os.path.join(APP, "hooks.py")
	src = open(hooks_path).read()
	targets = re.findall(r'"(alphax_cit\.[A-Za-z0-9_.]+)"', src)
	for dotted in set(targets):
		parts = dotted.split(".")
		fn = parts[-1]
		mod_path = os.path.join(os.path.dirname(APP), *parts[:-1]) + ".py"
		if not os.path.isfile(mod_path):
			ERRORS.append(f"hooks.py: module for '{dotted}' not found at {mod_path}")
			continue
		tree = ast.parse(open(mod_path).read())
		names = {n.name for n in ast.walk(tree)
		         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
		if fn not in names:
			ERRORS.append(f"hooks.py: '{dotted}' does not resolve to a function")


def check_process_flow_nodes(doctypes, seed_file="process_flow.py"):
	"""Every node in the seeder must point at a DocType this app knows about."""
	seed = os.path.join(APP, "seed", seed_file)
	if not os.path.isfile(seed):
		return 0, 0
	src = open(seed).read()
	tree = ast.parse(src)
	known = set(doctypes) | CORE_DOCTYPES
	nodes = stages = 0
	for node in ast.walk(tree):
		if not isinstance(node, ast.Assign):
			continue
		target = node.targets[0]
		if not isinstance(target, ast.Name):
			continue
		if target.id == "NODES":
			for elt in node.value.elts:
				nodes += 1
				vals = [e.value if isinstance(e, ast.Constant) else None for e in elt.elts]
				ntype, dt = vals[4], vals[5]
				if ntype == "DocType" and dt not in known:
					ERRORS.append(
						f"{seed_file}: node '{vals[0]}' points at unknown DocType '{dt}'")
		if target.id in ("STAGES", "STEPS"):
			stages = len(node.value.elts)
	stage_keys = set()
	for node in ast.walk(tree):
		if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
				and node.targets[0].id in ("STAGES", "STEPS"):
			for elt in node.value.elts:
				stage_keys.add(elt.elts[0].value)
	for node in ast.walk(tree):
		if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
				and node.targets[0].id == "NODES":
			for elt in node.value.elts:
				key = elt.elts[2].value
				if key not in stage_keys:
					ERRORS.append(
						f"{seed_file}: node '{elt.elts[0].value}' has unknown stage '{key}'")
	return stages, nodes


def check_translations():
	"""Flag labels and messages with no Arabic string — the app ships bilingual."""
	csv_path = os.path.join(APP, "translations", "ar.csv")
	if not os.path.isfile(csv_path):
		WARNINGS.append("translations/ar.csv is missing — the app will not render in Arabic")
		return
	import csv as _csv

	with open(csv_path, encoding="utf-8") as fh:
		known = {row[0] for row in _csv.reader(fh) if row}
	skip = re.compile(
		r"^[\d.\-]+$|^[A-Z]{3,6}-\.YYYY\.-$"
		r"|^(generic_rest|webhook|wialon|traccar|custom|trip_start|stop_arrive"
		r"|stop_complete|pod_capture|incident|panic|checklist|trip_complete)$")
	strings = set()
	for root, _d, files in os.walk(APP):
		for f in files:
			path = os.path.join(root, f)
			if f.endswith(".json") and os.sep + "doctype" + os.sep in root:
				try:
					data = json.load(open(path))
				except ValueError:
					continue
				if data.get("doctype") != "DocType":
					continue
				strings.add(data["name"])
				for fld in data.get("fields", []):
					if fld.get("label"):
						strings.add(fld["label"])
					if fld.get("fieldtype") == "Select" and fld.get("options"):
						strings.update(o.strip() for o in fld["options"].split("\n") if o.strip())
			elif f.endswith(".py"):
				src = open(path, encoding="utf-8").read()
				strings.update(re.findall(r'_\(\s*"([^"\n]{3,120})"', src))
			elif f.endswith(".js"):
				src = open(path, encoding="utf-8").read()
				strings.update(re.findall(r'__\("([^"\n]{2,120})"', src))
	missing = sorted(s for s in strings if not skip.match(s) and s not in known)
	if missing:
		WARNINGS.append(
			f"{len(missing)} string(s) have no Arabic translation, first few: {missing[:5]}")
	return len(known), len(missing)


def check_www_pages():
	www = os.path.join(APP, "www")
	if not os.path.isdir(www):
		return
	for f in os.listdir(www):
		if f.endswith(".html"):
			py = os.path.join(www, f[:-5] + ".py")
			if not os.path.isfile(py):
				WARNINGS.append(f"www/{f}: no context module — the page renders with no data")
		elif f.endswith(".py") and f != "__init__.py":
			html = os.path.join(www, f[:-3] + ".html")
			if not os.path.isfile(html):
				ERRORS.append(f"www/{f}: context module with no template")


def check_no_server_scripts():
	for root, _d, files in os.walk(APP):
		for f in files:
			if f == "server_script.json" or f.endswith(".server_script.json"):
				ERRORS.append(f"{os.path.join(root, f)}: server scripts are not allowed in app code")


def main():
	doctypes = load_doctypes()
	check_module_folders(doctypes)
	check_links(doctypes)
	check_field_order(doctypes)
	check_controllers(doctypes)
	check_naming(doctypes)
	check_package_inits(doctypes)
	check_demo_references(doctypes)
	check_submittable_fields(doctypes)
	check_hooks()
	check_no_server_scripts()
	check_www_pages()
	trans = check_translations()
	stages, nodes = check_process_flow_nodes(doctypes, "process_flow.py")
	j_stages, j_nodes = check_process_flow_nodes(doctypes, "journey_flow.py")

	children = sum(1 for _n, (_p, d) in doctypes.items() if d.get("istable"))
	print(f"DocTypes         : {len(doctypes)} ({children} child tables)")
	print(f"Submittable      : {sum(1 for _n, (_p, d) in doctypes.items() if d.get('is_submittable'))}")
	print(f"Detailed board   : {stages} stages, {nodes} nodes")
	print(f"Journey view     : {j_stages} steps, {j_nodes} nodes")
	controllers = sum(
		1 for _n, (p, _d) in doctypes.items()
		if os.path.isfile(os.path.join(os.path.dirname(p),
		                               os.path.basename(os.path.dirname(p)) + ".py")))
	print(f"Controllers      : {controllers}/{len(doctypes)}")
	if trans:
		print(f"Arabic strings   : {trans[0]} translated, {trans[1]} untranslated")
	print(f"Warnings         : {len(WARNINGS)}")
	for w in WARNINGS:
		print(f"  ! {w}")
	if ERRORS:
		print(f"\nFAILED with {len(ERRORS)} error(s):")
		for e in ERRORS:
			print(f"  x {e}")
		return 1
	print("\nOK — structure is consistent.")
	return 0


if __name__ == "__main__":
	sys.exit(main())

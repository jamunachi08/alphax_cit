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
	"Warehouse", "UOM", "Project", "Task",
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
	for name, (path, data) in doctypes.items():
		if data.get("istable"):
			continue
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


def check_process_flow_nodes(doctypes):
	"""Every node in the seeder must point at a DocType this app knows about."""
	seed = os.path.join(APP, "seed", "process_flow.py")
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
					ERRORS.append(f"process flow node '{vals[0]}' points at unknown DocType '{dt}'")
		if target.id == "STAGES":
			stages = len(node.value.elts)
	stage_keys = set()
	for node in ast.walk(tree):
		if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
				and node.targets[0].id == "STAGES":
			for elt in node.value.elts:
				stage_keys.add(elt.elts[0].value)
	for node in ast.walk(tree):
		if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
				and node.targets[0].id == "NODES":
			for elt in node.value.elts:
				key = elt.elts[2].value
				if key not in stage_keys:
					ERRORS.append(f"process flow node '{elt.elts[0].value}' has unknown stage '{key}'")
	return stages, nodes


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
	check_submittable_fields(doctypes)
	check_hooks()
	check_no_server_scripts()
	stages, nodes = check_process_flow_nodes(doctypes)

	children = sum(1 for _n, (_p, d) in doctypes.items() if d.get("istable"))
	print(f"DocTypes         : {len(doctypes)} ({children} child tables)")
	print(f"Submittable      : {sum(1 for _n, (_p, d) in doctypes.items() if d.get('is_submittable'))}")
	print(f"Process flow     : {stages} stages, {nodes} nodes")
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

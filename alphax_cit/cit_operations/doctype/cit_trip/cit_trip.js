frappe.ui.form.on("CIT Trip", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;

		if (frm.doc.status === "Planned") {
			frm.add_custom_button(__("Check Dispatch"), () => {
				frappe.call({
					method: "alphax_cit.cit_operations.doctype.cit_trip.cit_trip.check_dispatch",
					args: { trip: frm.doc.name },
					callback: (r) => {
						const blockers = (r.message || {}).blockers || [];
						frappe.msgprint({
							title: __("Dispatch Check"),
							indicator: blockers.length ? "red" : "green",
							message: blockers.length
								? blockers.map((b) => `<div>&bull; ${b}</div>`).join("")
								: __("All checks passed. This trip may be dispatched."),
						});
					},
				});
			}, __("Dispatch"));

			frm.add_custom_button(__("Dispatch Trip"), () => {
				frappe.call({
					method: "alphax_cit.cit_operations.doctype.cit_trip.cit_trip.dispatch",
					args: { trip: frm.doc.name },
					freeze: true,
					callback: () => frm.reload_doc(),
					error: () => frm.reload_doc(),
				});
			}, __("Dispatch")).addClass("btn-primary");

			frm.add_custom_button(__("Dispatch with Override"), () => {
				frappe.prompt(
					[{ fieldname: "reason", fieldtype: "Small Text", label: __("Override reason"), reqd: 1 }],
					(v) => {
						frappe.call({
							method: "alphax_cit.cit_operations.doctype.cit_trip.cit_trip.dispatch",
							args: { trip: frm.doc.name, ignore_blockers: 1, override_reason: v.reason },
							freeze: true,
							callback: () => frm.reload_doc(),
						});
					},
					__("Override Dispatch Block"),
					__("Dispatch anyway")
				);
			}, __("Dispatch"));
		}

		const next = {
			Dispatched: "In Transit",
			"In Transit": "Returned to Vault",
			"Returned to Vault": "Reconciled",
			Reconciled: "Closed",
		}[frm.doc.status];

		if (next) {
			frm.add_custom_button(__("Move to {0}", [next]), () => {
				frappe.call({
					method: "alphax_cit.cit_operations.doctype.cit_trip.cit_trip.advance",
					args: { trip: frm.doc.name, status: next },
					freeze: true,
					callback: () => frm.reload_doc(),
				});
			});
		}

		if (["Returned to Vault", "Reconciled"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Counting Session"), () => {
				frappe.new_doc("Counting Session", {
					cit_trip: frm.doc.name,
					vault: frm.doc.vault,
					session_date: frappe.datetime.get_today(),
				});
			}, __("Create"));
		}

		frm.dashboard.add_indicator(
			__("Reconciliation: {0}", [frm.doc.reconciliation_status || "Pending"]),
			frm.doc.reconciliation_status === "Variance" ? "red" : "blue"
		);
	},

	checklist_template(frm) {
		if (frm.doc.checklist_template && !(frm.doc.checklist || []).length) {
			frm.trigger("validate");
			frm.save();
		}
	},
});

frappe.ui.form.on("Cash Custody Entry", {
	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Post Reversal"), () => {
				frappe.prompt(
					[{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 }],
					(v) => {
						frappe.call({
							method:
								"alphax_cit.cit_cash.doctype.cash_custody_entry.cash_custody_entry.reverse",
							args: { entry: frm.doc.name, reason: v.reason },
							freeze: true,
							callback: (r) => frappe.set_route("Form", "Cash Custody Entry", r.message),
						});
					},
					__("Reverse Custody Entry"),
					__("Post reversal")
				);
			});
			frm.dashboard.add_comment(
				__("Custody entries are append-only. Corrections are posted as reversals so the audit chain stays intact."),
				"blue", true);
		}
	},
});

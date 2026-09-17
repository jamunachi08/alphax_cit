frappe.ui.form.on("CIT Discrepancy", {
	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.status === "Pending Approval") {
			frm.add_custom_button(__("Approve"), () => {
				frappe.prompt(
					[
						{
							fieldname: "responsible_party",
							fieldtype: "Select",
							label: __("Responsible party"),
							options: ["Customer", "Crew", "Vault", "Bank", "Under Investigation"],
							default: frm.doc.responsible_party,
							reqd: 1,
						},
						{ fieldname: "recoverable", fieldtype: "Check", label: __("Recoverable") },
						{ fieldname: "explanation", fieldtype: "Small Text", label: __("Explanation"), reqd: 1 },
					],
					(v) => {
						frm.call({ doc: frm.doc, method: "approve", args: v, freeze: true,
							callback: () => frm.reload_doc() });
					},
					__("Approve Discrepancy — {0}", [frm.doc.approval_band || ""]),
					__("Approve")
				);
			}).addClass("btn-primary");
		}
		if (frm.doc.required_approver_role) {
			frm.dashboard.add_indicator(
				__("Approver: {0}", [frm.doc.required_approver_role]), "orange");
		}
	},
});

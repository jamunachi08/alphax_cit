frappe.ui.form.on("CIT Billing Run", {
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Rate Trips"), () => {
				frm.call({
					doc: frm.doc,
					method: "rate_trips",
					freeze: true,
					freeze_message: __("Selecting and pricing completed trips…"),
					callback: (r) => {
						frm.reload_doc();
						const m = r.message || {};
						frappe.show_alert({
							message: __("{0} lines rated, total {1}", [m.lines, m.total]),
							indicator: "green",
						});
					},
				});
			}).addClass("btn-primary");
		}
		if (frm.doc.trips_held) {
			frm.dashboard.add_comment(
				__("{0} trip(s) are held back from billing because a cash discrepancy is still open.",
					[frm.doc.trips_held]),
				"orange",
				true
			);
		}
	},
});

frappe.pages["cit-process-flow"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("CIT Process Flow"),
		single_column: true,
	});
	wrapper.cit_flow = new CITProcessFlow(page);
};

class CITProcessFlow {
	constructor(page) {
		this.page = page;
		this.show_counts = true;
		this.make_controls();
		this.$body = $('<div class="cit-flow-body"></div>').appendTo(this.page.main);
		this.load();
	}

	make_controls() {
		this.flow_field = this.page.add_field({
			fieldname: "process_flow",
			label: __("Flow"),
			fieldtype: "Link",
			options: "CIT Process Flow",
			change: () => this.load(),
		});
		this.page.add_field({
			fieldname: "show_counts",
			label: __("Show counts"),
			fieldtype: "Check",
			default: 1,
			change: (e) => {
				this.show_counts = !!$(e.target).prop("checked");
				this.load();
			},
		});
		this.page.set_primary_action(__("Refresh"), () => this.load(), "refresh");
		this.page.add_menu_item(__("Manage nodes"), () =>
			frappe.set_route("List", "CIT Process Node"));
		this.page.add_menu_item(__("Verify custody chain"), () => {
			frappe.call({
				method: "alphax_cit.cit_cash.doctype.cash_custody_entry.cash_custody_entry.verify_chain",
				callback: (r) => {
					const d = r.message || {};
					frappe.msgprint({
						title: __("Chain of Custody"),
						indicator: d.ok ? "green" : "red",
						message: d.ok
							? __("Verified {0} entries. Chain intact.", [d.checked])
							: __("Chain broken at {0} after {1} entries.", [d.broken_at, d.checked]),
					});
				},
			});
		});
	}

	load() {
		this.$body.html(`<div class="text-muted" style="padding:2rem">${__("Loading…")}</div>`);
		frappe.call({
			method: "alphax_cit.api.process_flow.get_flow",
			args: {
				flow: this.flow_field.get_value() || null,
				with_counts: this.show_counts ? 1 : 0,
			},
			callback: (r) => this.render(r.message),
		});
	}

	render(data) {
		if (!data || !data.stages || !data.stages.length) {
			this.$body.html(
				`<div class="text-muted" style="padding:2rem">${__(
					"No process flow is configured. Run bench migrate, or create a CIT Process Flow record."
				)}</div>`
			);
			return;
		}
		this.$body.empty();
		const header = $(`
			<div class="cit-flow-header">
				<div class="cit-flow-title">${frappe.utils.escape_html(data.flow_name || "")}</div>
				<div class="cit-flow-sub text-muted">${frappe.utils.escape_html(data.description || "")}</div>
			</div>`);
		header.appendTo(this.$body);

		const lanes = {};
		data.stages.forEach((st) => {
			(lanes[st.lane] = lanes[st.lane] || []).push(st);
		});

		Object.keys(lanes).forEach((lane) => {
			const $lane = $(`
				<div class="cit-lane">
					<div class="cit-lane-label">${frappe.utils.escape_html(lane)}</div>
					<div class="cit-lane-track"></div>
				</div>`).appendTo(this.$body);
			const $track = $lane.find(".cit-lane-track");
			lanes[lane]
				.sort((a, b) => a.sequence - b.sequence)
				.forEach((stage, i) => {
					$track.append(this.stage_card(stage));
					if (i < lanes[lane].length - 1) {
						$track.append('<div class="cit-arrow">&rarr;</div>');
					}
				});
		});
	}

	stage_card(stage) {
		const $stage = $(`
			<div class="cit-stage" style="border-top:3px solid ${stage.colour || "#1F3864"}">
				<div class="cit-stage-head">
					<span class="cit-stage-seq">${stage.sequence}</span>
					<span class="cit-stage-label">${frappe.utils.escape_html(stage.stage_label)}</span>
				</div>
				<div class="cit-nodes"></div>
			</div>`);
		const $nodes = $stage.find(".cit-nodes");
		(stage.nodes || []).forEach((node) => $nodes.append(this.node_row(node)));
		if (!(stage.nodes || []).length) {
			$nodes.append(`<div class="text-muted small">${__("No documents mapped")}</div>`);
		}
		return $stage;
	}

	node_row(node) {
		const badge = node.is_erpnext_standard
			? `<span class="cit-tag cit-tag-std" title="${__("Standard ERPNext document")}">ERPNext</span>`
			: `<span class="cit-tag cit-tag-cit" title="${__("AlphaX CIT document")}">CIT</span>`;
		const count =
			node.count === null || node.count === undefined
				? ""
				: `<span class="cit-count">${node.count}</span>`;
		const $row = $(`
			<div class="cit-node">
				<div class="cit-node-main">
					<span class="cit-node-label">${frappe.utils.escape_html(node.node_label)}</span>
					${badge}${count}
				</div>
				<div class="cit-node-actions"></div>
			</div>`);
		$row.find(".cit-node-main").on("click", () => this.open(node, node.default_view || "List"));
		if (node.description) {
			$row.attr("title", node.description);
		}
		const $act = $row.find(".cit-node-actions");
		if (node.node_type === "DocType" && node.can_create) {
			$(`<button class="btn btn-xs btn-default" title="${__("New")}">+</button>`)
				.on("click", (e) => {
					e.stopPropagation();
					this.open(node, "New");
				})
				.appendTo($act);
		}
		if (node.node_type === "DocType") {
			$(`<button class="btn btn-xs btn-default" title="${__("Report view")}">&#9636;</button>`)
				.on("click", (e) => {
					e.stopPropagation();
					this.open(node, "Report");
				})
				.appendTo($act);
		}
		return $row;
	}

	open(node, view) {
		if (node.node_type === "URL" && node.route_override) {
			window.open(node.route_override, "_blank");
			return;
		}
		if (node.node_type === "Page" && node.route_override) {
			frappe.set_route(node.route_override);
			return;
		}
		if (node.node_type === "Report") {
			frappe.set_route("query-report", node.report_name);
			return;
		}
		if (node.node_type === "Dashboard") {
			frappe.set_route("dashboard-view", node.report_name || node.node_label);
			return;
		}
		const filters = node.filters || {};
		if (view === "New") {
			frappe.new_doc(node.document_type, filters);
			return;
		}
		if (view === "Report") {
			frappe.set_route("List", node.document_type, "Report", filters);
			return;
		}
		if (view === "Calendar") {
			frappe.set_route("List", node.document_type, "Calendar");
			return;
		}
		frappe.set_route("List", node.document_type, filters);
	}
}

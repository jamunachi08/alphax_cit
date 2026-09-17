frappe.pages["cit-flow"].on_page_load = function (wrapper) {
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
		this.lang = (frappe.boot.lang || "en").startsWith("ar") ? "ar" : "en";
		this.arabic = this.lang === "ar";
		this.direction = localStorage.getItem("alphax_cit_direction") || null;
		this.make_controls();
		this.$body = $('<div class="cit-flow-body"></div>').appendTo(this.page.main);
		this.apply_direction();
		this.load();
	}

	apply_direction() {
		if (this.direction) {
			this.$body.attr("dir", this.direction);
			return;
		}
		frappe.call({
			method: "alphax_cit.api.i18n.get_direction",
			callback: (r) => {
				const d = (r.message || {}).direction || "ltr";
				this.$body.attr("dir", d);
			},
		});
	}

	toggle_direction() {
		const current = this.$body.attr("dir") || "ltr";
		this.direction = current === "rtl" ? "ltr" : "rtl";
		localStorage.setItem("alphax_cit_direction", this.direction);
		this.$body.attr("dir", this.direction);
		frappe.show_alert({
			message: __("Reading direction: {0}", [this.direction.toUpperCase()]),
			indicator: "blue",
		});
	}

	make_controls() {
		this.flow_field = this.page.add_field({
			fieldname: "process_flow",
			label: __("View"),
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
		this.page.add_menu_item(__("Arabic / English content"), () => {
			this.arabic = !this.arabic;
			this.render(this.data);
		});
		this.page.add_menu_item(__("Left to right / Right to left"), () => this.toggle_direction());
		this.page.add_menu_item(__("Switch interface language"), () => {
			const next = (frappe.boot.lang || "en").startsWith("ar") ? "en" : "ar";
			frappe.call({
				method: "alphax_cit.api.i18n.set_language",
				args: { lang: next },
				freeze: true,
				freeze_message: __("Switching language…"),
				callback: () => window.location.reload(),
			});
		});
		this.page.add_menu_item(__("Open customer view"), () =>
			window.open("/cit-journey", "_blank"));
		this.page.add_menu_item(__("Manage steps and cards"), () =>
			frappe.set_route("List", "CIT Process Node"));
		this.page.add_menu_item(__("Verify custody chain"), () => {
			frappe.call({
				method: "alphax_cit.cit_cash.doctype.cash_custody_entry.cash_custody_entry.verify_chain",
				freeze: true,
				callback: (r) => {
					const d = r.message || {};
					frappe.msgprint({
						title: __("Chain of Custody"),
						indicator: d.ok ? "green" : "red",
						message: d.ok
							? __("Verified {0} entries. The chain is intact.", [d.checked])
							: __("Chain broken at {0} after {1} entries.", [d.broken_at, d.checked]),
					});
				},
			});
		});
	}

	load() {
		this.$body.html(`<div class="cit-loading text-muted">${__("Loading…")}</div>`);
		frappe.call({
			method: "alphax_cit.api.process_flow.get_flow",
			args: {
				flow: this.flow_field.get_value() || null,
				with_counts: this.show_counts ? 1 : 0,
			},
			callback: (r) => {
				this.data = r.message;
				this.render(this.data);
			},
		});
	}

	render(data) {
		if (!data || !data.stages || !data.stages.length) {
			this.$body.html(
				`<div class="cit-loading text-muted">${__(
					"No process flow is configured. Run bench migrate, or create a CIT Process Flow record."
				)}</div>`
			);
			return;
		}
		this.$body.empty();
		this.render_header(data);
		if ((data.flow_type || "Detailed") === "Journey") {
			this.render_journey(data);
		} else {
			this.render_lanes(data);
		}
	}

	render_header(data) {
		const title = this.arabic && data.flow_name_ar ? data.flow_name_ar : data.flow_name;
		const $h = $(`
			<div class="cit-flow-header">
				<div>
					<div class="cit-flow-title">${frappe.utils.escape_html(title || "")}</div>
					<div class="cit-flow-sub text-muted">${frappe.utils.escape_html(data.description || "")}</div>
				</div>
				<div class="cit-flow-switch"></div>
			</div>`);
		const $switch = $h.find(".cit-flow-switch");
		(data.available_flows || []).forEach((f) => {
			const active = f.name === data.flow;
			$(`<button class="btn btn-xs ${active ? "btn-primary" : "btn-default"}">
					${f.flow_type === "Journey" ? __("Journey") : __("Detailed board")}
				</button>`)
				.on("click", () => {
					this.flow_field.set_value(f.name);
				})
				.appendTo($switch);
		});
		$h.appendTo(this.$body);
	}

	// ------------------------------------------------------------ journey
	render_journey(data) {
		const $wrap = $('<div class="cit-journey"></div>').appendTo(this.$body);
		let phase = null;
		data.stages.forEach((stage, i) => {
			if (stage.lane !== phase) {
				phase = stage.lane;
				$(`<div class="cit-phase" style="--phase:${stage.colour || "#1F3864"}">
						<span class="cit-phase-dot"></span>
						<span class="cit-phase-label">${frappe.utils.escape_html(phase)}</span>
					</div>`).appendTo($wrap);
			}
			$wrap.append(this.journey_step(stage, i === data.stages.length - 1));
		});
	}

	journey_step(stage, is_last) {
		const label = this.arabic && stage.stage_label_ar ? stage.stage_label_ar : stage.stage_label;
		const what = this.arabic && stage.what_happens_ar ? stage.what_happens_ar : stage.what_happens;
		const $step = $(`
			<div class="cit-step ${is_last ? "is-last" : ""}" style="--phase:${stage.colour || "#1F3864"}">
				<div class="cit-step-rail">
					<div class="cit-step-num">${stage.sequence}</div>
				</div>
				<div class="cit-step-card">
					<div class="cit-step-head">
						<div class="cit-step-title">${frappe.utils.escape_html(label || "")}</div>
						<div class="cit-step-meta"></div>
					</div>
					<div class="cit-step-what"></div>
					<div class="cit-step-guarantee"></div>
					<div class="cit-step-nodes"></div>
				</div>
			</div>`);

		const $meta = $step.find(".cit-step-meta");
		if (stage.actor) {
			$meta.append(`<span class="cit-chip">${frappe.utils.escape_html(stage.actor)}</span>`);
		}
		if (stage.duration_hint) {
			$meta.append(
				`<span class="cit-chip cit-chip-quiet">${frappe.utils.escape_html(stage.duration_hint)}</span>`
			);
		}
		if (what) {
			$step.find(".cit-step-what").text(what);
		} else {
			$step.find(".cit-step-what").remove();
		}
		if (stage.guarantee) {
			$step.find(".cit-step-guarantee").html(
				`<span class="cit-shield">&#10003;</span><span>${frappe.utils.escape_html(
					stage.guarantee
				)}</span>`
			);
		} else {
			$step.find(".cit-step-guarantee").remove();
		}

		const $nodes = $step.find(".cit-step-nodes");
		(stage.nodes || []).forEach((n) => $nodes.append(this.node_chip(n)));
		if (!(stage.nodes || []).length) {
			$nodes.remove();
		}
		return $step;
	}

	node_chip(node) {
		const label = this.arabic && node.node_label_ar ? node.node_label_ar : node.node_label;
		const count =
			node.count === null || node.count === undefined
				? ""
				: `<span class="cit-chip-count">${node.count}</span>`;
		const isNew = node.default_view === "New";
		const $chip = $(`
			<button class="cit-doc ${node.is_erpnext_standard ? "is-std" : "is-cit"} ${
			isNew ? "is-new" : ""
		}" title="${frappe.utils.escape_html(node.description || "")}">
				${isNew ? '<span class="cit-doc-plus">+</span>' : ""}
				<span>${frappe.utils.escape_html(label || "")}</span>${count}
			</button>`);
		$chip.on("click", () => this.open(node, node.default_view || "List"));
		return $chip;
	}

	// ------------------------------------------------------------ detailed board
	render_lanes(data) {
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
		const label = this.arabic && stage.stage_label_ar ? stage.stage_label_ar : stage.stage_label;
		const $stage = $(`
			<div class="cit-stage" style="border-top:3px solid ${stage.colour || "#1F3864"}">
				<div class="cit-stage-head">
					<span class="cit-stage-seq">${stage.sequence}</span>
					<span class="cit-stage-label">${frappe.utils.escape_html(label || "")}</span>
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
		const label = this.arabic && node.node_label_ar ? node.node_label_ar : node.node_label;
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
					<span class="cit-node-label">${frappe.utils.escape_html(label || "")}</span>
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

	// ------------------------------------------------------------ routing
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
		frappe.set_route("List", node.document_type, filters);
	}
}

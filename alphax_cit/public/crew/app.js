/* AlphaX CIT Crew — view controller.

   Every operational action is written to the outbox first and only then sent.
   Nothing in this file waits on the network to let the crew move on, because
   the vault basement and half the route have no signal. */
(function (w) {
  const S = w.Store, A = w.API, T = w.I18N;

  const root = document.getElementById("root");
  const tabs = document.getElementById("tabs");
  const linkState = document.getElementById("linkstate");
  const linkText = document.getElementById("linkstate-text");
  const barHeading = document.getElementById("bar-heading");
  const barSub = document.getElementById("bar-sub");
  const btnBack = document.getElementById("btn-back");
  const badge = document.getElementById("tab-outbox-count");

  const INCIDENT_CATEGORIES = ["Delay", "Customer Refusal", "Site Closed", "Breakdown",
    "Accident", "Security Event", "Shortage", "Excess", "Seal Broken", "Other"];

  let stack = [];
  let session = {};
  let syncing = false;

  // ------------------------------------------------------------ helpers
  function tpl(id) {
    return document.getElementById("tpl-" + id).content.cloneNode(true);
  }

  function money(v) {
    return (Number(v) || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
  }

  function clock(s) {
    if (!s) return "";
    const m = String(s).match(/(\d{2}):(\d{2})/);
    return m ? m[1] + ":" + m[2] : "";
  }

  function toast(msg, tone) {
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.dataset.tone = tone || "ok";
    el.hidden = false;
    clearTimeout(el._t);
    el._t = setTimeout(function () { el.hidden = true; }, 2600);
  }

  function confirmSheet(title, body, yes) {
    return new Promise(function (resolve) {
      const sheet = document.getElementById("sheet");
      document.getElementById("sheet-title").textContent = title;
      document.getElementById("sheet-body").textContent = body;
      const btnYes = document.getElementById("sheet-yes");
      const btnNo = document.getElementById("sheet-no");
      btnYes.textContent = yes;
      btnNo.textContent = T.t("cancel", "Cancel");
      sheet.hidden = false;
      function close(v) {
        sheet.hidden = true;
        btnYes.onclick = btnNo.onclick = null;
        resolve(v);
      }
      btnYes.onclick = function () { close(true); };
      btnNo.onclick = function () { close(false); };
    });
  }

  // GPS is best-effort. A stop is never blocked on a fix, but every
  // operational event carries one when the receiver has it.
  function position() {
    return new Promise(function (resolve) {
      if (!navigator.geolocation) return resolve({});
      navigator.geolocation.getCurrentPosition(
        function (p) { resolve({ latitude: p.coords.latitude, longitude: p.coords.longitude }); },
        function () { resolve({}); },
        { enableHighAccuracy: true, timeout: 6000, maximumAge: 30000 }
      );
    });
  }

  function stamp() { return new Date().toISOString().slice(0, 19).replace("T", " "); }

  // ------------------------------------------------------- link status
  function setLink(state) {
    linkState.dataset.state = state;
    linkText.textContent = T.t(state, state.charAt(0).toUpperCase() + state.slice(1));
  }

  function refreshBadge() {
    return S.pending().then(function (rows) {
      badge.hidden = rows.length === 0;
      badge.textContent = rows.length;
      return rows.length;
    });
  }

  function sync(manual) {
    if (syncing) return Promise.resolve();
    if (!navigator.onLine && !A.isDemo) {
      if (manual) toast(T.t("no_conn", "No connection. This will send later."), "bad");
      return Promise.resolve();
    }
    syncing = true;
    setLink("syncing");
    return A.flush()
      .then(function (r) {
        if (r.sent) toast(r.sent + " " + (r.sent === 1 ? "record sent" : "records sent"));
        if (r.failed) toast(r.failed + " rejected — open Outbox", "bad");
        return refreshBadge();
      })
      .then(function () { return A.pull().catch(function () { /* keep cache */ }); })
      .then(function () {
        if (current() === "trips") render("trips");
        if (current() === "outbox") render("outbox");
      })
      .catch(function () { /* stay quiet, retry on the next tick */ })
      .then(function () {
        syncing = false;
        setLink(navigator.onLine ? "online" : "offline");
      });
  }

  // ------------------------------------------------------------ router
  function current() { return stack.length ? stack[stack.length - 1].view : null; }

  function render(view, arg, replace) {
    if (replace || !stack.length) stack = [{ view: view, arg: arg }];
    else if (current() === view) stack[stack.length - 1] = { view: view, arg: arg };
    else stack.push({ view: view, arg: arg });
    draw();
  }

  function go(view, arg) { render(view, arg); }

  function back() {
    if (stack.length > 1) { stack.pop(); draw(); }
  }

  function draw() {
    const top = stack[stack.length - 1];
    root.innerHTML = "";
    btnBack.hidden = stack.length <= 1 || top.view === "trips";
    tabs.hidden = !session.user;

    const fn = VIEWS[top.view];
    if (!fn) return;
    const node = fn(top.arg);
    if (node) root.appendChild(node);
    T.apply(root);
    window.scrollTo(0, 0);

    tabs.querySelectorAll("button").forEach(function (b) {
      b.classList.toggle("is-active", b.dataset.view === top.view);
    });
  }

  // ------------------------------------------------------------- views
  const VIEWS = {};

  VIEWS.login = function () {
    const n = tpl("login");
    barHeading.textContent = "AlphaX CIT";
    barSub.textContent = "";
    const err = n.getElementById("login-err");
    n.getElementById("device-line").textContent = "Device " + A.device;

    S.kv.get("site").then(function (s) { if (s) n.getElementById("f-site").value = s; });

    n.getElementById("btn-login").onclick = function (e) {
      const btn = e.currentTarget;
      const site = document.getElementById("f-site").value.trim();
      const usr = document.getElementById("f-user").value.trim();
      const pwd = document.getElementById("f-pass").value;
      if (!site || !usr || !pwd) return;
      btn.disabled = true;
      err.hidden = true;
      A.login(site, usr, pwd)
        .then(function (info) {
          session = { user: info.user, employee: info.employee, employee_name: info.employee_name };
          return A.pull();
        })
        .then(function () { render("trips", null, true); })
        .catch(function (e2) {
          btn.disabled = false;
          err.hidden = false;
          err.textContent = e2.status === 403
            ? T.t("device_blocked", "This device is not registered. Contact the control room.")
            : T.t("bad_login", "Could not sign in. Check the address, user and password.");
        });
    };

    n.getElementById("btn-demo").onclick = function () {
      A.startDemo()
        .then(function () {
          session = { user: "demo@alphax.local", employee: "HR-EMP-00042", employee_name: "Demo crew" };
          return A.pull();
        })
        .then(function () { render("trips", null, true); });
    };
    return n;
  };

  VIEWS.trips = function () {
    const n = tpl("trips");
    barHeading.textContent = T.t("trips", "Trips");
    barSub.textContent = session.employee_name || "";
    const list = n.getElementById("trip-list");
    const empty = n.getElementById("trips-empty");

    S.trips().then(function (rows) {
      empty.hidden = rows.length > 0;
      rows.forEach(function (tr) {
        const done = (tr.stops || []).filter(function (s) { return s.status === "Completed"; }).length;
        const total = (tr.stops || []).reduce(function (a, s) { return a + (Number(s.declared_value) || 0); }, 0);
        const li = document.createElement("li");
        const btn = document.createElement("button");
        btn.className = "trip-card";
        btn.dataset.status = tr.status;
        btn.innerHTML =
          '<h3>' + tr.trip + '</h3>' +
          '<div class="meta">' +
            '<span>' + tr.status + '</span>' +
            '<span class="mono">' + (tr.vehicle || "—") + '</span>' +
            '<span>' + done + "/" + (tr.stops || []).length + " " + T.t("stops", "stops") + '</span>' +
            '<span class="num" style="margin-inline-start:auto">' + money(total) + ' SAR</span>' +
          '</div>';
        btn.onclick = function () { go("trip", tr.trip); };
        li.appendChild(btn);
        list.appendChild(li);
      });
    });
    return n;
  };

  VIEWS.trip = function (name) {
    const n = tpl("trip");
    barHeading.textContent = name;
    barSub.textContent = "";

    S.trip(name).then(function (tr) {
      if (!tr) return;
      const chip = document.getElementById("trip-status");
      chip.textContent = tr.status;
      chip.dataset.tone = tr.status === "In Transit" ? "hazard" : tr.status === "Dispatched" ? "verified" : "";
      document.getElementById("trip-vehicle").textContent = tr.vehicle || "—";
      document.getElementById("trip-name").textContent = tr.trip_date || "";
      document.getElementById("trip-stopcount").textContent = (tr.stops || []).length;
      document.getElementById("trip-value").textContent =
        money((tr.stops || []).reduce(function (a, s) { return a + (Number(s.declared_value) || 0); }, 0));
      document.getElementById("trip-vault").textContent = tr.vault || "—";

      // ---- checklist
      const cl = document.getElementById("checklist");
      const wrap = document.getElementById("checklist-wrap");
      if (!(tr.checklist || []).length) wrap.hidden = true;
      (tr.checklist || []).forEach(function (row) {
        const li = document.createElement("li");
        const b = document.createElement("button");
        b.className = "check";
        b.setAttribute("aria-pressed", row.checked ? "true" : "false");
        b.innerHTML = '<span class="box">&#10003;</span><span>' + row.label + '</span>' +
          (row.mandatory ? '<span class="req">' + T.t("required", "Required") + '</span>' : "");
        b.onclick = function () {
          row.checked = row.checked ? 0 : 1;
          b.setAttribute("aria-pressed", row.checked ? "true" : "false");
          S.putTrip(tr).then(function () {
            return S.queue("checklist", {
              trip: tr.trip,
              items: [{ label: row.label, checked: row.checked, remarks: "" }]
            }, "Check: " + row.label);
          }).then(refreshBadge).then(sync);
        };
        li.appendChild(b);
        cl.appendChild(li);
      });

      // ---- stops
      const ol = document.getElementById("stops");
      (tr.stops || []).forEach(function (st) {
        const li = document.createElement("li");
        const b = document.createElement("button");
        b.className = "stop-row";
        b.dataset.done = st.status === "Completed" ? "1" : "0";
        b.innerHTML =
          '<span class="seq">' + st.seq + '</span>' +
          '<span class="stop-body">' +
            '<span class="stop-name">' + (st.site || st.job) + '</span>' +
            '<span class="stop-meta">' + (st.stop_type || "") +
              (st.planned_arrival ? " &middot; " + clock(st.planned_arrival) : "") + '</span>' +
          '</span>' +
          '<span class="stop-amt num">' + money(st.declared_value) + '</span>';
        b.onclick = function () { go("stop", { trip: tr.trip, seq: st.seq }); };
        li.appendChild(b);
        ol.appendChild(li);
      });

      // ---- trip-level action
      const act = document.getElementById("btn-trip-action");
      const allDone = (tr.stops || []).every(function (s) { return s.status === "Completed"; });
      if (tr.status === "Dispatched") {
        act.textContent = T.t("start_trip", "Start trip");
        act.onclick = function () { startTrip(tr); };
      } else if (tr.status === "In Transit" && allDone) {
        act.textContent = T.t("complete_trip", "Complete trip and return to vault");
        act.className = "btn btn-verified";
        act.onclick = function () { completeTrip(tr); };
      } else if (tr.status === "In Transit") {
        act.textContent = T.t("complete_trip", "Complete trip and return to vault");
        act.disabled = true;
      } else {
        act.textContent = T.t("trip_closed", "Trip closed");
        act.disabled = true;
      }

      document.getElementById("btn-panic").onclick = function () { panic(tr); };
    });
    return n;
  };

  VIEWS.stop = function (arg) {
    const n = tpl("stop");
    S.trip(arg.trip).then(function (tr) {
      const st = (tr.stops || []).find(function (s) { return s.seq === arg.seq; });
      if (!st) return;
      const d = st.site_detail || {};
      barHeading.textContent = st.site || st.job;
      barSub.textContent = arg.trip;

      document.getElementById("stop-seq").textContent = st.seq;
      document.getElementById("stop-site").textContent = st.site || st.job;
      document.getElementById("stop-window").textContent =
        d.service_window_from ? T.t("window", "Service window") + " " + clock(d.service_window_from) + "–" + clock(d.service_window_to) : "";
      document.getElementById("stop-value").textContent = money(st.declared_value);
      document.getElementById("stop-bags").textContent = st.bags || 0;
      document.getElementById("stop-type").textContent = st.stop_type || "";

      // ---- site detail
      const det = document.getElementById("site-detail");
      const rows = document.createElement("dl");
      rows.className = "detail-rows";
      function addRow(label, value) {
        if (!value) return;
        const div = document.createElement("div");
        const dt = document.createElement("dt"); dt.textContent = label;
        const dd = document.createElement("dd"); dd.textContent = value;
        div.append(dt, dd);
        rows.appendChild(div);
      }
      addRow(T.t("access", "Access"), d.access_protocol);
      addRow(T.t("instructions", "Special instructions"), d.special_instructions);
      det.appendChild(rows);

      if ((d.contacts || []).length) {
        const h = document.createElement("h3");
        h.textContent = T.t("authorised_receivers", "Authorised to receive");
        det.appendChild(h);
        d.contacts.forEach(function (c) {
          const row = document.createElement("div");
          row.className = "contact";
          row.innerHTML = "<div><b>" + c.contact_name + "</b><br><span class='muted'>" +
            (c.designation || "") + " &middot; <span class='mono'>" + (c.id_number || "") + "</span></span></div>" +
            (c.authorised_to_receive ? "<span class='ok' style='margin-inline-start:auto'>&#10003;</span>" : "");
          det.appendChild(row);
        });
      }

      if (d.latitude && d.longitude) {
        const a = document.createElement("a");
        a.className = "btn btn-ghost";
        a.href = "geo:" + d.latitude + "," + d.longitude + "?q=" + d.latitude + "," + d.longitude;
        a.textContent = T.t("navigate", "Navigate to site");
        det.appendChild(a);
      }

      // ---- actions
      const bar = document.getElementById("stop-actions");
      const done = st.status === "Completed";
      const arrived = st.status === "Arrived";

      if (!done && !arrived) {
        bar.appendChild(button(T.t("arrive", "Record arrival"), "btn-primary", function () {
          arrive(tr, st);
        }));
      }
      if (!done) {
        bar.appendChild(button(
          st.stop_type === "Delivery" ? T.t("deliver", "Confirm delivery") : T.t("collect", "Confirm collection"),
          "btn-verified",
          function () { go("pod", { trip: tr.trip, seq: st.seq }); }
        ));
      }
      bar.appendChild(button(T.t("report", "Report incident"), "btn-ghost", function () {
        go("incident", { trip: tr.trip, job: st.job });
      }));
    });
    return n;
  };

  function button(label, cls, onclick) {
    const b = document.createElement("button");
    b.className = "btn " + cls;
    b.textContent = label;
    b.onclick = onclick;
    return b;
  }

  VIEWS.pod = function (arg) {
    const n = tpl("pod");
    const bags = [];
    const photos = [];

    S.trip(arg.trip).then(function (tr) {
      const st = (tr.stops || []).find(function (s) { return s.seq === arg.seq; });
      barHeading.textContent = T.t("pod_title", "Proof of delivery");
      barSub.textContent = (st.site || st.job);
      document.getElementById("pod-context").textContent =
        st.stop_type + " · " + money(st.declared_value) + " SAR · " + (st.bags || 0) + " " + T.t("bags", "bags");

      const list = document.getElementById("pod-bags");
      function addBag(seal, amount) {
        const row = { seal_no: seal || "", declared_amount: amount || "", seal_intact: 1 };
        bags.push(row);
        const li = document.createElement("li");
        li.className = "bag-row";
        li.innerHTML =
          '<div><label>' + T.t("seal_no", "Seal number") + '</label><input class="mono" inputmode="numeric"></div>' +
          '<div><label>' + T.t("amount", "Amount") + '</label><input class="num" inputmode="decimal"></div>' +
          '<button class="drop" aria-label="Remove">&times;</button>';
        const inputs = li.querySelectorAll("input");
        inputs[0].value = row.seal_no;
        inputs[1].value = row.declared_amount;
        inputs[0].oninput = function () { row.seal_no = this.value; };
        inputs[1].oninput = function () { row.declared_amount = this.value; };
        li.querySelector(".drop").onclick = function () {
          bags.splice(bags.indexOf(row), 1);
          li.remove();
        };
        list.appendChild(li);
      }
      for (let i = 0; i < (st.bags || 1); i++) addBag();
      document.getElementById("btn-add-bag").onclick = function () { addBag(); };

      const auth = document.getElementById("pod-authorised");
      const contacts = (st.site_detail && st.site_detail.contacts) || [];
      if (contacts.length) {
        auth.hidden = false;
        auth.textContent = T.t("authorised_receivers", "Authorised to receive") + ": " +
          contacts.filter(function (c) { return c.authorised_to_receive; })
                  .map(function (c) { return c.contact_name; }).join(", ");
      }

      // ---- signature pad
      const canvas = document.getElementById("sig");
      const pad = signaturePad(canvas);
      document.getElementById("btn-sig-clear").onclick = pad.clear;

      // ---- photos
      const fileInput = document.getElementById("pod-file");
      const gallery = document.getElementById("pod-photos");
      fileInput.onchange = function () {
        Array.prototype.forEach.call(fileInput.files, function (f) {
          shrink(f).then(function (dataUrl) {
            photos.push(dataUrl);
            const fig = document.createElement("figure");
            const img = document.createElement("img");
            img.src = dataUrl;
            const rm = document.createElement("button");
            rm.textContent = "×";
            rm.onclick = function () {
              photos.splice(photos.indexOf(dataUrl), 1);
              fig.remove();
            };
            fig.append(img, rm);
            gallery.appendChild(fig);
          });
        });
        fileInput.value = "";
      };

      document.getElementById("btn-pod-cancel").onclick = back;

      document.getElementById("btn-pod-save").onclick = function (e) {
        const err = document.getElementById("pod-err");
        const name = document.getElementById("pod-name").value.trim();
        if (!name) { err.hidden = false; err.textContent = T.t("need_name", "Enter who received it."); return; }
        if (pad.empty()) { err.hidden = false; err.textContent = T.t("need_sig", "A signature is required."); return; }
        err.hidden = true;
        e.currentTarget.disabled = true;

        Promise.all([
          position(),
          S.putBlob(pad.dataUrl()),
          Promise.all(photos.map(S.putBlob))
        ]).then(function (r) {
          const pos = r[0], sigId = r[1], photoIds = r[2];
          const payload = {
            trip: tr.trip, job: st.job, customer_site: st.site,
            pod_type: st.stop_type === "Delivery" ? "Delivery" : "Collection",
            timestamp: stamp(),
            signatory_name: name,
            signatory_id: document.getElementById("pod-id").value.trim(),
            employee: session.employee,
            bags: bags.filter(function (b) { return b.seal_no || b.declared_amount; }),
            signature_blob: sigId,
            photo_blobs: photoIds,
            latitude: pos.latitude, longitude: pos.longitude
          };
          return S.queue("pod_capture", payload, "POD " + (st.site || st.job))
            .then(function () {
              return S.queue("stop_complete", {
                trip: tr.trip, job: st.job, status: "Completed",
                timestamp: stamp(), latitude: pos.latitude, longitude: pos.longitude
              }, "Stop complete " + st.seq);
            })
            .then(function () {
              st.status = "Completed";
              return S.putTrip(tr);
            });
        }).then(function () {
          toast(T.t("queued_ok", "Queued. It will send when there is a signal."));
          refreshBadge();
          stack.pop();          // leave the POD form
          stack.pop();          // and the stop behind it
          draw();
          sync();
        });
      };
    });
    return n;
  };

  VIEWS.incident = function (arg) {
    const n = tpl("incident");
    barHeading.textContent = T.t("report_incident", "Report an incident");
    barSub.textContent = arg.trip || "";
    const sel = n.getElementById("inc-cat");
    INCIDENT_CATEGORIES.forEach(function (c) {
      const o = document.createElement("option");
      o.value = c; o.textContent = c;
      sel.appendChild(o);
    });
    n.getElementById("btn-inc-cancel").onclick = back;
    n.getElementById("btn-inc-save").onclick = function (e) {
      e.currentTarget.disabled = true;
      position().then(function (pos) {
        return S.queue("incident", {
          trip: arg.trip, job: arg.job,
          category: document.getElementById("inc-cat").value,
          severity: document.getElementById("inc-sev").value,
          description: document.getElementById("inc-desc").value,
          employee: session.employee,
          timestamp: stamp(),
          latitude: pos.latitude, longitude: pos.longitude
        }, "Incident: " + document.getElementById("inc-cat").value);
      }).then(function () {
        toast(T.t("queued_ok", "Queued. It will send when there is a signal."));
        refreshBadge();
        back();
        sync();
      });
    };
    return n;
  };

  VIEWS.outbox = function () {
    const n = tpl("outbox");
    barHeading.textContent = T.t("outbox", "Outbox");
    barSub.textContent = "";
    const list = n.getElementById("outbox-list");
    const empty = n.getElementById("outbox-empty");

    S.outbox().then(function (rows) {
      empty.hidden = rows.length > 0;
      rows.sort(function (a, b) { return b.seq - a.seq; }).forEach(function (ev) {
        const li = document.createElement("li");
        li.innerHTML =
          '<div class="what"><b></b><span></span></div>' +
          '<span class="state" data-s="' + ev.status + '">' + T.t(ev.status, ev.status) + '</span>';
        li.querySelector("b").textContent = ev.label;
        li.querySelector("span").textContent =
          new Date(ev.created).toLocaleString() +
          (ev.attempts ? " · " + ev.attempts + " " + T.t("attempts", "attempts") : "") +
          (ev.error ? " · " + ev.error : "");
        if (ev.status === "quarantined") {
          const retry = document.createElement("button");
          retry.className = "link-sync";
          retry.textContent = T.t("retry", "Retry");
          retry.onclick = function () {
            S.markEvent(ev.client_event_id, { status: "queued", error: null })
              .then(function () { return sync(true); })
              .then(function () { render("outbox"); });
          };
          li.appendChild(retry);
        }
        list.appendChild(li);
      });
    });
    return n;
  };

  VIEWS.settings = function () {
    const n = tpl("settings");
    barHeading.textContent = T.t("settings", "Settings");
    barSub.textContent = "";

    Promise.all([S.kv.get("user"), S.kv.get("employee"), S.kv.get("site"), S.kv.get("last_pull")])
      .then(function (r) {
        document.getElementById("set-user").textContent = r[0] || "—";
        document.getElementById("set-emp").textContent = (session.employee_name || "") + " " + (r[1] || "");
        document.getElementById("set-site").textContent = r[2] || (A.isDemo ? "Demo shift — no site" : "—");
        document.getElementById("set-device").textContent = A.device;
        document.getElementById("set-pull").textContent = r[3] ? new Date(r[3]).toLocaleString() : "—";
      });

    const seg = n.getElementById("dir-seg");
    seg.querySelectorAll("button").forEach(function (b) {
      b.classList.toggle("is-active", b.dataset.dir === T.dirPref);
      b.onclick = function () { T.setDir(b.dataset.dir); render("settings"); };
    });

    n.getElementById("btn-refresh").onclick = function () {
      A.pull().then(function () { toast(T.t("done", "Trips updated")); render("trips"); })
              .catch(function () { toast(T.t("no_conn", "No connection."), "bad"); });
    };

    n.getElementById("btn-logout").onclick = function () {
      confirmSheet(T.t("logout_confirm", "End shift?"),
                   T.t("wipe_note", "Signing out clears cached trips. Anything still in the outbox is sent first."),
                   T.t("end_shift", "End shift")).then(function (ok) {
        if (!ok) return;
        sync().then(function () { return A.logout(); })
              .then(function () { return S.wipe(); })
              .then(function () { session = {}; render("login", null, true); });
      });
    };
    return n;
  };

  // --------------------------------------------------------- trip acts
  function startTrip(tr) {
    position().then(function (pos) {
      return S.queue("trip_start", {
        trip: tr.trip, employee: session.employee, timestamp: stamp(),
        latitude: pos.latitude, longitude: pos.longitude
      }, "Start " + tr.trip);
    }).then(function () {
      tr.status = "In Transit";
      return S.putTrip(tr);
    }).then(function () {
      toast(T.t("queued_ok", "Queued."));
      refreshBadge();
      render("trip", tr.trip);
      sync();
    });
  }

  function completeTrip(tr) {
    position().then(function (pos) {
      return S.queue("trip_complete", {
        trip: tr.trip, employee: session.employee, timestamp: stamp(),
        latitude: pos.latitude, longitude: pos.longitude
      }, "Complete " + tr.trip);
    }).then(function () {
      tr.status = "Returned to Vault";
      return S.putTrip(tr);
    }).then(function () {
      refreshBadge();
      render("trips", null, true);
      sync();
    });
  }

  function arrive(tr, st) {
    position().then(function (pos) {
      return S.queue("stop_arrive", {
        trip: tr.trip, job: st.job, timestamp: stamp(),
        latitude: pos.latitude, longitude: pos.longitude
      }, "Arrived " + (st.site || st.job));
    }).then(function () {
      st.status = "Arrived";
      return S.putTrip(tr);
    }).then(function () {
      toast(T.t("queued_ok", "Queued."));
      refreshBadge();
      render("stop", { trip: tr.trip, seq: st.seq });
      sync();
    });
  }

  function panic(tr) {
    confirmSheet(T.t("panic_confirm", "Send a panic alert?"),
                 T.t("panic_body", "The control room is alerted immediately with your location."),
                 T.t("send", "Send")).then(function (ok) {
      if (!ok) return;
      position().then(function (pos) {
        return S.queue("panic", {
          trip: tr.trip, vehicle: tr.vehicle, employee: session.employee,
          timestamp: stamp(), latitude: pos.latitude, longitude: pos.longitude
        }, "PANIC " + tr.trip);
      }).then(function () {
        refreshBadge();
        // A panic goes ahead of the queue on every channel available.
        sync(true);
        toast(T.t("panic_sent", "Panic queued and sending"), "bad");
      });
    });
  }

  // ------------------------------------------------------ signature pad
  function signaturePad(canvas) {
    const ctx = canvas.getContext("2d");
    const ratio = Math.max(window.devicePixelRatio || 1, 1);
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * ratio;
    canvas.height = rect.height * ratio;
    ctx.scale(ratio, ratio);
    ctx.lineWidth = 2.2;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue("--ink").trim() || "#141A21";

    let drawing = false, dirty = false, last = null;

    function pt(e) {
      const r = canvas.getBoundingClientRect();
      const t = e.touches ? e.touches[0] : e;
      return { x: t.clientX - r.left, y: t.clientY - r.top };
    }
    function down(e) { e.preventDefault(); drawing = true; last = pt(e); }
    function move(e) {
      if (!drawing) return;
      e.preventDefault();
      const p = pt(e);
      ctx.beginPath();
      ctx.moveTo(last.x, last.y);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      last = p;
      dirty = true;
    }
    function up() { drawing = false; }

    canvas.addEventListener("pointerdown", down);
    canvas.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);

    return {
      clear: function () { ctx.clearRect(0, 0, canvas.width, canvas.height); dirty = false; },
      empty: function () { return !dirty; },
      dataUrl: function () { return canvas.toDataURL("image/png"); }
    };
  }

  // Photos are resized on the device. A 12 MP capture is 4 MB of payload that
  // will never clear a 2G handover; 1280px long edge is legible for a seal.
  function shrink(file, max) {
    max = max || 1280;
    return new Promise(function (resolve) {
      const img = new Image();
      const reader = new FileReader();
      reader.onload = function () { img.src = reader.result; };
      img.onload = function () {
        const scale = Math.min(1, max / Math.max(img.width, img.height));
        const c = document.createElement("canvas");
        c.width = Math.round(img.width * scale);
        c.height = Math.round(img.height * scale);
        c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
        resolve(c.toDataURL("image/jpeg", 0.72));
      };
      reader.readAsDataURL(file);
    });
  }

  // ------------------------------------------------------------- boot
  document.getElementById("btn-back").onclick = back;
  document.getElementById("btn-lang").onclick = function () { T.toggle(); draw(); };
  document.getElementById("btn-sync").onclick = function () { sync(true); };
  tabs.querySelectorAll("button").forEach(function (b) {
    b.onclick = function () { render(b.dataset.view, null, true); };
  });

  window.addEventListener("online", function () { setLink("online"); sync(); });
  window.addEventListener("offline", function () { setLink("offline"); });

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js", { scope: "./" }).catch(function () { /* http, or blocked */ });
  }

  T.apply(document);
  setLink(navigator.onLine ? "online" : "offline");

  A.init()
    .then(function () { return Promise.all([S.kv.get("user"), S.kv.get("employee"), S.kv.get("employee_name")]); })
    .then(function (r) {
      if (r[0]) {
        session = { user: r[0], employee: r[1], employee_name: r[2] };
        render("trips", null, true);
        sync();
      } else {
        render("login", null, true);
      }
      refreshBadge();
    });

  // Retry loop. Cheap, and the only thing standing between a completed stop
  // in a basement and the dispatcher's board.
  setInterval(function () { if (session.user) sync(); }, 60000);
})(window);

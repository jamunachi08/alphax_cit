/* Talks to alphax_cit.api.mobile on a Frappe/ERPNext v15 site.

   Served from the site itself (/assets/alphax_cit/crew/) this is same-origin
   and needs no extra configuration. Packaged as an APK the origin is
   https://localhost, so the site needs:

     bench --site <site> set-config allow_cors '["https://localhost","capacitor://localhost"]'

   Every request carries X-CIT-Device. The server rejects a device that is not
   an active CIT Device row — see alphax_cit/api/mobile.py. This is the control
   that closes the API-login gap in Frappe's 2FA, which does not apply to API
   logins. */
(function (w) {
  const S = w.Store;
  let base = "";
  let deviceId = "";
  let demo = false;

  function init() {
    return Promise.all([S.kv.get("site"), S.kv.get("device_id"), S.kv.get("demo")])
      .then(function (r) {
        base = r[0] || "";
        demo = !!r[2];
        deviceId = r[1];
        if (deviceId) return deviceId;
        deviceId = "web-" + S.uuid().slice(0, 18);
        return S.kv.set("device_id", deviceId).then(function () { return deviceId; });
      });
  }

  function url(method) { return (base ? base.replace(/\/+$/, "") : "") + "/api/method/" + method; }

  function call(method, body, opts) {
    opts = opts || {};
    return fetch(url(method), {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-CIT-Device": deviceId
      },
      body: JSON.stringify(body || {}),
      signal: opts.signal
    }).then(function (res) {
      return res.text().then(function (text) {
        let data = null;
        try { data = text ? JSON.parse(text) : null; } catch (e) { data = null; }
        if (!res.ok) {
          const err = new Error((data && (data._server_messages || data.message || data.exc_type)) || ("HTTP " + res.status));
          err.status = res.status;
          err.data = data;
          throw err;
        }
        return data && Object.prototype.hasOwnProperty.call(data, "message") ? data.message : data;
      });
    });
  }

  // ------------------------------------------------------------ auth
  function login(site, usr, pwd) {
    base = site.replace(/\/+$/, "");
    return S.kv.set("site", base)
      .then(function () { return S.kv.set("demo", false); })
      .then(function () { return call("login", { usr: usr, pwd: pwd }); })
      .then(function () {
        return call("alphax_cit.api.mobile.bootstrap", {
          device_id: deviceId,
          platform: w.Capacitor ? "Android" : "Other",
          app_version: "0.3.1",
          label: navigator.userAgent.slice(0, 120)
        });
      })
      .then(function (info) {
        demo = false;
        return Promise.all([
          S.kv.set("employee", info.employee),
          S.kv.set("employee_name", info.employee_name),
          S.kv.set("user", info.user),
          S.kv.set("company", info.company)
        ]).then(function () { return info; });
      });
  }

  function logout() {
    if (demo) return Promise.resolve();
    return call("logout").catch(function () { /* session may already be gone */ });
  }

  // ------------------------------------------------------------ pull
  function pull() {
    if (demo) return demoPull();
    return S.kv.get("employee").then(function (emp) {
      return call("alphax_cit.api.mobile.pull", { employee: emp });
    }).then(function (res) {
      return S.saveTrips(res.trips || [])
        .then(function () { return S.kv.set("last_pull", new Date().toISOString()); })
        .then(function () { return res; });
    });
  }

  // ------------------------------------------------------------ push
  // Photos and signatures live in the blob store as data URLs. They are
  // uploaded first and replaced by the returned file URL, so the sync body
  // stays small and a failed upload does not lose the event.
  function materialise(ev) {
    const p = ev.payload || {};
    const jobs = [];

    if (p.signature_blob) {
      jobs.push(S.getBlob(p.signature_blob).then(function (b) {
        if (!b) return;
        if (demo) { p.signature = "(demo signature)"; return; }
        return call("alphax_cit.api.mobile.upload_photo", {
          filename: "signature-" + ev.client_event_id.slice(0, 8) + ".png",
          data: b.data, is_private: 1
        }).then(function (r) { p.signature = r.file_url; });
      }));
    }

    (p.photo_blobs || []).forEach(function (id, i) {
      jobs.push(S.getBlob(id).then(function (b) {
        if (!b) return;
        if (demo) { (p.photos = p.photos || []).push({ photo: "(demo photo)", caption: "" }); return; }
        return call("alphax_cit.api.mobile.upload_photo", {
          filename: "pod-" + ev.client_event_id.slice(0, 8) + "-" + i + ".jpg",
          data: b.data, is_private: 1
        }).then(function (r) { (p.photos = p.photos || []).push({ photo: r.file_url, caption: "" }); });
      }));
    });

    return Promise.all(jobs).then(function () {
      const clean = Object.assign({}, p);
      delete clean.signature_blob;
      delete clean.photo_blobs;
      return Object.assign({}, ev, { payload: clean });
    });
  }

  function flush(onProgress) {
    return S.pending().then(function (rows) {
      if (!rows.length) return { sent: 0, failed: 0 };
      if (!navigator.onLine && !demo) return { sent: 0, failed: 0, offline: true };

      return rows.reduce(function (chain, ev) {
        return chain.then(function (acc) {
          if (onProgress) onProgress(ev);
          return S.markEvent(ev.client_event_id, { status: "sending" })
            .then(function () { return materialise(ev); })
            .then(function (ready) {
              if (demo) return demoPush(ready);
              return call("alphax_cit.api.mobile.push", {
                events: [{
                  client_event_id: ready.client_event_id,
                  seq: ready.seq,
                  event_type: ready.event_type,
                  payload: ready.payload
                }],
                device_id: deviceId
              });
            })
            .then(function (res) {
              const r = (res && res.results && res.results[0]) || {};
              // Applied means it landed. Duplicate now means it landed on an
              // earlier attempt — the server only says Duplicate for an event
              // whose status is Applied, so dropping it here is safe.
              // Anything else stays in the outbox with its attachments.
              if (r.status === "Applied" || r.status === "Duplicate") {
                (ev.payload.photo_blobs || []).forEach(S.dropBlob);
                if (ev.payload.signature_blob) S.dropBlob(ev.payload.signature_blob);
                acc.sent++;
                return S.dropEvent(ev.client_event_id);
              }
              acc.failed++;
              return S.markEvent(ev.client_event_id, {
                status: "quarantined",
                attempts: (ev.attempts || 0) + 1,
                error: r.error || r.status || "Rejected by server"
              });
            })
            .catch(function (e) {
              acc.failed++;
              // A transport failure stays queued and is retried. Only the
              // server saying "no" moves an event to quarantined.
              return S.markEvent(ev.client_event_id, {
                status: e.status && e.status >= 400 && e.status < 500 ? "quarantined" : "queued",
                attempts: (ev.attempts || 0) + 1,
                error: e.message
              });
            })
            .then(function () { return acc; });
        });
      }, Promise.resolve({ sent: 0, failed: 0 }));
    });
  }

  // ------------------------------------------------------------ demo
  // A self-contained shift so the app can be walked through without a site.
  // Same shapes as api/sync.py returns, so nothing in app.js branches on it.
  function demoPull() {
    const today = new Date().toISOString().slice(0, 10);
    const trips = [{
      trip: "CITT-2026-00418", status: "Dispatched", vehicle: "ARM-17",
      trip_date: today, vault: "Riyadh Central Vault",
      checklist: [
        { label: "Armour and glazing inspected", mandatory: 1, checked: 0 },
        { label: "Weapon locker sealed", mandatory: 1, checked: 0 },
        { label: "Tracker responding", mandatory: 1, checked: 0 },
        { label: "Radio check with control room", mandatory: 0, checked: 0 }
      ],
      stops: [
        {
          seq: 1, job: "CITJ-2026-01192", site: "Olaya Branch 114", stop_type: "Collection",
          planned_arrival: today + " 09:15:00", declared_value: 1450000, bags: 6, status: "Pending",
          site_detail: {
            site_name: "Olaya Branch 114", latitude: 24.6941, longitude: 46.6853,
            access_protocol: "Rear service door. Call the branch manager two minutes out; guard opens on visual confirmation only.",
            special_instructions: "Do not enter the banking hall. Handover at the cash office window.",
            service_window_from: "09:00:00", service_window_to: "11:00:00",
            contacts: [
              { contact_name: "Faisal Al-Harbi", designation: "Branch Manager", id_number: "1043298871", mobile: "+966 50 118 4420", authorised_to_receive: 1 },
              { contact_name: "Noura Al-Qahtani", designation: "Head Teller", id_number: "1088341206", mobile: "+966 55 902 7731", authorised_to_receive: 1 }
            ]
          }
        },
        {
          seq: 2, job: "CITJ-2026-01193", site: "Granada Mall Kiosk", stop_type: "Collection",
          planned_arrival: today + " 10:40:00", declared_value: 318500, bags: 2, status: "Pending",
          site_detail: {
            site_name: "Granada Mall Kiosk", latitude: 24.7749, longitude: 46.7387,
            access_protocol: "Loading bay 3. Mall security escort required between the bay and the kiosk.",
            special_instructions: "Kiosk closes for prayer. Confirm before approach.",
            service_window_from: "10:00:00", service_window_to: "12:30:00",
            contacts: [
              { contact_name: "Abdulaziz Al-Dosari", designation: "Kiosk Supervisor", id_number: "1055720193", mobile: "+966 53 447 1188", authorised_to_receive: 1 }
            ]
          }
        },
        {
          seq: 3, job: "CITJ-2026-01194", site: "Riyadh Central Vault", stop_type: "Delivery",
          planned_arrival: today + " 12:10:00", declared_value: 1768500, bags: 8, status: "Pending",
          site_detail: {
            site_name: "Riyadh Central Vault", latitude: 24.6333, longitude: 46.7167,
            access_protocol: "Airlock. One crew member at a time, weapons secured in the vehicle locker.",
            special_instructions: "Seal numbers are read back to the counting supervisor before the bag is accepted.",
            service_window_from: "08:00:00", service_window_to: "16:00:00",
            contacts: [
              { contact_name: "Mishal Al-Otaibi", designation: "Vault Supervisor", id_number: "1029948812", mobile: "+966 56 330 9014", authorised_to_receive: 1 }
            ]
          }
        }
      ]
    }];
    return S.saveTrips(trips)
      .then(function () { return S.kv.set("last_pull", new Date().toISOString()); })
      .then(function () { return { trips: trips, demo: true }; });
  }

  function demoPush(ev) {
    // Mirrors the server contract, including the duplicate reply.
    return new Promise(function (resolve) {
      setTimeout(function () {
        resolve({ results: [{ client_event_id: ev.client_event_id, status: "Applied",
                              result_doctype: "CIT Trip", result_name: ev.payload.trip || "" }] });
      }, 220);
    });
  }

  function startDemo() {
    demo = true;
    base = "";
    return Promise.all([
      S.kv.set("demo", true),
      S.kv.set("site", ""),
      S.kv.set("employee", "HR-EMP-00042"),
      S.kv.set("employee_name", "Demo crew"),
      S.kv.set("user", "demo@alphax.local"),
      S.kv.set("company", "Demo CIT")
    ]);
  }

  w.API = {
    init: init,
    login: login, logout: logout,
    pull: pull, flush: flush,
    startDemo: startDemo,
    get isDemo() { return demo; },
    get device() { return deviceId; },
    get base() { return base; }
  };
})(window);

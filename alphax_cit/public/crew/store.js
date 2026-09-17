/* Local durable store.
   Four object stores:
     outbox   — events waiting for alphax_cit.api.sync.push, keyed by client_event_id
     trips    — the last successful pull(), so the app opens with no signal
     blobs    — photos and signatures, kept out of the event body until upload
     kv       — session, employee, device id, cursor timestamps
   Nothing here talks to the network. api.js owns that. */
(function (w) {
  const DB_NAME = "alphax-cit-crew";
  const DB_VER = 1;
  let dbp = null;

  function open() {
    if (dbp) return dbp;
    dbp = new Promise(function (resolve, reject) {
      const req = indexedDB.open(DB_NAME, DB_VER);
      req.onupgradeneeded = function () {
        const db = req.result;
        if (!db.objectStoreNames.contains("outbox")) {
          const s = db.createObjectStore("outbox", { keyPath: "client_event_id" });
          s.createIndex("seq", "seq");
          s.createIndex("status", "status");
        }
        if (!db.objectStoreNames.contains("trips")) db.createObjectStore("trips", { keyPath: "trip" });
        if (!db.objectStoreNames.contains("blobs")) db.createObjectStore("blobs", { keyPath: "id" });
        if (!db.objectStoreNames.contains("kv")) db.createObjectStore("kv");
      };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
    return dbp;
  }

  function tx(store, mode, fn) {
    return open().then(function (db) {
      return new Promise(function (resolve, reject) {
        const t = db.transaction(store, mode);
        const s = t.objectStore(store);
        let out;
        try { out = fn(s); } catch (e) { reject(e); return; }
        t.oncomplete = function () { resolve(out && out.result !== undefined ? out.result : out); };
        t.onerror = function () { reject(t.error); };
        t.onabort = function () { reject(t.error); };
      });
    });
  }

  function all(store) {
    return tx(store, "readonly", function (s) { return s.getAll(); })
      .then(function (r) { return r || []; });
  }

  // ------------------------------------------------------------- kv
  const kv = {
    get: function (k) { return tx("kv", "readonly", function (s) { return s.get(k); }); },
    set: function (k, v) { return tx("kv", "readwrite", function (s) { s.put(v, k); }); },
    del: function (k) { return tx("kv", "readwrite", function (s) { s.delete(k); }); }
  };

  // --------------------------------------------------------- outbox
  // A monotonic sequence per device. The server applies events in seq order
  // and dedupes on client_event_id, so a retry after a half-finished sync is
  // always safe — see alphax_cit/api/sync.py.
  function nextSeq() {
    return kv.get("seq").then(function (n) {
      const next = (n || 0) + 1;
      return kv.set("seq", next).then(function () { return next; });
    });
  }

  function uuid() {
    if (crypto.randomUUID) return crypto.randomUUID();
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      const r = (Math.random() * 16) | 0;
      return (c === "x" ? r : ((r & 0x3) | 0x8)).toString(16);
    });
  }

  function queue(event_type, payload, label) {
    return nextSeq().then(function (seq) {
      const ev = {
        client_event_id: uuid(),
        seq: seq,
        event_type: event_type,
        payload: payload || {},
        label: label || event_type,
        status: "queued",
        attempts: 0,
        error: null,
        created: new Date().toISOString()
      };
      return tx("outbox", "readwrite", function (s) { s.put(ev); }).then(function () { return ev; });
    });
  }

  function pending() {
    return all("outbox").then(function (rows) {
      return rows.filter(function (r) { return r.status === "queued" || r.status === "sending"; })
                 .sort(function (a, b) { return a.seq - b.seq; });
    });
  }

  function markEvent(id, patch) {
    return tx("outbox", "readwrite", function (s) {
      const g = s.get(id);
      g.onsuccess = function () {
        const row = g.result;
        if (!row) return;
        Object.assign(row, patch);
        s.put(row);
      };
    });
  }

  function dropEvent(id) { return tx("outbox", "readwrite", function (s) { s.delete(id); }); }

  // ---------------------------------------------------------- trips
  function saveTrips(list) {
    return open().then(function (db) {
      return new Promise(function (resolve, reject) {
        const t = db.transaction("trips", "readwrite");
        const s = t.objectStore("trips");
        s.clear();
        (list || []).forEach(function (tr) { s.put(tr); });
        t.oncomplete = resolve;
        t.onerror = function () { reject(t.error); };
      });
    });
  }

  function trips() { return all("trips"); }
  function trip(name) { return tx("trips", "readonly", function (s) { return s.get(name); }); }
  function putTrip(tr) { return tx("trips", "readwrite", function (s) { s.put(tr); }); }

  // ---------------------------------------------------------- blobs
  function putBlob(dataUrl) {
    const id = uuid();
    return tx("blobs", "readwrite", function (s) { s.put({ id: id, data: dataUrl }); })
      .then(function () { return id; });
  }
  function getBlob(id) { return tx("blobs", "readonly", function (s) { return s.get(id); }); }
  function dropBlob(id) { return tx("blobs", "readwrite", function (s) { s.delete(id); }); }

  function wipe() {
    return open().then(function (db) {
      return Promise.all(["trips", "blobs", "kv"].map(function (name) {
        return new Promise(function (res, rej) {
          const t = db.transaction(name, "readwrite");
          t.objectStore(name).clear();
          t.oncomplete = res;
          t.onerror = function () { rej(t.error); };
        });
      }));
    });
  }

  w.Store = {
    kv: kv, uuid: uuid,
    queue: queue, pending: pending, outbox: function () { return all("outbox"); },
    markEvent: markEvent, dropEvent: dropEvent,
    saveTrips: saveTrips, trips: trips, trip: trip, putTrip: putTrip,
    putBlob: putBlob, getBlob: getBlob, dropBlob: dropBlob,
    wipe: wipe
  };
})(window);

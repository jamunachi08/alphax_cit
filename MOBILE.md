# AlphaX CIT — crew application

One codebase, two delivery channels. The PWA under `alphax_cit/public/crew/` is
the product; the Android project in `mobile/` wraps the same files so the fleet
can be managed through MDM and the handset can hold a wake lock through a long
upload.

RFP §9 in full, plus the §7 control that Frappe's own two-factor authentication
cannot provide on its own.

---

## 1. What the crew sees

| RFP §9 | Where |
|---|---|
| 9.1 Viewing assigned trips | Trip list and trip detail, served from IndexedDB, opens with no signal |
| 9.2 Trip start and completion | `trip_start` / `trip_complete`, odometer and position captured |
| 9.3 Collection and delivery confirmation | `stop_arrive`, `stop_complete` per stop |
| 9.4 Digital signatures | Pointer-event canvas, uploaded as a private PNG File |
| 9.5 Document/photo upload | Camera capture, resized to 1280 px on the handset before it is queued |
| 9.6 Incident reporting | All ten `CIT Incident` categories, plus a panic button on every trip |
| 9.7 GPS/location integration | Position attached to every operational event; `mobile.heartbeat` feeds the same GPS pipeline as a vehicle tracker |
| 9.8 Offline with automatic sync | Durable outbox, monotonic `seq`, `client_event_id` dedupe, quarantine and retry |

The crew can also read the site access protocol, the special instructions and
the list of people authorised to receive a bag before they get out of the
vehicle. That is the part that prevents a handover to the wrong person, and it
comes from `Customer Site` and `CIT Site Contact` with no extra data entry.

---

## 2. Install the PWA

The crew app ships inside the Frappe app. There is nothing separate to host.

```bash
cd ~/frappe-bench
bench get-app alphax_cit /path/to/alphax_cit
bench --site <site> install-app alphax_cit
bench --site <site> migrate
bench build --app alphax_cit
```

Then on the handset, open:

```
https://<site>/crew
```

Chrome and Safari both offer "Add to home screen". After the first load the
shell is cached and the app opens offline.

Requirements:

- **HTTPS.** Service workers, geolocation and the camera are all refused on
  plain HTTP. There is no way round this and no reason to want one.
- **An Employee record linked to the user**, with one of the roles `CIT Crew`,
  `CIT Dispatcher`, `CIT Control Room` or `CIT Manager`.

### Enrolling a handset

The first call after login registers the device and then refuses it:

> This device has been submitted for approval. The control room must enable it.

A dispatcher opens **CIT Device**, finds the new row, confirms it belongs to the
crew member standing in front of them, and ticks **Active**. The crew member
signs in again and is through.

To skip the approval step during a pilot, tick **AlphaX CIT Settings → Activate
New Devices Automatically**. Turn it back off before go-live.

---

## 3. Why the device register exists

Frappe's two-factor authentication does not apply to API logins. The crew app
is an API client. Without a second control, a leaked password is a complete
bypass of the second factor against the endpoints that write custody records.

`alphax_cit/api/mobile.py` closes that:

- Every call requires an `X-CIT-Device` header matching an **active** `CIT Device`.
- An unknown handset is registered inactive and cannot post until a human enables it.
- A handset bound to one employee and used by another is logged and refused.
- `push()` overwrites the client-supplied `employee` with the session's own
  employee, so a handset cannot post work in someone else's name.
- `AlphaX CIT Settings → Enable Mobile API` cuts every handset at once during an
  incident, without touching user accounts.

Revoking a lost handset is one checkbox on one row. That is the operational
property that matters at 02:00.

**This is a compensating control, not a replacement for 2FA.** Still enable
Frappe 2FA for desk users, and still keep the API surface off the public
internet where you can.

---

## 4. Build the APK

The Android project is generated and committed under `mobile/`. It cannot be
compiled without the Android SDK and Google's Maven repository.

### In CI (recommended)

`.github/workflows/android.yml` is ready. Add four repository secrets:

| Secret | What |
|---|---|
| `ANDROID_KEYSTORE_B64` | `base64 -w0 release.keystore` |
| `ANDROID_KEYSTORE_PASSWORD` | keystore password |
| `ANDROID_KEY_ALIAS` | key alias, default `alphax-cit` |
| `ANDROID_KEY_PASSWORD` | key password |

Create the keystore once and keep it somewhere you will still have in five
years. Losing it means every handset must uninstall and reinstall.

```bash
keytool -genkeypair -v \
  -keystore release.keystore \
  -alias alphax-cit \
  -keyalg RSA -keysize 4096 -validity 10000 \
  -dname "CN=AlphaX CIT Crew, O=Neotec Integrated Solutions, C=SA"
```

Push a tag (`v0.4.0`) and collect `alphax-cit-crew-apk` from the run's
artifacts. It contains both the APK for sideloading and the AAB for Play.

### On a workstation

```bash
cd mobile
npm ci
npx cap sync android
cd android && ./gradlew assembleRelease
# android/app/build/outputs/apk/release/app-release.apk
```

Needs **JDK 17**, the Android SDK (API 34) and network access to
`dl.google.com` and `services.gradle.org`.

JDK 21 will not work. This project is on AGP 8.2.1 / Gradle 8.2.1, and Gradle
did not support Java 21 until 8.5. Raise both together or leave both alone.

### Point the app at a site

The APK ships the same login screen as the PWA, so the site address is typed
once by the crew member. To pin it instead, set `server.url` in
`capacitor.config.json` and rebuild.

Because the APK's origin is `https://localhost`, the site must allow it:

```bash
bench --site <site> set-config allow_cors '["https://localhost","capacitor://localhost"]'
```

The PWA served from `/crew` is same-origin and needs none of this.

---

## 5. The sync contract

An event is a row in the outbox until the server confirms it.

```json
{
  "client_event_id": "5b1f…",
  "seq": 42,
  "event_type": "stop_complete",
  "payload": { "trip": "CITT-2026-00418", "job": "CITJ-2026-01192", "…": "…" }
}
```

- `seq` is monotonic per device. The server applies a batch in `seq` order.
- `client_event_id` is generated on the handset. Replaying an applied event
  returns `Duplicate` with no side effects, so a sync that dies halfway is
  always safe to retry.
- A handler that throws rolls back to a savepoint and the event is
  **quarantined**, visible in the crew's Outbox tab with a Retry button and in
  `CIT Sync Event` on the desk.
- A transport failure leaves the event **queued**. Only the server saying no
  moves it to quarantined.
- Photos and signatures upload first and are replaced by their file URL, so a
  failed image upload never costs the crew a whole POD.

Retry runs on a 60-second timer, on every `online` event, and on every action.

---

## 6. Security model of the sync path

`alphax_cit/api/sync.py` is **not whitelisted**. `push` and `pull` are plain
Python functions; the only route in is `alphax_cit.api.mobile`, which
authorises the handset first. Re-adding `@frappe.whitelist()` to either one
re-opens the bypass, so don't.

On top of the device check, every event is tested against the roster:
`assert_own_trip()` refuses an event whose trip does not list the session's
employee in `CIT Trip Crew`. Dispatchers, control room and managers are
exempt, because correcting other people's work from the desk is their job. A
refused event is logged as a security event and returned as `Rejected` — it is
never silently dropped.

### Duplicate means applied, and nothing else

The server returns `Duplicate` only when the earlier attempt reached status
`Applied`. An event that was quarantined, or that died between writing its log
row and running its handler, is re-executed on the same `CIT Sync Event` row
and its `retry_count` is incremented.

This matters because the handset deletes an event from its outbox as soon as
it sees `Applied` or `Duplicate`. If `Duplicate` were returned for a
quarantined event, every Retry would silently destroy the crew's only copy of
a collection that the server never recorded.

---

## 7. What is still open

- **No automated tests.** The same gap the rest of the app has. The sync
  idempotency path and the device guard are the two that deserve tests first.
- **No background sync.** The app syncs when it is open. A stop completed in a
  basement reaches the desk when the crew next opens the app in signal, not
  before. Background Sync API would narrow this on Android; iOS will not.
- **No push notification** for a re-routed trip. The crew pulls, dispatch cannot
  push.
- **No biometric re-auth** on the handset before a POD is signed.
- **Certificate pinning is not on.** Worth adding for the APK before go-live.

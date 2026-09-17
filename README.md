# AlphaX CIT

Cash in Transit operations, chain of custody, fleet compliance and contract billing for
**Frappe / ERPNext v15**.

Built by Neotec Integrated Solutions to close every requirement scored **2 — Partially
Supported** or **3 — Requires Customization** in the CIT Requirement Compliance Matrix
(67 of 96 requirements). Requirements scored **1 — Fully Supported** are met by standard
ERPNext and are surfaced through the process flow rather than rebuilt.

Version **0.3.0**.

### 0.3.0 — bilingual with a direction switch
- **`translations/ar.csv`** — 772 Arabic strings covering every DocType name, field label,
  select option, role, report, workspace card and runtime message in the app. Authored,
  not machine-translated. `verify_tree.py` fails the build if a new string has no Arabic.
- **Reading direction is a choice, not a consequence of language.** `AlphaX CIT Settings →
  Interface Direction`: Automatic (Arabic = RTL), or force Left-to-Right / Right-to-Left
  for the whole site. Individual users can flip it for their own browser from the flow
  page menu.
- One-click **Switch interface language** on the flow page — no trip to My Settings.
- Custom CSS moved to logical properties (`border-inline-start`) with explicit RTL rules;
  numerals stay LTR inside Arabic text.
- `/cit-journey` honours `?lang=ar` and `?dir=ltr` independently, with both toggles on the
  page.
- New **CIT POD Bilingual** print format: Arabic and English on every label, so the
  customer signs a document they can read.

### 0.2.1 — the journey as a shareable page
- New website route **`/cit-journey`** renders the same twelve steps as a clean,
  printable page — for customers, new joiners and proposals. Rendered from the journey
  flow record, so it cannot drift from the desk view.
- `?lang=ar` switches the page to Arabic; the browser print dialog produces a tidy PDF.
- Public access is off by default. Tick **AlphaX CIT Settings → Publish Journey Page
  Publicly** to let the link be opened without a login.
- Workspace shortcut and a desk-page menu item both open it.

### 0.2.0 — one global journey view
- **`CIT Journey — Start to End`**: twelve steps on a single spine, grouped into five
  phases, seeded as the default flow. Each step states who does it, what happens, what the
  system guarantees and the typical duration — in English and Arabic.
- The 26-stage swimlane board is unchanged and one click away via the view switch.
- `CIT Process Stage` gained `actor`, `what_happens`, `what_happens_ar`, `guarantee` and
  `duration_hint`; `CIT Process Flow` gained `flow_type` (Journey or Detailed).
- Page rewritten with two renderers, an Arabic toggle and a mobile-friendly layout.

### 0.1.1 — install fixes + demo data
- Controller modules generated for all 17 child tables. Frappe calls
  `load_doctype_module()` for every DocType on import, including child tables, so a
  missing `<slug>.py` aborted the install. `verify_tree.py` now checks all 48.
- `autoname: "naming_series:"` set on the 15 DocTypes that carry a `naming_series`
  field. Without it Frappe falls back to hash names.
- `before_install` hook seeds the 10 CIT roles **before** the DocType JSONs are
  imported, because their permission rows, the desk page and the reports all link to
  those roles.
- `Company` field added to `CIT Vault`; discrepancy journal entries now resolve the
  cash account through the counting session's vault.
- Custom field anchors moved to fields that exist across every v15 build.
- Demo dataset added (`alphax_cit/demo/demo_data.py`).

---

## What it adds

| Area | DocTypes |
|---|---|
| Operations | `CIT Job`, `CIT Trip` (+ crew, stops, checklist), `CIT POD`, `CIT Incident`, `CIT Sync Event`, `CIT Service Type`, `CIT Checklist Template` |
| Cash & vault | `Cash Custody Entry`, `Cash Bag`, `Seal Register`, `Counting Session`, `CIT Denomination Count`, `CIT Discrepancy`, `CIT Vault` |
| Fleet | `Vehicle Compliance Document`, `CIT Maintenance Request`, `CIT Fuel Entry`, `Vehicle Incident`, `Fleet Availability Log` |
| Commercial | `Customer Site`, `CIT Service Contract`, `CIT Tariff Line`, `CIT SLA Target`, `CIT SLA Breach`, `CIT Billing Run` |
| Telematics | `GPS Provider`, `GPS Position Event`, `Geofence`, `Geofence Event`, `CIT Alert`, `CIT Device` |
| Process flow | `CIT Process Flow`, `CIT Process Stage`, `CIT Process Node` |

48 DocTypes in total (17 child tables, 12 submittable), 3 script reports, 10 roles,
1 desk page, 1 workspace, 2 process flows (12-step journey + 26-stage board).

## The process flow board

`/app/cit-process-flow` opens on the **journey view**: one linear spine of **12 steps**
from registering a customer to collecting the invoice, grouped into five phases —
Commercial, Operations, Field, Vault & Cash, Finance.

Each step card carries the plain-language answer to the four questions a new user or a
customer actually asks: *who does this*, *what happens here*, *what will the system not
let go wrong*, and *how long does it take*. Below that sit the documents for that step as
clickable chips, dashed ones creating a new record.

The **detailed board** — **7 swimlanes, 26 stages and 76 document nodes** — is one click
away on the view switch, for dispatchers and controllers who live in the system all day.
Both views are seeded on install and both are data-driven.

For anyone outside the desk — a customer, a new joiner, a proposal reader — the same
journey is published at **`https://<your-site>/cit-journey`**: no login needed once
enabled, `?lang=ar` for Arabic, and the browser print dialog gives you a clean PDF.

Every card opens the document behind it:

- click a card → filtered list view
- `+` → new document pre-filled with the node's filters
- `▣` → report view
- nodes are tagged **CIT** or **ERPNext** so it is obvious which part of the process runs
  on standard software

**30 of the 76 nodes point at standard ERPNext documents** — Customer, Contract, Item,
Vehicle, Vehicle Log, Asset, Asset Maintenance Log, Employee, Attendance, Leave
Application, Training Event, Payroll Entry, Salary Slip, Sales Invoice, Purchase Invoice,
Payment Entry, Journal Entry, Bank Transaction, Bank Reconciliation Tool, Expense Claim,
Activity Log, Access Log, Role, Workflow and others. The flow is the operator's
navigation surface, not a picture kept in a separate file.

Nodes respect permissions: a card is hidden if the user cannot read its DocType, and
`allowed_roles` narrows it further. Counts are live.

The page menu also exposes **Verify custody chain**, which re-computes the hash chain and
reports the first broken link.

## Design decisions worth knowing

- **The ERPNext core is never modified.** Standard documents are extended through Custom
  Fields owned by this app (`seed/custom_fields.py`), created idempotently and removed on
  uninstall.
- **No server scripts.** All logic is in versioned Python controllers. `verify_tree.py`
  fails the build if a server script appears in app code.
- **Custody entries are append-only.** `on_cancel` and `on_trash` raise. Corrections are
  posted as reversals. Each entry stores a SHA-256 of its content chained to the previous
  entry's hash, so later tampering with the database is detectable.
- **Dispatch is gated server-side.** Expired vehicle documents, expired crew
  certification, overlapping assignment and insufficient rest all block dispatch. Override
  requires a role, a reason and raises a critical alert.
- **Mobile sync is idempotent.** Every event carries a client-generated
  `client_event_id`. Replays return `Duplicate` with no side effect; failures roll back to
  a savepoint and land in a quarantine queue rather than being discarded.
- **Telematics is behind an adapter.** Changing provider is a new class in
  `api/gps.ADAPTERS`, not a redesign.
- **Billing holds on open discrepancies.** A trip with an unresolved variance above the
  configured threshold is held back from invoicing by default.
- **Bilingual, with direction as a separate choice.** 772 Arabic strings ship in
  `translations/ar.csv`; content records carry their own `_ar` fields. Arabic normally
  means right-to-left, but a site or a user can force left-to-right — some finance teams
  prefer it for numeric screens while still reading Arabic labels.

## Demo data

Not installed automatically. Seed it explicitly:

```bash
bench --site <site> execute alphax_cit.demo.demo_data.create_demo_data
# or
bench --site <site> cit-demo
```

Seeds **Wadi Secure Logistics**: 3 customers, 6 sites with geofences, 3 service
contracts with full tariffs and SLA targets, 5 armoured vehicles with 25 compliance
documents, 8 crew with qualification dates, a vault, a 200-seal register, 4 crew
devices and a GPS provider.

It then walks one trip end to end so every screen has something real in it:

1. Three jobs → a trip with 4 crew, dispatched and completed three days ago
2. Three proofs of collection with 29 sealed bags
3. 29 custody entries transferring the bags from crew to vault, hash-chained
4. A counting session with a **deliberate SAR 2,500 shortage** and **SAR 500 in
   counterfeit notes**
5. Two auto-created discrepancies; the shortage is approved and posted to the GL,
   the counterfeit stays open
6. A billing run that **held the trip while the shortage was open** and rates it once
   released
7. Plus a live trip for the control room, a trip that **cannot be dispatched** (one
   crew member has an expired licence, the vehicle has an expired inspection), fuel
   entries, a maintenance request and a breakdown

Two vehicles carry expiring or expired documents on purpose, so the fleet compliance
cockpit and the daily expiry alerts have something to show.

Remove it with:

```bash
bench --site <site> execute alphax_cit.demo.demo_data.clear_demo_data
```

Both are idempotent.

## Install

```bash
bench get-app alphax_cit /path/to/alphax_cit
bench --site <site> install-app alphax_cit
bench --site <site> migrate
```

On Frappe Cloud: push to the connected repository and run a migration from the dashboard.

`after_install` and `after_migrate` both call `setup/install.py`, which seeds roles,
custom fields, service types, the pre-trip checklist, settings defaults, the process flow
and the workspace. Every seeder is idempotent — running migrate repeatedly changes
nothing.

## First-run configuration

1. **AlphaX CIT Settings** — company, default vault, discrepancy accounts, approval bands,
   dispatch controls, alert thresholds, billing hold threshold.
2. **CIT Vault** — at least one vault with its cash account.
3. **Vehicles** — set `cit_tracker_id` so GPS positions resolve, and attach
   `Vehicle Compliance Document` records.
4. **Employees** — tick `cit_is_crew` and fill the licence, clearance, permit and medical
   expiry dates. These are enforced at dispatch.
5. **Customer Site** — geo position and access protocol; create a matching `Geofence` to
   get automatic arrival and departure stamping.
6. **CIT Service Contract** — sites, tariff lines and SLA targets.
7. **GPS Provider** — base URL and API key, or the webhook secret.

## Mobile API

```
POST /api/method/alphax_cit.api.sync.pull    {employee}
POST /api/method/alphax_cit.api.sync.push    {events: [...], device_id}
```

Event types: `trip_start`, `stop_arrive`, `stop_complete`, `pod_capture`, `incident`,
`panic`, `checklist`, `trip_complete`.

Each event: `{client_event_id, seq, event_type, employee, payload}`.

## Scheduled jobs

## Language and direction

| Where | What the user does |
|---|---|
| Flow page menu | *Switch interface language* — one click, reloads in Arabic or English |
| Flow page menu | *Left to right / Right to left* — flips direction for that browser only |
| Flow page menu | *Arabic / English content* — swaps the step text without changing the UI language |
| AlphaX CIT Settings | *Interface Direction* — Automatic, or forced for the whole site |
| `/cit-journey` | `?lang=ar` and `?dir=ltr` as independent query parameters, with buttons |
| Print | **CIT POD Bilingual** — Arabic and English on every label and column |

Anything the user types — site names, service types, process steps — has its own `_ar`
field, so content is bilingual alongside the interface.

| Cadence | Job |
|---|---|
| every 5 min | GPS polling, prolonged halt and signal-loss detection |
| hourly | SLA evaluation from operational timestamps |
| daily | document expiry ladder, maintenance due, contract status, fleet availability snapshot |
| weekly | position event retention purge |

## Before committing

```bash
python3 verify_tree.py
```

Checks module folders against `modules.txt`, link targets, field order, **a controller
module for every DocType including child tables**, **naming-series autoname rules**,
**`__init__.py` at every package level**, submittable amend fields, hook resolution,
process flow node targets, demo data references and the absence of server scripts.

## Files

```
alphax_cit/
├── verify_tree.py              structural guard
├── COVERAGE.md                 67 requirements → implementation map
└── alphax_cit/
    ├── hooks.py, events.py, permissions.py, tasks.py, cit_utils.py
    ├── api/                    process_flow.py, sync.py, gps.py
    ├── demo/demo_data.py        seed and clear the demo dataset
    ├── translations/ar.csv      772 Arabic strings
    ├── www/cit-journey.*        public journey page
    ├── commands.py              bench --site <site> cit-demo
    ├── seed/                   roles, custom_fields, defaults, journey_flow,
    │                           process_flow, workspace
    ├── setup/install.py
    ├── cit_operations/  cit_cash/  cit_fleet/  cit_commercial/  cit_telematics/
    └── cit_process_flow/page/cit_process_flow/
```

---

© 2026 Neotec Integrated Solutions. Commercial licence.

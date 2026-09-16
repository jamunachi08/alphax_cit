# AlphaX CIT

Cash in Transit operations, chain of custody, fleet compliance and contract billing for
**Frappe / ERPNext v15**.

Built by Neotec Integrated Solutions to close every requirement scored **2 — Partially
Supported** or **3 — Requires Customization** in the CIT Requirement Compliance Matrix
(67 of 96 requirements). Requirements scored **1 — Fully Supported** are met by standard
ERPNext and are surfaced through the process flow rather than rebuilt.

Version **0.1.0**.

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
1 desk page, 1 workspace.

## The process flow board

`/app/cit-process-flow` renders the end-to-end CIT process as **7 swimlanes, 26 stages
and 76 document nodes**, seeded on install.

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
- **Bilingual.** Arabic labels are seeded for service types, process stages and nodes.

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

Checks module folders against `modules.txt`, link targets, field order, controller class
names, submittable amend fields, hook resolution, process flow node targets and the
absence of server scripts.

## Files

```
alphax_cit/
├── verify_tree.py              structural guard
├── COVERAGE.md                 67 requirements → implementation map
└── alphax_cit/
    ├── hooks.py, events.py, permissions.py, tasks.py, cit_utils.py
    ├── api/                    process_flow.py, sync.py, gps.py
    ├── seed/                   roles, custom_fields, defaults, process_flow, workspace
    ├── setup/install.py
    ├── cit_operations/  cit_cash/  cit_fleet/  cit_commercial/  cit_telematics/
    └── cit_process_flow/page/cit_process_flow/
```

---

© 2026 Neotec Integrated Solutions. Commercial licence.

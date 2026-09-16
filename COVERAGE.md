# AlphaX CIT — Requirement Coverage Map

Every requirement scored **2 — Partially Supported** or **3 — Requires Customization** in the Requirement Compliance Matrix, mapped to what delivers it in this application.

Total mapped: **67** requirements (21 partial, 46 custom).

| Ref | Requirement | Score | Delivered in `alphax_cit` by |
|---|---|---|---|
| 1.1 | Cash collection and delivery management | 3 Custom | `CIT Job` (service type, declared value, window, contract validation) |
| 1.2 | Trip planning and scheduling | 3 Custom | `CIT Trip` + stops table; dispatch board via `CIT Trip.board()` |
| 1.3 | Assignment of armored vehicles and crew | 3 Custom | `CIT Trip Crew` + `dispatch_blockers()` (vehicle documents, crew certification) |
| 1.4 | Driver and security personnel assignment | 3 Custom | `CIT Trip Crew.crew_role`; rest-hour and overlap guards |
| 1.5 | Collection and delivery confirmation | 3 Custom | `CIT POD` + mobile `stop_complete` sync handler |
| 1.6 | Digital proof of delivery | 3 Custom | `CIT POD` with signature, photos, seal numbers and GPS stamp |
| 1.7 | Trip status tracking from initiation to completion | 3 Custom | `CIT Trip.TRANSITIONS` state machine with `move_to()` |
| 1.8 | Exception, incident, shortage and excess management | 3 Custom | `CIT Incident` (10 categories, severity, closure) |
| 2.1 | End-to-end tracking of cash movements | 3 Custom | `Cash Custody Entry` — append-only ledger |
| 2.2 | Cash-in and cash-out transactions | 2 Partial | `Cash Custody Entry` + ERPNext `Journal Entry` / `Payment Entry` (custody layer above the GL) |
| 2.3 | Cash, bag and seal number tracking | 3 Custom | `Cash Bag` + `Seal Register` / `Seal Entry` lifecycle |
| 2.5 | Expected vs. actual cash reconciliation | 3 Custom | `Counting Session` + `Counting Session Bag` + `CIT Denomination Count` |
| 2.6 | Shortage and excess recording | 3 Custom | Auto-created `CIT Discrepancy` on variance, counterfeit, damaged note |
| 2.7 | Approval workflow for cash discrepancies | 2 Partial | `CIT Discrepancy.apply_threshold()` — value bands from `AlphaX CIT Settings.approval_thresholds` |
| 2.8 | Complete audit trail for all cash transactions | 3 Custom | SHA-256 hash chain in `before_submit`; `verify_chain()`; cancel and delete blocked |
| 3.1 | Complete vehicle records | 2 Partial | Custom fields on ERPNext `Vehicle` (armour level, compartments, tracker ID, weapon locker, availability) |
| 3.2 | Registration, insurance and inspection tracking | 3 Custom | `Vehicle Compliance Document` (istimara, insurance, fahs, permit) |
| 3.3 | Preventive and corrective maintenance | 2 Partial | `CIT Maintenance Request` → ERPNext `Asset Maintenance Log`; `tasks.check_maintenance_due` |
| 3.4 | Fuel management | 2 Partial | `CIT Fuel Entry` → ERPNext `Vehicle Log`; km/litre variance computed on submit |
| 3.5 | Vehicle availability and utilisation | 3 Custom | `Fleet Availability Log` + daily snapshot task |
| 3.6 | Accident and breakdown management | 3 Custom | `Vehicle Incident` with claim tracking → `CIT Incident` + downtime log |
| 3.7 | Automated alerts for expiry dates and maintenance | 2 Partial | `tasks.check_document_expiry` with the 90/60/30/7 ladder → `CIT Alert` |
| 3.8 | GPS integration and vehicle tracking | 3 Custom | `api/gps.py` provider adapter + `GPS Position Event` |
| 4.2 | Driver and security personnel management | 2 Partial | Custom fields on ERPNext `Employee` (licence, clearance, weapon permit, medical fitness) |
| 4.3 | Assignment of employees to trips | 3 Custom | `CIT Trip Crew` assignment with conflict and rest-hour detection |
| 4.5 | Employee documents and expiry tracking | 2 Partial | `cit_utils.employee_document_status()` + daily expiry task |
| 4.6 | Training and certification records | 2 Partial | Certification validity enforced at dispatch by `CIT Trip.dispatch_blockers()` |
| 5.2 | Contract management | 2 Partial | `CIT Service Contract` linked to the standard ERPNext `Contract` |
| 5.4 | Service and pricing configuration | 3 Custom | `CIT Tariff Line` — 9 charge bases including ad valorem bands |
| 5.5 | Customer-specific routes and requirements | 3 Custom | `Customer Site` (access protocol, authorised receivers, service window, geofence) |
| 5.6 | SLA monitoring | 3 Custom | `CIT SLA Target` + `CIT SLA Breach` + `tasks.evaluate_sla` |
| 6.1 | Automated invoicing based on completed services/trips | 3 Custom | `CIT Billing Run.rate_trips()` → draft `Sales Invoice` |
| 6.6 | Customer and contract profitability | 2 Partial | `CIT Trip Performance` report + accounting dimensions on `Sales Invoice Item.cit_trip` |
| 6.9 | Financial and operational reporting | 2 Partial | 3 script reports + workspace; ERPNext financial statements unchanged |
| 7.2 | Segregation of duties | 2 Partial | Role set seeded by `seed/roles.py`; SoD matrix consumed from AlphaX GRC |
| 8.1 | Real-time vehicle tracking | 3 Custom | `CIT Trip.board()` with last known position per vehicle |
| 8.2 | Trip tracking | 3 Custom | `GPS Position Event.cit_trip` correlation |
| 8.3 | Route monitoring | 3 Custom | Position feed retained per `position_retention_days` |
| 8.4 | Geofencing | 3 Custom | `Geofence` (circle + polygon) with `point_in_polygon` / `haversine_metres` |
| 8.5 | Arrival and departure tracking | 3 Custom | `_stamp_stop()` — arrival, departure and dwell measured from geofence events |
| 8.6 | Route deviation alerts | 3 Custom | `raise_alert` on deviation, speeding, prolonged halt, signal loss, prohibited zone |
| 8.7 | Integration with existing or third-party GPS platforms | 3 Custom | `ADAPTERS` registry + `webhook()` with shared-secret check |
| 9.1 | Viewing assigned trips | 3 Custom | `api/sync.pull()` — trips, stops, site detail, contacts |
| 9.2 | Trip start and completion | 3 Custom | `trip_start` / `trip_complete` handlers with odometer capture |
| 9.3 | Collection and delivery confirmation | 3 Custom | `stop_arrive` / `stop_complete` handlers |
| 9.4 | Digital signatures | 3 Custom | `CIT POD.signature` + signatory identification |
| 9.5 | Document/photo upload | 3 Custom | `CIT POD Photo` child table |
| 9.6 | Incident reporting | 3 Custom | `incident` and `panic` sync handlers |
| 9.7 | GPS/location integration | 3 Custom | Latitude and longitude captured on every operational event |
| 9.8 | Offline functionality with automatic synchronisation | 3 Custom | `api/sync.push()` — `client_event_id` uniqueness, savepoint rollback, quarantine queue |
| 10.1 | Daily and completed trips | 3 Custom | `CIT Trip Performance` report + flow nodes |
| 10.2 | Delayed and outstanding trips | 3 Custom | Flow node: trips by status with ageing |
| 10.3 | Vehicle availability and utilisation | 3 Custom | `CIT Fleet Compliance Cockpit` + availability log |
| 10.4 | Crew utilisation | 3 Custom | Crew utilisation from `CIT Trip Crew` joins |
| 10.5 | Cash discrepancies | 3 Custom | `CIT Cash Discrepancy Ageing` report |
| 10.6 | Customer activity | 3 Custom | Customer activity nodes filtered by customer |
| 10.8 | Operational costs | 2 Partial | `CIT Trip Performance` (cost per trip, distance, discrepancy) |
| 10.9 | Profitability | 2 Partial | ERPNext `Profitability Analysis` node + trip-level allocation fields |
| 10.10 | SLA performance | 3 Custom | `CIT SLA Breach` list and penalty exposure |
| 10.11 | Operational and financial KPIs | 2 Partial | `AlphaX CIT` workspace shortcuts + number cards |
| 11.3 | GOSI | 2 Partial | ERPNext Payroll GOSI fields; reconciliation report node in the flow |
| 11.4 | Qiwa | 2 Partial | `AlphaX Integration Layer` node placeholder — scope fixed at blueprint |
| 11.5 | Mudad | 2 Partial | ERPNext Payroll WPS file; Mudad posting subject to subscription |
| 11.7 | Banking integrations | 2 Partial | ERPNext `Bank Transaction` / `Bank Reconciliation Tool` nodes in the flow |
| 11.9 | GPS platforms | 3 Custom | See 8.7 |
| 11.10 | Payment gateways | 2 Partial | ERPNext payment gateway framework (connector out of scope of v0.1.0) |
| 12.3 | Integration with Odoo (operational, customer, invoicing, accounting data) | 3 Custom | REST/webhook surface ready; Dual Sync mapping is a separate licensed module |

## Notes

- Items 11.3 to 11.10 depend on the client's own subscriptions and authorised access. The application exposes the integration points; the connector scope is fixed at blueprint.
- Item 12.3 (Odoo synchronisation) is delivered by the separate Neotec Dual Sync module, priced as an option in the Commercial Proposal.
- Requirements scored **1 — Fully Supported** are met by standard ERPNext v15 and are surfaced in the process flow rather than rebuilt.

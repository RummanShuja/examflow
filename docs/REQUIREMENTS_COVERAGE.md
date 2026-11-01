# Requirements coverage

This index links the bundled starter/full implementation to its verification evidence. Paths below are relative to the project; substitute `artifacts/starter` for the starter evidence. The provided business statement and recruiter PDFs drove this implementation. No external dataset was used.

| Requirement | Implementation | Verification / evidence |
|---|---|---|
| Executable end-to-end workflow | `python -m examflow demo --both --output artifacts` | `artifacts/{starter,full}/demo_summary.json` passed |
| All 11 core entities | `schema.py`, `schema.sql` (plus 12 supporting entities) | STRICT tables, dictionary and DB integrity checks |
| Type, required, allowed, units, uniqueness and validation for every field | Declarative Field/Table definitions | `docs/DATA_DICTIONARY.md` generated before data |
| Every PK/FK and bridge | 23 tables, 33 declared FK relationships | `validation_summary.json` lists every join and matching counts |
| Cardinality, optionality, effective dates and lifecycle states | `docs/ER_MODEL.md` | Lifecycle/effective-date and malformed-event tests |
| Parent/master before dependent records | `_populate()` insertion order; parent-first SQL seed | FK enforcement and SQL restore tests |
| Immutable ID conventions and assignment ID across runs | Deterministic zero-padded IDs; immutable PK triggers; composite assignment PK | ID checks, immutable-PK test, two-run test |
| 5,000 students / 300 exams / 100 rooms / 200 invigilators | Full configuration | Full-scale automated acceptance and source-count JSON |
| Same generator, starter and parameterized scale | `configuration(profile,scale,seed)` | Starter + full demos; scale=0.1 test |
| Seed 20261022 | Dedicated local `random.Random(seed)` | Manifest, source configuration and independent builds |
| Realistic variation and enrollment conflicts | Cohort core courses, shared electives, weighted durations, staff shifts, closures, capacity changes | Graph has 299 vertices / 11,195 edges; source exports |
| Special equipment and duration/accessibility needs | Equipment bridges, scoped/expired/pending/approved support | Missing-equipment, approval-state, interval and capacity tests |
| Valid baseline before anomaly injection | Source/production built first; fixtures are separate JSON | Production audit zero violations; fixture evaluation separate |
| Five specified negative scenarios | `fixtures.py`, controlled source-derived assignments | Five TP / zero FP / zero FN in `evaluation.json` |
| Clean and boundary cases | Clean, adjacent intervals, exact capacity | Three clean controls; additional tests for touching closures and changed capacity |
| Derived demand, duration, staffing and labels | Enrollment/support formulas and controlled fixture proofs | Independent recomputation, tampered-requirement test, ground-truth rationale |
| Separate ground truth, no input leakage | `fixtures/inputs.json` vs `ground_truth.csv/json` | Label-isolation test; only evaluator reads labels |
| Build conflict graph then schedule times/rooms/staff | `domain.py`, `scheduler.py` | Deterministic assignments and weighted graph export |
| Student and resource conflicts | Actual `[start,end)` checks; independent pairwise detector | Production zero violations; conflict fixtures/tests |
| Effective room capacity/equipment/openings/closures | Entire-interval filtering and independent audit | Capacity-boundary, exact-capacity, closure and equipment tests |
| Full-duration staff availability, count and no double-booking | Effective availability unions, bookings, ceil(demand/40) | Availability, duplicate-count and concurrent-staff tests |
| Consistent approved accommodations | Max effective extra time and accessible room | All 1,532 scheduled support obligations fulfilled; ignored-support fixture |
| Exam windows, cancellation, effective dates and active enrollment | Source snapshot policy + independent audit | Window, cancelled-exam, approval and lifecycle tests |
| One accepted assignment or honest unassigned outcome | Unique `(run,exam)` and outcome coverage validation | 298 scheduled + 1 unassigned = 299 planned; 1 cancelled excluded |
| Every unassigned exam has machine reason and evidence | NO_COMPATIBLE_ROOM / NO_FEASIBLE_SLOT / NO_ENROLLMENTS | Unassigned CSV/JSON, decision events and rule-derived expectation |
| Genuine infeasible demand | EQ-SECURE required, no room offers it | Separate expected decision proof and evaluated actual reason |
| Append-only state/run/decision history | Typed lifecycle + decision events; immutable histories; atomic runs | Trigger, lifecycle-chain, retained-second-run tests |
| Independent imported-assignment validator | `validate.py`, CLI JSON/CSV import | Bad-import CLI exits 2; doesn't trust stored requirement cache |
| PKs, FKs, enums, required fields, duplicates and dates | STRICT SQL/checks + independent source checks | PRAGMA integrity_check / foreign_key_check and tests |
| Usage reconciliation | Python durations vs joined SQL totals | Room 57,892 minutes; staff 173,856 minutes; exact match |
| Precision/recall, TP/FP/FN per rule | Eight-case evaluator, undefined rates explicitly null | `evaluation.json`, HTML report; small-fixture limitation stated |
| Operational outputs with denominators | `metrics.py`, room/staff usage, accommodations | `metrics.json` definitions and `docs/VERIFICATION.md` |
| Reproduce twice and compare counts/checksums/scheduling | Two fresh databases and canonical record hashes | Every one of 23 tables matched; no excluded columns; `reproducibility.json` |
| CSV/JSON/SQL, DB, manifest and validation summary | `export.py`, artifacts per profile | SQL restoration round-trip and checksum checks |
| Windows SQLite beginner setup | README doctor/demo/py fallback and inspection commands | No external packages/server; Linux verification passed; Windows setup check passed and cleanup correction tested |
| Learner/instructor/admin/support/platform actors | Student lookup, timetable/report/exports/audit | Report role descriptions; no unnecessary authentication scope |
| Explain choices, complexity, assumptions and limitations | README, WALKTHROUGH, ER_MODEL | Architecture, assumptions and decision traces documented |
| Prompt history and honest AI disclosure | PROMPT_HISTORY, verbatim relevant prompts, AI_USAGE | Available current prompt text retained; unavailable earlier history disclosed |
| Public dedicated GitHub repo and actual commits | Clean source distribution | Publish as a dedicated public repository and submit its URL |
| Deadline / same recruitment email submission | 72-hour window and submission channel documented | Deadline is calculated from the recorded recruitment timestamp |
| Downloadable complete project | Source, data, reports, docs and tests in ZIP | Archive integrity and extracted-project smoke checks |
| No secrets/private/external data | Synthetic names only; no API keys or dependencies | Repository inspection and source manifest; no recruiter PDFs copied into public source |

The FAQ permits a local executable demonstration. AI use and available prompt records are documented in AI_USAGE.md and PROMPT_HISTORY.md. The repository must be public for submission.

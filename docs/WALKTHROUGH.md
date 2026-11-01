# Explain the solution

## A one-minute introduction

“ExamFlow generates related synthetic enrollment and resource data, schedules exams using a deterministic conflict-graph heuristic, and checks the result with an independent auditor. A valid schedule cannot hide exceptions: every planned exam gets an assignment or an explicit unassigned outcome. Immutable run records, lifecycle events and decision events make the output traceable. The default dataset meets all four required volumes.”

## Architecture and reading order

| File | Responsibility |
|---|---|
| `schema.py` | 23 STRICT SQLite tables, FKs, checks, immutable PK/history triggers; dictionary generation |
| `generate.py` | Seeded parent-first synthetic recipe and lifecycle event creation |
| `domain.py` | Scheduler facts, enrollment-derived demand/support and weighted conflict graph |
| `scheduler.py` | Deterministic feasible placement, explicit exceptions, atomic run persistence |
| `validate.py` | Independent source and imported-assignment auditing; does not import scheduler or ground truth |
| `fixtures.py` | Controlled scenarios, separate labels, and the only reader of the ground-truth file |
| `metrics.py` | Resource-time, seat-time and support-coverage reconciliation |
| `export.py`, `reproduce.py` | Portable outputs and two independent canonical comparisons |
| `report.py`, `__main__.py` | Offline report and small CLI workflow |

The database is the source of truth. A connection enables foreign keys before any work. The generator refuses to overwrite a database with another configuration. Each scheduling run is computed and committed as one transaction; failed transactions leave no partial “completed” run. Decision events record the run start, each outcome with evidence, and completion. No current date or random UUID enters deterministic data.

## How generation works

Each learner belongs to a cohort and enrolls in its five core courses plus one shared elective. A small number of extra elective enrollments are subsequently withdrawn; both states are retained as events. There is exactly one exam per course in this assessment period. One elective exam is cancelled, and the final planned elective requires specialist equipment absent from all rooms.

Durations are sampled from a documented weighted list. Approved support, active enrollments and base duration determine demand, maximum extra time, accessible-room needs, duration and staffing. Pending, rejected, expired and exam-scoped accommodations demonstrate conditional rules. Rooms include capacity versions, varied equipment, a one-seat space, partial/full closures and one retired room. Staff have full or partial shifts, days off and cancelled availability. The first resource records provide predictable clean boundary controls; the remaining records provide seeded variation.

## Why the graph helps

Each planned exam is a vertex. Two exams have an edge when their active course enrollments share at least one learner; the edge weight is the shared learner count. Placing highly connected exams first reduces the risk of leaving hard exams until the end.

Order is descending `(degree, duration, enrollment)`, then ascending exam ID. For each exam, try 08:00, 10:30, 13:00 and 15:30 on each weekday in order. Reject a start if a student's assigned exam overlaps. Filter rooms by equipment, accessibility, effective capacity, opening hours, closures and current bookings. Choose the sufficient room with least spare capacity; room ID breaks ties. Select fully available, unbooked staff by prior allocated minutes, then ID. Persist an assignment only when every hard rule holds.

The number of learners sets staff demand: `ceil(demand / 40)`. The longest applicable approved extra-time allowance extends the whole examination: `ceil(base_minutes * (100 + max_extra_percent) / 100)`. This simple policy reserves more room/staff time than individualized sessions; the metrics explicitly report that cost.

## Complexity and honest failure

Graph construction costs `O(sum_s k_s^2)`, where `k_s` is the number of exams for learner `s`; graph memory is `O(V + E)`, plus source enrollments. Let `T` be candidate starts, `R` rooms, `I` staff, `A` interval records per resource, and `B` prior bookings per resource. Placement is approximately `O(V * T * (degree + R*(A+B) + I*log(I) + I*(A+B)))`, with additional support lookups. At the default size, `V=299` planned exams and `T=40`. The independent assignment auditor compares exam pairs in `O(V^2)` and separately audits source/event records.

The heuristic does not optimize globally or prove feasibility over arbitrary start times. `NO_FEASIBLE_SLOT` means no placement under this candidate policy. `NO_COMPATIBLE_ROOM` is a static incompatibility; the demonstration's missing specialist equipment proves that demand infeasible even if rooms/times were rearranged. `NO_ENROLLMENTS` is an explicit outcome for empty demand. Every exception stores counts/evidence and an explanation.

## Why the validator is separate

The auditor reconstructs enrolled learners, support obligations and staffing from source rows, rather than trusting cached ExamRequirement values or scheduler rejection decisions. It checks actual time intervals and all imported parent IDs. It independently finds student, room and staff overlaps, checks availability/capacities, and reconciles SQL aggregates against Python totals. It can read an imported assignment CSV or JSON without running placement.

Production validation also checks all 33 declared FK joins, schema integrity, enum/required fields, effective intervals, lifecycle chains, immutable-history guards, derived values, outcome coverage and decision payloads. Imported coverage normally matches the selected run's scheduled-exam set; `--allow-partial` deliberately disables that one check for subset analysis. Hard rules remain enforced.

## Five failures and three controls

| Case | Controlled modification | Expected detector result |
|---|---|---|
| CASE-000001 | Concurrent exams of the same cohort, different rooms/staff | STUDENT_OVERLAP |
| CASE-000002 | Demand placed in a one-seat room | ROOM_CAPACITY |
| CASE-000003 | Disjoint cohorts, separate rooms, same concurrent staff | INVIGILATOR_DOUBLE_BOOKED |
| CASE-000004 | Base duration used despite approved extra time | ACCOMMODATION_IGNORED |
| CASE-000005 | 07:00 start while room opens at 08:00 | ROOM_UNAVAILABLE |
| CASE-000006 | Feasible source-derived assignment | No violation |
| CASE-000007 | Same learners/room/staff in adjacent `[start,end)` intervals | No violation |
| CASE-000008 | Demand equals effective room seats | No violation |

The input document contains only neutral case IDs and assignments. A separate ground-truth document records labels and construction proofs. The evaluator is the only consumer of that label file. Counts are per `(case, rule)`; precision/recall for unrepresented positive rules are undefined, not claimed as perfect.

## Trace an assignment

Retrieve `STU-000001`'s timetable and follow an assignment through its ExamRequirement, InvigilatorAllocation and DecisionEvent records. Compare its duration and room capacity against the source records. The interval-boundary tests show why adjacent exams are legal; the separate negative fixtures show how invalid schedules are detected without contaminating the accepted timetable.

# Executed verification and limits

Verification ran on Linux with Python 3.12.14. Exact SQLite/platform versions and UTC execution time are recorded in `artifacts/verification_execution.json`. The commands below reproduce the checks.

```text
python -m unittest discover -s tests -v
python -m examflow demo --both --output artifacts
python tools/verify.py
```

The current automated suite passed **37 tests**, including three new connection-lifetime regressions. The final verifier runs that same suite and saves its actual output in `artifacts/tests.log`; it then verifies the bundled artifacts independently. The first release passed 34 tests on Linux but missed a connection leak that blocked Windows temporary-file deletion. The new tests reproduce that leak without relying on Linux's permissive unlink behavior. Earlier in development, a test attribute named `run` shadowed `unittest.TestCase.run`; it was renamed `run_id`. All accepted schedules passed the independent hard-constraint audit.

## Full dataset, seed 20261022

| Measure | Executed result |
|---|---:|
| Students | 5,000 |
| Courses / Exams | 300 / 300 |
| Enrollment rows (including withdrawn history) | 30,183 |
| Rooms / Invigilators | 100 / 200 |
| Accommodation records (including other states/expired) | 362 |
| Planned / Cancelled exams | 299 / 1 |
| Scheduled / Unassigned | 298 / 1 |
| Scheduling rate (scheduled / planned) | 99.6656% |
| Hard-constraint violations | 0 |
| FK join checks | 33, all reconciled |
| Conflict graph vertices / edges / max degree | 299 / 11,195 / 245 |
| Room minutes, Python and joined SQL | 57,892, equal |
| Invigilator minutes, Python and joined SQL | 173,856, equal |
| Available room minutes | 568,800 |
| Room-time utilization | 10.1779% |
| Available effective seat-minutes | 71,998,800 |
| Student seat-minutes | 5,793,166 |
| Seat-time utilization across full available horizon | 8.0462% |
| Capacity-minutes of occupied rooms | 6,995,708 |
| Occupied-room seat fill | 82.8103% |
| Available invigilator minutes | 821,700 |
| Invigilator-time utilization | 21.1581% |
| Approved support obligations on scheduled exams / fulfilled | 1,532 / 1,532 (100%) |
| Approved support obligations on all planned exams | 1,536 |
| End-to-end support coverage, including unassigned exam | 1,532 / 1,536 (99.7396%) |
| Whole-exam accommodation overhead, room / staff minutes | 17,782 / 53,406 |

Room/staff availability denominators cover all ten weekdays in the declared horizon, subtracting closures/cancelled availability and respecting lifecycle/effective dates. Seat-time uses dated seat counts. These are horizon utilization values, not peak utilization or an optimization result. The unassigned reason is `NO_COMPATIBLE_ROOM`; its EQ-SECURE requirement is absent from all rooms. The cancelled exam is excluded from the planned denominator and has no assignment or outcome.

## Starter and detector coverage

Starter has 250 students, 30 exams, 12 rooms and 24 invigilators: 28 scheduled, one unassigned, one cancelled, zero hard violations.

Both profiles' eight regression cases returned **TP=5, FP=0, FN=0**, with three clean/boundary controls producing no false positives. Per-rule precision and recall are in each evaluation.json. Counting unit is `(case,rule)`; unrepresented positive rules have undefined recall. The selected fixtures do not establish broad accuracy on unseen data.

Two independent fresh builds per profile matched row counts and SHA-256 checksums for all **23 tables**, plus the complete deterministic scheduling and fixture results. No database columns were excluded. Raw SQLite file bytes are not the checksum contract; records are canonical sorted-key JSON, UTF-8 with LF, in declared primary-key order.

## Export and report verification

The final verifier loads each assignment CSV through the independent detector, recalculates saved metrics/checksums, reconstructs both full and starter databases from SQL seeds, and compares every restored table checksum. Both HTML reports have matching timetable row counts and working local export/anchor targets. Inline JavaScript syntax passed a Node parse check. Visual browser review was attempted but unavailable because the Playwright browser executable was not installed.

The project uses only Python's standard library at runtime. Git is needed for publication or packaging from a committed source tree. Known limitations are the greedy finite start grid, one room per exam, whole-exam support extension, binary equipment capability, frozen enrollment/support state within windows, and a CLI/static-report interface. The captured automated checks cover Linux; full native Windows execution and visual browser rendering are outside that record.

## Windows cleanup fix (1.0.1)

The initial Windows run used Python 3.14.6 / SQLite 3.50.4 and stopped at cleanup of `independent-1.sqlite3`. `with sqlite3.Connection` commits/rolls back but does not close the handle. Reproduction, source-reuse, CLI, verifier and test ownership scopes now use `contextlib.closing`; transaction scopes remain separate. Connection initialization also closes the handle if configuration fails.

Three new tests failed against the previous code (four failure subcases), then passed after the change. The full 37-test suite, exported-data verification and both demos on copied existing databases passed on Linux. Existing RUN-000001 remained present and each demo appended RUN-000002. The resource-lifetime regression checks run across platforms by asserting handle closure before deletion.

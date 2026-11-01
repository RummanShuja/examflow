# ExamFlow

An executable, local solution for the YottaFlex AI exam-scheduling assignment. It generates related synthetic data, builds an enrollment conflict graph, assigns exams to times, rooms and invigilators, preserves decisions, and independently validates the result.

**Default full build:** 5,000 students, 300 exams, 100 rooms, 200 invigilators. **298 scheduled, 1 unassigned, 1 cancelled; zero hard-constraint violations.** The unassigned exam requires specialist equipment absent from every room. It stays unassigned with evidence instead of violating a constraint.

## Run on Windows / PowerShell

Install Python 3.11 or newer from [python.org](https://www.python.org/downloads/) and enable the installer option to add Python to PATH. Git is only needed for publishing. No pip packages are required.

Extract the ZIP, open PowerShell inside its `yottaflex-examflow` folder, then run:

```powershell
python -m examflow doctor
python -m examflow demo --both --output artifacts
Start-Process .\artifacts\full\report.html
```

If `python` is not recognized, use the Windows Python launcher:

```powershell
py -3 -m examflow doctor
py -3 -m examflow demo --both --output artifacts
Start-Process .\artifacts\full\report.html
```

The command checks for Python >=3.11 and built-in SQLite >=3.37. If neither `python` nor `py` works, install Python, close PowerShell, and open it again. There is no separate SQLite installation, server, GUI, account, password, API key or configuration file.

`sqlite3` is a Python standard-library module. It stores tables in a normal file: `artifacts/full/examflow.sqlite3` (and `artifacts/starter/examflow.sqlite3`). The application creates the database, schema and data automatically. Both generated demonstrations are already included.

Version **1.0.1** fixes Windows `WinError 32` during temporary database cleanup. SQLite's transaction context does not close a connection; all owned connection scopes now explicitly close their handles, including on failure. Existing databases need no migration.

## What happens

1. Generate or reuse immutable, fixed-seed master data and typed lifecycle history.
2. Validate source data, build the enrollment conflict graph, and append a scheduling run.
3. Independently audit source records and accepted intervals.
4. Evaluate five invalid cases and three clean/boundary controls against separate ground truth.
5. Build twice independently and compare all 23 tables' row counts and canonical SHA-256 checksums, scheduling results and fixtures.
6. Export CSV, JSON, parent-first SQL seed data, metrics, audit evidence and a self-contained HTML report.

Every connection explicitly enables SQLite foreign keys. History tables reject updates/deletes, and all primary keys are immutable. Rerunning appends a new `RUN-...`; it retains earlier assignments and events. Runs are alternative versions of the timetable, so bookings from different runs do not conflict with each other. The root exports/report show the latest run; table exports and the database contain all runs. A different seed/profile/scale requires a different output directory.

## Commands

```powershell
# Fast starter build (250 students / 30 exams / 12 rooms / 24 invigilators)
python -m examflow demo --profile starter --output scratch-demo

# Full-scale build; choose a new directory for a different configuration
python -m examflow demo --profile full --seed 20261022 --output my-full-demo

# Same generator, custom scale (500 / 30 / 10 / 20)
python -m examflow demo --profile full --scale 0.1 --output scaled-demo

# Run automated tests, including full-scale acceptance
python -m unittest discover -s tests -v

# Tests plus source/CSV/metrics/checksums/SQL-restore/report-link verification
python tools/verify.py

# Independently revalidate the latest committed run
python -m examflow validate --db artifacts/full/examflow.sqlite3

# Audit imported JSON or CSV, including expected scheduled-exam coverage
python -m examflow validate --db artifacts/full/examflow.sqlite3 --assignments artifacts/full/assignments.json

# For a deliberately partial import, skip only completeness, not hard rules
python -m examflow validate --db artifacts/full/examflow.sqlite3 --assignments example.json --allow-partial

# Learner timetable and exception lookup
python -m examflow student --id STU-000001 --db artifacts/full/examflow.sqlite3

# List previous runs, or append a run without refreshing exports
python -m examflow runs --db artifacts/full/examflow.sqlite3
python -m examflow schedule --db artifacts/full/examflow.sqlite3

# Two fresh builds, without changing the bundled database
python -m examflow reproduce --profile full --output reproduction.json
```

Replace the initial `python` in any command with `py -3` if needed. Successful checks exit with code 0; invalid data or failed checks exit with code 2. In PowerShell, inspect `$LASTEXITCODE` immediately after a command.

Inspect the database without installing a SQLite tool:

```powershell
python -c "import sqlite3; c=sqlite3.connect('artifacts/full/examflow.sqlite3'); c.execute('PRAGMA foreign_keys=ON'); print(c.execute('SELECT run_id,status,COUNT(*) FROM ExamOutcome GROUP BY run_id,status').fetchall()); c.close()"
```

Restore the SQL seed into a **new, empty** file:

```powershell
python -c "from pathlib import Path; import sqlite3; c=sqlite3.connect('restored.sqlite3'); c.executescript(Path('artifacts/full/exports/database_seed.sql').read_text(encoding='utf-8')); print(c.execute('PRAGMA foreign_key_check').fetchall()); c.close()"
```

## Outputs

| Path | Contents |
|---|---|
| `artifacts/{starter,full}/report.html` | Searchable offline timetable, exceptions, metrics, evaluation and export links |
| `examflow.sqlite3` | Usable database, sources, all scheduling runs and events |
| `assignments.csv/json`, `invigilator_allocations.csv` | Latest accepted decisions and staffing bridge |
| `unassigned.csv/json` | Every unassigned planned exam, reason and rejection evidence |
| `exports/csv/`, `exports/json/` | All 23 tables, one file per table |
| `exports/database_seed.sql` | Schema + parent-first inserts, full database reconstruction |
| `fixtures/inputs.json` | Neutral case IDs and assignments; no anomaly labels |
| `fixtures/ground_truth.csv/json` | Separate expected labels, rationale and source proofs |
| `validation_summary.json`, `evaluation.json` | Integrity/join checks, violations, confusion counts and per-rule precision/recall |
| `metrics.json`, `*_usage.csv`, `conflict_graph.csv` | Derived operational outputs and explicit denominators |
| `checksums.json`, `reproducibility.json` | Canonical per-table checksums and independent two-build comparison |
| `source_manifest.json` | Recipe, seed, schema version, provenance and separation policy |
| `docs/` | Dictionary, schema, relationships, coverage, walkthrough, verification and AI disclosure |

## Assumptions and limitations

The deterministic greedy heuristic prioritizes graph degree, duration and demand. It checks four candidate starts on each of ten weekdays; it offers no optimality guarantee. One exam uses one room, with the entire exam extended by the maximum approved extra-time percentage (rounded up to a minute). Staffing is one invigilator per 40 students, rounded up. Equipment is a binary room capability; the effective seat count is assumed usable for that equipment. There are no walking breaks, room-splitting, individual accommodation sessions or soft fairness objectives.

Intervals are `[start, end)` in Asia/Kolkata, stored with `+05:30`. Enrollment/student/support state is stable during each exam window; mid-window changes are rejected by source validation. Room capacities, closures and invigilator availability vary through the window and are checked over the whole assigned interval. Master generation is immutable per database; no administrative editing UI is provided. This is a CLI and static report, with no authentication, web hosting or external integrations.

The eight fixture cases provide regression coverage rather than a population accuracy estimate. Automated verification ran on Linux/Python 3.12.14. The Windows setup check passed with Python 3.14.6 and SQLite 3.50.4; version 1.0.1 addresses the temporary-file cleanup error from the initial Windows demo. See the verification record for platform coverage.

Read [the walkthrough](docs/WALKTHROUGH.md), [requirements coverage](docs/REQUIREMENTS_COVERAGE.md), [verification](docs/VERIFICATION.md) and [AI disclosure](docs/AI_USAGE.md).

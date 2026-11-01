# AI use

ChatGPT/Codex assisted with architecture, schema design, implementation, synthetic-data generation, scheduling, validation, tests and documentation. It also helped diagnose and fix the Windows SQLite cleanup issue. The available prompts are recorded in [PROMPT_HISTORY.md](PROMPT_HISTORY.md).

## Design choices

The solution uses Python's standard library and SQLite, a deterministic conflict-graph heuristic, one room per exam, whole-exam extra-time extension, separate anomaly fixtures and ground truth, and append-only scheduling history. It uses synthetic data without external datasets, paid services or API keys.

## Verification

The recorded checks cover both dataset sizes, 37 automated tests, independent source and timetable validation, all five required negative scenarios, CSV imports, SQL reconstruction, usage reconciliation and fixed-seed reproducibility. Commands, environment details and results are in `artifacts/tests.log`, `artifacts/verification_execution.json` and [VERIFICATION.md](VERIFICATION.md).

The packaged verification evidence was generated on Linux with Python 3.12.14. Running `python tools/verify.py` refreshes the test log and records the actual local platform, versions and results in `artifacts/verification_execution.json`. The Windows setup check passed with Python 3.14.6 and SQLite 3.50.4; version 1.0.1 closes the handles behind the original temporary-file cleanup error and includes regression tests. Visual browser rendering is outside the automated checks.

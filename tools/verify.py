"""Run tests and verify shipped data/SQL/HTML from the project root, stdlib only."""
from contextlib import closing
import csv
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import platform
import re
import sqlite3
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from examflow.export import table_checksums, write_json
from examflow.fixtures import evaluate
from examflow.metrics import calculate
from examflow.schema import connect
from examflow.scheduler import read_assignments
from examflow.validate import detect, validate_run


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.rows = set(), [], 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
        if tag == "tr" and "data-search" in attrs:
            self.rows += 1


def main():
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    tests = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (ROOT / "artifacts").mkdir(exist_ok=True)
    (ROOT / "artifacts/tests.log").write_text(tests.stdout, encoding="utf-8")
    print("\n".join(tests.stdout.strip().splitlines()[-4:]), flush=True)
    count = re.search(r"Ran (\d+) tests", tests.stdout)
    result = {"executed_at_utc": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
              "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version, "command": "python tools/verify.py",
              "tests": {"command": "python -m unittest discover -s tests -v", "count": int(count.group(1)) if count else None,
                        "exit_code": tests.returncode, "passed": tests.returncode == 0, "log": "artifacts/tests.log"},
              "profiles": {}, "windows_execution": "not performed", "visual_html_review": "not performed: local browser executable unavailable"}
    try:
        assert tests.returncode == 0, "Automated tests failed"
        for profile in ("starter", "full"):
            folder = ROOT / "artifacts" / profile
            with closing(connect(folder / "examflow.sqlite3")) as conn:
                rid = conn.execute("SELECT run_id FROM SchedulingRun ORDER BY run_id DESC LIMIT 1").fetchone()[0]
                assignments = read_assignments(conn, rid)
                validation = validate_run(conn, rid, assignments)
                assert validation["passed"], validation
                evaluation = evaluate(conn, folder / "fixtures", rid)
                assert evaluation["passed"], evaluation
                assert calculate(conn, rid, assignments) == json.loads((folder / "metrics.json").read_text()), "Saved metrics differ from source-derived metrics"
                assert table_checksums(conn) == json.loads((folder / "checksums.json").read_text()), "Saved checksums differ"
                reproduction = json.loads((folder / "reproducibility.json").read_text())
                assert reproduction["passed"] and all(c["matched"] for c in reproduction["tables"].values())
                assert len(reproduction["tables"]) == 23 and reproduction["excluded_columns"] == []
                with (folder / "assignments.csv").open(encoding="utf-8", newline="") as file:
                    imported = list(csv.DictReader(file))
                for a in imported:
                    a["invigilator_ids"] = json.loads(a["invigilator_ids"])
                assert not detect(conn, imported, expected_exam_ids={a["exam_id"] for a in assignments}), "CSV import audit failed"
                with tempfile.TemporaryDirectory(prefix="examflow-sql-restore-") as temporary:
                    with closing(connect(Path(temporary) / "restored.sqlite3")) as restored:
                        restored.executescript((folder / "exports/database_seed.sql").read_text(encoding="utf-8"))
                        assert table_checksums(restored) == table_checksums(conn), "Full SQL reconstruction differs"
                        assert not list(restored.execute("PRAGMA foreign_key_check"))
                html = ReportParser()
                html.feed((folder / "report.html").read_text(encoding="utf-8"))
                broken = [link for link in html.links if (link.startswith("#") and link[1:] not in html.ids)
                          or (not link.startswith("#") and not (folder / link).is_file())]
                assert not broken and html.rows == len(assignments), f"HTML links/rows: {broken}"
                result["profiles"][profile] = {"passed": True, "run_id": rid, "assignments": len(assignments),
                                               "source_and_schedule": True, "evaluation": True, "reproducibility_report": True,
                                               "checksums_and_metrics_recomputed": True, "csv_import": True,
                                               "sql_restore_all_table_checksums": True, "html_links_and_row_counts": True}
                print(f"{profile}: source, schedule, fixtures, CSV, metrics, checksums, SQL restore, HTML links PASS", flush=True)
        result["passed"] = True
    except (AssertionError, OSError, ValueError, sqlite3.Error) as exc:
        result["passed"] = False
        result["error"] = str(exc)
        print("FAIL:", exc, file=sys.stderr)
    write_json(ROOT / "artifacts/verification_execution.json", result)
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

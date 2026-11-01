"""Run `python -m examflow --help` for commands. No third-party packages."""
from contextlib import closing
import argparse
import csv
import json
from pathlib import Path
import sqlite3
import sys

from .export import export_all, write_json
from .fixtures import evaluate, write_fixtures
from .generate import configuration, generate
from .metrics import calculate
from .report import render
from .reproduce import reproduce
from .schema import connect, write_dictionary
from .scheduler import read_assignments, schedule
from .validate import detect, validate_run, validate_source


def latest(conn, value=None):
    if value:
        found = conn.execute("SELECT run_id FROM SchedulingRun WHERE run_id=?", (value,)).fetchone()
    else:
        found = conn.execute("SELECT run_id FROM SchedulingRun ORDER BY run_id DESC LIMIT 1").fetchone()
    if found is None:
        raise ValueError("No requested scheduling run; run the schedule/demo command first")
    return found[0]


def require_db(path):
    if not Path(path).is_file():
        raise ValueError("Database not found; run demo or generate first")
    return connect(path)


def demo_one(root, config):
    root = Path(root)
    print(f"[{config['profile']}] Generate/reuse immutable sources", flush=True)
    generate(root / "examflow.sqlite3", config)
    with closing(connect(root / "examflow.sqlite3")) as conn:
        # Reject changed/corrupt input before graph construction or placement.
        initial = validate_source(conn)
        if not initial["passed"]:
            write_json(root / "validation_summary.json", initial)
            raise ValueError("Source validation failed; see validation_summary.json")
        run_id = schedule(conn)
        assignments = read_assignments(conn, run_id)
        validation = validate_run(conn, run_id, assignments)
        write_fixtures(conn, root / "fixtures")
        evaluation = evaluate(conn, root / "fixtures", run_id)
        metrics = calculate(conn, run_id, assignments)
        write_json(root / "validation_summary.json", validation)
        write_json(root / "evaluation.json", evaluation)
        write_json(root / "metrics.json", metrics)
        print(f"[{config['profile']}] {metrics['scheduled']} scheduled; {metrics['unassigned']} unassigned; {validation['violation_count']} hard violations", flush=True)
        reproducibility = reproduce(config, root / "reproducibility.json")
        export_all(conn, run_id, assignments, root, metrics)
        render(conn, root, metrics, validation, evaluation, reproducibility, assignments)
        passed = validation["passed"] and evaluation["passed"] and reproducibility["passed"]
        write_json(root / "demo_summary.json", {"passed": passed, "run_id": run_id,
                   "source_counts": metrics["source_counts"], "scheduled": metrics["scheduled"], "unassigned": metrics["unassigned"],
                   "validation_passed": validation["passed"], "evaluation_passed": evaluation["passed"], "reproducibility_passed": reproducibility["passed"]})
        print(f"[{config['profile']}] {'PASS' if passed else 'FAIL'}: validation, fixtures, reproducibility; report: {root / 'report.html'}", flush=True)
        return passed


def main(argv=None):
    parser = argparse.ArgumentParser(description="ExamFlow: synthetic exam scheduling with independent validation")
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="Check Python and built-in SQLite prerequisites")
    for command in ("demo", "generate", "reproduce"):
        p = sub.add_parser(command)
        p.add_argument("--profile", choices=("starter", "full"), default="full")
        p.add_argument("--scale", type=float, default=1)
        p.add_argument("--seed", type=int, default=20261022)
        if command == "demo":
            p.add_argument("--both", action="store_true", help="Build starter and full under output/{starter,full}")
            p.add_argument("--output", type=Path, default=Path("artifacts/full"))
        elif command == "generate":
            p.add_argument("--db", type=Path, required=True)
        else:
            p.add_argument("--output", type=Path, default=Path("reproducibility.json"))
    for command in ("schedule", "validate", "student", "runs", "evaluate"):
        p = sub.add_parser(command)
        p.add_argument("--db", type=Path, default=Path("artifacts/full/examflow.sqlite3"))
        if command in ("validate", "student", "evaluate"):
            p.add_argument("--run")
        if command == "validate":
            p.add_argument("--assignments", type=Path, help="Independent audit of imported JSON/CSV assignments")
            p.add_argument("--allow-partial", action="store_true", help="Skip exam-set coverage only for imported data")
            p.add_argument("--output", type=Path, default=Path("validation_import.json"))
        if command == "student":
            p.add_argument("--id", required=True)
        if command == "evaluate":
            p.add_argument("--fixtures", type=Path, default=Path("artifacts/full/fixtures"))
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11) or sqlite3.sqlite_version_info < (3, 37, 0):
        parser.error("Python >=3.11 with built-in SQLite >=3.37 is required; install a current Python from python.org")
    try:
        if args.command == "doctor":
            print(json.dumps({"passed": True, "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
                              "third_party_packages_required": 0, "sqlite_installation_required": False}, indent=2))
            return 0
        if args.command in ("demo", "generate", "reproduce"):
            config = configuration(args.profile, args.scale, args.seed)
            if args.command == "demo":
                write_dictionary(Path(__file__).resolve().parent.parent / "docs")
                if args.both:
                    # Evaluate both even when the first fails; never short-circuit a promised build.
                    statuses = [demo_one(args.output / profile, configuration(profile, args.scale, args.seed)) for profile in ("starter", "full")]
                    return 0 if all(statuses) else 2
                return 0 if demo_one(args.output, config) else 2
            if args.command == "generate":
                generate(args.db, config)
                print(f"Database ready: {args.db}; source configuration is immutable")
                return 0
            result = reproduce(config, args.output)
            print(f"Reproducibility: {'PASS' if result['passed'] else 'FAIL'}; {args.output}")
            return 0 if result["passed"] else 2
        with closing(require_db(args.db)) as conn:
            if args.command == "runs":
                print(json.dumps([dict(r) for r in conn.execute("SELECT * FROM SchedulingRun ORDER BY run_id")], indent=2))
                return 0
            if args.command == "schedule":
                source = validate_source(conn)
                if not source["passed"]:
                    print(json.dumps(source, indent=2))
                    return 2
                rid = schedule(conn)
                validation = validate_run(conn, rid, read_assignments(conn, rid))
                print(json.dumps({"run_id": rid, "passed": validation["passed"], "note": "Database history appended. Run demo to refresh exported reports as well."}, indent=2))
                return 0 if validation["passed"] else 2
            rid = latest(conn, args.run)
            if args.command == "validate":
                if args.assignments:
                    if args.assignments.suffix.lower() == ".csv":
                        with args.assignments.open(encoding="utf-8", newline="") as file:
                            imported = list(csv.DictReader(file))
                        for a in imported:
                            a["invigilator_ids"] = json.loads(a["invigilator_ids"])
                    else:
                        imported = json.loads(args.assignments.read_text(encoding="utf-8"))
                    if not isinstance(imported, list):
                        raise ValueError("Assignment import must be a JSON array or assignment CSV, not a labelled fixture document")
                    expected = None if args.allow_partial else {a["exam_id"] for a in read_assignments(conn, rid)}
                    source = validate_source(conn)
                    violations = detect(conn, imported, expected_exam_ids=expected)
                    result = {"passed": source["passed"] and not violations, "source": source, "hard_constraint_violations": violations,
                              "violation_count": len(violations), "imported_rows": len(imported), "partial_import": args.allow_partial}
                else:
                    result = validate_run(conn, rid, read_assignments(conn, rid))
                write_json(args.output, result)
                print(json.dumps({"passed": result["passed"], "violation_count": result["violation_count"], "report": str(args.output)}, indent=2))
                return 0 if result["passed"] else 2
            if args.command == "student":
                if not conn.execute("SELECT 1 FROM Student WHERE student_id=?", (args.id,)).fetchone():
                    raise ValueError("Unknown student ID")
                data = [dict(r) for r in conn.execute("""SELECT e.exam_id,e.title,o.status,o.reason_code,a.room_id,a.starts_at,a.ends_at
                    FROM Enrollment en JOIN Exam e ON e.course_id=en.course_id JOIN ExamOutcome o ON o.exam_id=e.exam_id AND o.run_id=?
                    LEFT JOIN ScheduleAssignment a ON a.run_id=o.run_id AND a.assignment_id=o.assignment_id
                    WHERE en.student_id=? AND en.status='ACTIVE' ORDER BY coalesce(a.starts_at,e.window_start),e.exam_id""", (rid, args.id))]
                print(json.dumps({"student_id": args.id, "run_id": rid, "exams": data}, indent=2))
                return 0
            if args.command == "evaluate":
                result = evaluate(conn, args.fixtures, rid)
                print(json.dumps(result, indent=2))
                return 0 if result["passed"] else 2
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

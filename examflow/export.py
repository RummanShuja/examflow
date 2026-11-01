"""Portable CSV/JSON/SQL exports, canonical checksums and source manifest."""
from pathlib import Path
import csv
import hashlib
import json

from .common import canonical, rows
from .domain import Facts, conflict_graph
from .schema import SCHEMA_VERSION, TABLES, schema_sql


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def write_csv(path, data, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or (list(data[0]) if data else [])
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in data:
            writer.writerow({k: canonical(v) if isinstance(v, (list, dict)) else v for k, v in row.items()})


def table_checksums(conn):
    result = {}
    for t in TABLES:
        data = sorted(rows(conn, t.name), key=lambda r: tuple(r[k] for k in t.pk))
        hasher = hashlib.sha256()
        for record in data:
            hasher.update((canonical(record) + "\n").encode("utf-8"))
        result[t.name] = {"rows": len(data), "sha256": hasher.hexdigest()}
    return result


def _sql(value):
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + value.replace("'", "''") + "'"


def export_all(conn, run_id, assignments, root, metrics):
    root = Path(root)
    folder = root / "exports"
    folder.mkdir(parents=True, exist_ok=True)
    sql_path = folder / "database_seed.sql"
    with sql_path.open("w", encoding="utf-8", newline="\n") as sql:
        sql.write("-- Rebuild into a NEW empty SQLite database; parent tables/records first.\n")
        sql.write("PRAGMA foreign_keys=ON;\nBEGIN TRANSACTION;\n")
        sql.write(schema_sql())
        for table in TABLES:
            data = sorted(rows(conn, table.name), key=lambda r: tuple(r[k] for k in table.pk))
            fields = [f.name for f in table.fields]
            write_csv(folder / "csv" / (table.name + ".csv"), data, fields)
            write_json(folder / "json" / (table.name + ".json"), data)
            for record in data:
                sql.write('INSERT INTO "' + table.name + '" VALUES (' + ",".join(_sql(record[f]) for f in fields) + ");\n")
        sql.write("COMMIT;\nPRAGMA foreign_key_check;\n")
    write_json(root / "assignments.json", assignments)
    write_csv(root / "assignments.csv", assignments,
              ("run_id", "assignment_id", "exam_id", "room_id", "starts_at", "ends_at", "status", "invigilator_ids"))
    outcomes = [dict(r) for r in conn.execute("SELECT * FROM ExamOutcome WHERE run_id=? AND status='UNASSIGNED' ORDER BY exam_id", (run_id,))]
    write_json(root / "unassigned.json", outcomes)
    write_csv(root / "unassigned.csv", outcomes, ("run_id", "exam_id", "status", "assignment_id", "reason_code", "evidence_json"))
    allocations = [dict(r) for r in conn.execute("SELECT * FROM InvigilatorAllocation WHERE run_id=? ORDER BY assignment_id, invigilator_id", (run_id,))]
    write_csv(root / "invigilator_allocations.csv", allocations, ("run_id", "assignment_id", "invigilator_id"))
    _, edges = conflict_graph(Facts(conn))
    write_csv(root / "conflict_graph.csv", edges, ("exam_a", "exam_b", "shared_students"))
    write_csv(root / "room_usage.csv", metrics["rooms"])
    write_csv(root / "invigilator_usage.csv", metrics["invigilators"])
    write_json(root / "checksums.json", table_checksums(conn))
    config = json.loads(conn.execute("SELECT config_json FROM Dataset").fetchone()[0])
    write_json(root / "source_manifest.json", {
        "schema_version": SCHEMA_VERSION, "configuration": config, "seed": config["seed"],
        "provenance": "Entirely synthetic; created by examflow/generate.py using Python random.Random(seed).",
        "external_sources": [], "private_or_personal_data": False, "source_urls": [],
        "license_or_terms": "No external datasets or third-party code snippets incorporated; source and data are supplied for this exam-scheduling project.",
        "recipe": "Round-robin cohorts; five core courses + one PRNG-selected shared elective per learner; small labelled-by-state withdrawn enrollment history; weighted durations; effective resource intervals; approved/pending/rejected support.",
        "derived_values": "Source enrollments and approvals determine demand, duration, accessibility, staffing and outcomes; anomaly labels follow controlled rule violations.",
        "simulation_dates": "Database timestamps describe a synthetic 2026 assessment period, not actual artifact creation times.",
        "ground_truth_separation": "Only fixtures/evaluate() opens ground_truth.json; labels are absent from all master tables and fixture inputs.",
        "checksum_contract": "SHA-256 over canonical sorted-key JSON records, UTF-8 plus LF, ordered by declared primary key. No DB columns excluded."})

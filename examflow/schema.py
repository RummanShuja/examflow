"""Schema and field-level dictionary from one declarative source of truth."""
from dataclasses import dataclass
from pathlib import Path
import json
import sqlite3

SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class Field:
    name: str
    kind: str = "TEXT"
    required: bool = True
    rule: str = "Non-empty text"
    units: str = "none"
    allowed: tuple = ()
    check: str = ""


def f(name, kind="TEXT", required=True, rule="Non-empty text", units="none", allowed=(), check=""):
    return Field(name, kind, required, rule, units, tuple(allowed), check)


def ts(name, required=True):
    return f(name, required=required, rule="ISO 8601 with +05:30 offset; half-open intervals", units="Asia/Kolkata timestamp")


def ident(name, example):
    return f(name, rule=f"Immutable deterministic identifier, e.g. {example}")


@dataclass(frozen=True)
class Table:
    name: str
    fields: tuple
    pk: tuple
    foreign: tuple = ()
    unique: tuple = ()
    checks: tuple = ()
    note: str = ""


def t(name, fields, pk, foreign=(), unique=(), checks=(), note=""):
    return Table(name, tuple(fields), tuple(pk.split(",")), tuple(foreign), tuple(unique), tuple(checks), note)


TABLES = [
    t("Dataset", [f("dataset_id", check="dataset_id = 'DATASET-000001'"), f("schema_version"),
                  f("seed", "INTEGER", rule="Nonnegative PRNG seed", check="seed >= 0"),
                  f("profile", allowed=("starter", "full")), f("scale", "REAL", rule="Positive scale multiplier", check="scale > 0"),
                  f("config_json", rule="Canonical JSON configuration, no labels"), f("timezone", allowed=("Asia/Kolkata",)),
                  ts("generated_at")], "dataset_id", note="One immutable generation configuration per database."),
    t("Cohort", [ident("cohort_id", "COH-000001"), f("name")], "cohort_id", unique=(("name",),)),
    t("Student", [ident("student_id", "STU-000001"), f("synthetic_name"), f("cohort_id"),
                  f("status", allowed=("ACTIVE", "INACTIVE")), ts("effective_from"), ts("effective_to", False)],
      "student_id", foreign=(("cohort_id", "Cohort", "cohort_id"),),
      checks=("effective_to IS NULL OR effective_to > effective_from",)),
    t("Course", [ident("course_id", "CRS-000001"), f("title"),
                 f("category", allowed=("CORE", "ELECTIVE")), f("cohort_id", required=False, rule="Required for CORE; null for shared ELECTIVE")],
      "course_id", foreign=(("cohort_id", "Cohort", "cohort_id"),),
      checks=("(category = 'CORE' AND cohort_id IS NOT NULL) OR (category = 'ELECTIVE' AND cohort_id IS NULL)",)),
    t("Enrollment", [ident("enrollment_id", "ENR-000001"), f("student_id"), f("course_id"),
                     f("status", allowed=("ACTIVE", "WITHDRAWN")), ts("effective_from"), ts("effective_to", False)],
      "enrollment_id", foreign=(("student_id", "Student", "student_id"), ("course_id", "Course", "course_id")),
      unique=(("student_id", "course_id"),), checks=("effective_to IS NULL OR effective_to > effective_from",
      "(status = 'ACTIVE' AND effective_to IS NULL) OR (status = 'WITHDRAWN' AND effective_to IS NOT NULL)"),
      note="Student N:M Course bridge; current states are stable across the scheduling horizon."),
    t("Exam", [ident("exam_id", "EXAM-2026-000001"), f("course_id"), f("title"),
               f("base_duration_minutes", "INTEGER", rule="Positive base writing duration", units="minutes", check="base_duration_minutes > 0"),
               ts("window_start"), ts("window_end"), f("status", allowed=("PLANNED", "CANCELLED"))],
      "exam_id", foreign=(("course_id", "Course", "course_id"),), unique=(("course_id",),), checks=("window_end > window_start",),
      note="One examination per course in this assessment period; no retakes."),
    t("Equipment", [ident("equipment_id", "EQ-COMPUTER"), f("name")], "equipment_id", unique=(("name",),)),
    t("ExamEquipmentRequirement", [f("exam_id"), f("equipment_id")], "exam_id,equipment_id",
      foreign=(("exam_id", "Exam", "exam_id"), ("equipment_id", "Equipment", "equipment_id")),
      note="Exam N:M Equipment bridge. Equipment is a binary capability, not a seat count."),
    t("Room", [ident("room_id", "ROOM-000001"), f("name"),
               f("accessible", "INTEGER", rule="Boolean physical accessibility", allowed=(0, 1)),
               f("status", allowed=("OPEN", "RETIRED")), ts("effective_from"), ts("effective_to", False)],
      "room_id", unique=(("name",),), checks=("effective_to IS NULL OR effective_to > effective_from",)),
    t("RoomCapacity", [ident("capacity_id", "CAP-000001"), f("room_id"),
                       f("seats", "INTEGER", rule="Positive usable exam seats", units="seats", check="seats > 0"),
                       ts("effective_from"), ts("effective_to")], "capacity_id", foreign=(("room_id", "Room", "room_id"),),
      unique=(("room_id", "effective_from"),), checks=("effective_to > effective_from",),
      note="Room 1:N capacity versions, which must not overlap. Capacity must cover the whole exam."),
    t("RoomEquipment", [f("room_id"), f("equipment_id")], "room_id,equipment_id",
      foreign=(("room_id", "Room", "room_id"), ("equipment_id", "Equipment", "equipment_id"))),
    t("RoomOpening", [ident("opening_id", "OPN-000001"), f("room_id"), ts("starts_at"), ts("ends_at")],
      "opening_id", foreign=(("room_id", "Room", "room_id"),), unique=(("room_id", "starts_at"),), checks=("ends_at > starts_at",)),
    t("RoomClosure", [ident("closure_id", "CLS-000001"), f("room_id"), ts("starts_at"), ts("ends_at"),
                      f("reason", allowed=("MAINTENANCE", "CAMPUS_EVENT"))], "closure_id",
      foreign=(("room_id", "Room", "room_id"),), unique=(("room_id", "starts_at"),), checks=("ends_at > starts_at",)),
    t("Invigilator", [ident("invigilator_id", "INV-000001"), f("synthetic_name"),
                      f("status", allowed=("ACTIVE", "INACTIVE")), ts("effective_from"), ts("effective_to", False)],
      "invigilator_id", checks=("effective_to IS NULL OR effective_to > effective_from",)),
    t("Availability", [ident("availability_id", "AVL-000001"), f("invigilator_id"), ts("starts_at"), ts("ends_at"),
                       f("status", allowed=("AVAILABLE", "CANCELLED"))], "availability_id",
      foreign=(("invigilator_id", "Invigilator", "invigilator_id"),), unique=(("invigilator_id", "starts_at"),),
      checks=("ends_at > starts_at",)),
    t("Accommodation", [ident("accommodation_id", "ACC-000001"), f("student_id"),
                        f("exam_id", required=False, rule="Null applies to all enrolled exams; otherwise applies to this exam only"),
                        f("kind", allowed=("EXTRA_TIME", "ACCESSIBLE_ROOM")),
                        f("extra_percent", "INTEGER", rule="0 for accessibility; 25 or 50 for extra time", units="percent", allowed=(0, 25, 50)),
                        f("status", allowed=("PENDING", "APPROVED", "REJECTED")), ts("effective_from"), ts("effective_to")],
      "accommodation_id", foreign=(("student_id", "Student", "student_id"), ("exam_id", "Exam", "exam_id")),
      checks=("effective_to > effective_from", "(kind = 'EXTRA_TIME' AND extra_percent > 0) OR (kind = 'ACCESSIBLE_ROOM' AND extra_percent = 0)")),
    t("ExamRequirement", [f("exam_id"),
                          f("enrolled_count", "INTEGER", rule="Derived active enrollment count at window_start", units="students", check="enrolled_count >= 0"),
                          f("duration_minutes", "INTEGER", rule="ceil(base_duration * (100 + max_extra_percent) / 100)", units="minutes", check="duration_minutes > 0"),
                          f("max_extra_percent", "INTEGER", rule="Maximum approved applicable extra time; 0 if none", units="percent", allowed=(0, 25, 50)),
                          f("accessible_required", "INTEGER", rule="Any enrolled learner with approved accessibility support", allowed=(0, 1)),
                          f("invigilators_required", "INTEGER", rule="ceil(enrolled_count / 40)", units="people", check="invigilators_required >= 0")],
      "exam_id", foreign=(("exam_id", "Exam", "exam_id"),), note="Exam 1:1 derived requirement; never a feature carrying anomaly labels."),
    t("LifecycleEvent", [ident("event_id", "LFE-000001"),
                         *[f(n, required=False, rule="Exactly one entity FK is non-null") for n in
                           ("student_id", "enrollment_id", "exam_id", "room_id", "invigilator_id", "availability_id", "accommodation_id")],
                         f("from_state", required=False, rule="Previous enum state; null only on creation"),
                         f("to_state", allowed=("ACTIVE", "INACTIVE", "WITHDRAWN", "PLANNED", "CANCELLED", "OPEN", "RETIRED", "AVAILABLE", "PENDING", "APPROVED", "REJECTED")),
                         ts("occurred_at")], "event_id",
      foreign=tuple((c, tab, c) for c, tab in (("student_id", "Student"), ("enrollment_id", "Enrollment"), ("exam_id", "Exam"),
                    ("room_id", "Room"), ("invigilator_id", "Invigilator"), ("availability_id", "Availability"), ("accommodation_id", "Accommodation"))),
      checks=("(student_id IS NOT NULL) + (enrollment_id IS NOT NULL) + (exam_id IS NOT NULL) + (room_id IS NOT NULL) + (invigilator_id IS NOT NULL) + (availability_id IS NOT NULL) + (accommodation_id IS NOT NULL) = 1",),
      note="Append-only typed event history; all entity references have actual FKs."),
    t("SchedulingRun", [ident("run_id", "RUN-000001"), f("algorithm", allowed=("degree-greedy-v1",)),
                        f("status", allowed=("COMPLETED",)), ts("started_at"), ts("completed_at"),
                        f("config_json", rule="Canonical candidate-start policy and immutable source configuration")], "run_id",
      checks=("completed_at >= started_at",), note="Committed atomically only after all decisions; both start/completion events retained."),
    t("ScheduleAssignment", [f("run_id"), ident("assignment_id", "ASN-EXAM-2026-000001-ROOM-000001"), f("exam_id"), f("room_id"),
                             ts("starts_at"), ts("ends_at"), f("status", allowed=("ACCEPTED",))], "run_id,assignment_id",
      foreign=(("run_id", "SchedulingRun", "run_id"), ("exam_id", "Exam", "exam_id"), ("room_id", "Room", "room_id")),
      unique=(("run_id", "exam_id"),), checks=("ends_at > starts_at", "assignment_id = 'ASN-' || exam_id || '-' || room_id"),
      note="Immutable decisions. Natural assignment ID can repeat in separate runs; composite PK prevents collisions."),
    t("InvigilatorAllocation", [f("run_id"), f("assignment_id"), f("invigilator_id")], "run_id,assignment_id,invigilator_id",
      foreign=(("run_id,assignment_id", "ScheduleAssignment", "run_id,assignment_id"), ("invigilator_id", "Invigilator", "invigilator_id")),
      note="Assignment N:M Invigilator bridge, scoped to one scheduling run."),
    t("ExamOutcome", [f("run_id"), f("exam_id"), f("status", allowed=("SCHEDULED", "UNASSIGNED")),
                      f("assignment_id", required=False, rule="Required iff SCHEDULED"),
                      f("reason_code", required=False, rule="Required iff UNASSIGNED", allowed=("NO_ENROLLMENTS", "NO_COMPATIBLE_ROOM", "NO_FEASIBLE_SLOT")),
                      f("evidence_json", rule="JSON counters and human-readable evidence; never ground truth")], "run_id,exam_id",
      foreign=(("run_id", "SchedulingRun", "run_id"), ("exam_id", "Exam", "exam_id"), ("run_id,assignment_id", "ScheduleAssignment", "run_id,assignment_id")),
      checks=("(status = 'SCHEDULED' AND assignment_id IS NOT NULL AND reason_code IS NULL) OR (status = 'UNASSIGNED' AND assignment_id IS NULL AND reason_code IS NOT NULL)",)),
    t("DecisionEvent", [ident("event_id", "DEC-RUN-000001-000001"), f("run_id"),
                        f("exam_id", required=False, rule="Null for run-wide events"),
                        f("kind", allowed=("RUN_STARTED", "EXAM_ASSIGNED", "EXAM_UNASSIGNED", "RUN_COMPLETED")),
                        ts("occurred_at"), f("payload_json", rule="Canonical JSON decision and rejection evidence")], "event_id",
      foreign=(("run_id", "SchedulingRun", "run_id"), ("exam_id", "Exam", "exam_id")), note="Append-only audit trail."),
]

TABLE_NAMES = [x.name for x in TABLES]
HISTORY_TABLES = ("LifecycleEvent", "SchedulingRun", "ScheduleAssignment", "InvigilatorAllocation", "ExamOutcome", "DecisionEvent")


def schema_sql():
    chunks = ["-- ExamFlow schema v" + SCHEMA_VERSION, "PRAGMA foreign_keys = ON;"]
    for table in TABLES:
        parts = []
        for field in table.fields:
            text = f'"{field.name}" {field.kind}' + (" NOT NULL" if field.required else "")
            if field.kind == "TEXT":
                text += f' CHECK ("{field.name}" IS NULL OR length("{field.name}") > 0)'
            if field.allowed:
                values = ", ".join(str(v) if isinstance(v, int) else "'" + v + "'" for v in field.allowed)
                text += f' CHECK ("{field.name}" IN ({values}))'
            if field.check:
                text += " CHECK (" + field.check + ")"
            parts.append(text)
        parts.append("PRIMARY KEY (" + ",".join(table.pk) + ")")
        parts += ["FOREIGN KEY (" + a + ") REFERENCES " + b + "(" + c + ")" for a, b, c in table.foreign]
        parts += ["UNIQUE (" + ",".join(u) + ")" for u in table.unique]
        parts += ["CHECK (" + c + ")" for c in table.checks]
        chunks.append('CREATE TABLE "' + table.name + '" (\n  ' + ",\n  ".join(parts) + "\n) STRICT;")
    chunks += ["CREATE INDEX idx_enrollment_course ON Enrollment(course_id, status);",
               "CREATE INDEX idx_accommodation_student ON Accommodation(student_id, status);",
               "CREATE INDEX idx_availability_staff ON Availability(invigilator_id, starts_at);",
               "CREATE INDEX idx_lifecycle_enrollment ON LifecycleEvent(enrollment_id);",
               "CREATE INDEX idx_assignment_exam ON ScheduleAssignment(exam_id);"]
    for table in HISTORY_TABLES:
        for operation in ("UPDATE", "DELETE"):
            chunks.append(f"CREATE TRIGGER immutable_{table}_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'append-only history'); END;")
    for table in TABLES:
        changed = " OR ".join(f'NEW."{k}" IS NOT OLD."{k}"' for k in table.pk)
        chunks.append(f'CREATE TRIGGER immutable_pk_{table.name} BEFORE UPDATE OF {",".join(table.pk)} ON "{table.name}" WHEN {changed} BEGIN SELECT RAISE(ABORT, \'immutable primary key\'); END;')
    return "\n\n".join(chunks) + "\n"


def write_dictionary(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "schema.sql").write_text(schema_sql(), encoding="utf-8")
    output = ["# Data dictionary", "", "All intervals are [start, end), ISO 8601 +05:30. PKs are immutable. "
              "SQLite STRICT tables, checks, uniqueness constraints and FKs enforce basic integrity; temporal and lifecycle rules are validated in Python.", ""]
    serial = {}
    for table in TABLES:
        output += [f"## {table.name}", "", table.note, "", f"Primary key: `{', '.join(table.pk)}`.", ""]
        if table.foreign:
            output += ["Foreign keys: " + "; ".join(f"`{a}` -> `{b}({c})`" for a, b, c in table.foreign) + ".", ""]
        output += ["| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |",
                   "|---|---|---|---|---|---|---|"]
        serial[table.name] = []
        for field in table.fields:
            membership = []
            if field.name in table.pk:
                membership.append("PK" if len(table.pk) == 1 else "part of composite PK")
            membership += ["unique(" + ",".join(u) + ")" for u in table.unique if field.name in u]
            unique = "; ".join(membership) or "not unique"
            allowed = ", ".join(map(str, field.allowed)) or "as validated"
            rule = field.rule + ("; " + field.check if field.check else "")
            output.append(f"| {field.name} | {field.kind} | {'yes' if field.required else 'no'} | {allowed} | {field.units} | {unique} | {rule} |")
            serial[table.name].append({**field.__dict__, "uniqueness": unique})
        if table.checks:
            output += ["", "Cross-field checks: " + "; ".join("`" + c + "`" for c in table.checks) + "."]
        output.append("")
    (root / "DATA_DICTIONARY.md").write_text("\n".join(output), encoding="utf-8")
    (root / "data_dictionary.json").write_text(json.dumps(serial, indent=2) + "\n", encoding="utf-8")


def connect(path):
    """Return a caller-owned connection; `with conn` only manages transactions.

    Use `with closing(connect(path)) as conn` for an owned connection's lifetime.
    Keep transaction scopes (`with conn`) separate so committing never closes a
    connection that its caller still needs.
    """
    conn = sqlite3.connect(path)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("SQLite foreign-key enforcement is unavailable")
    except BaseException:
        conn.close()
        raise
    return conn

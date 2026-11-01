"""Independent source/assignment auditor. Does not import scheduler or labels.

Candidate selection is deliberately absent. Requirements are recalculated directly
from enrolled students and approved, effective accommodations, not trusted caches.
"""
from collections import Counter, defaultdict
from itertools import combinations
import json
import re

from .common import canonical, covered, dt, minutes, overlaps, rows
from .schema import HISTORY_TABLES, TABLES

RULES = {
    "STUDENT_OVERLAP": "A learner's enrolled examinations overlap.",
    "ROOM_DOUBLE_BOOKED": "One room has overlapping accepted intervals.",
    "ROOM_CAPACITY": "Effective usable seats do not cover enrollment for the full interval.",
    "INVIGILATOR_DOUBLE_BOOKED": "One invigilator is allocated to overlapping intervals.",
    "INVIGILATOR_UNAVAILABLE": "A staff member is inactive or lacks full interval availability.",
    "INSUFFICIENT_INVIGILATORS": "Allocated distinct staff count differs from ceil(demand / 40).",
    "ACCOMMODATION_IGNORED": "Approved extra time or accessible room support is missing.",
    "ACCOMMODATION_EFFECTIVE_INTERVAL": "The examination crosses an applicable support end date.",
    "ROOM_UNAVAILABLE": "Room is closed, outside opening hours, retired, or outside its lifecycle.",
    "EQUIPMENT_MISSING": "The room lacks a required binary equipment capability.",
    "DURATION_MISMATCH": "Duration differs from the documented whole-exam extension policy.",
    "EXAM_WINDOW": "Assigned interval falls outside the examination window.",
    "EXAM_INELIGIBLE": "A cancelled exam or exam with no active enrollment was assigned.",
    "FOREIGN_KEY": "An imported identifier has no corresponding parent.",
    "INVALID_INTERVAL": "An interval is malformed, noncanonical or not increasing.",
    "DUPLICATE_ASSIGNMENT": "An exam or natural assignment ID appears more than once.",
    "INVALID_ASSIGNMENT": "Missing/incorrect fields, duplicate staffing IDs or invalid nomenclature.",
    "OUTCOME_COVERAGE": "Exam outcomes do not cover each eligible exam exactly once.",
}


class AuditContext:
    def __init__(self, conn):
        self.students = {x["student_id"]: x for x in rows(conn, "Student")}
        self.exams = {x["exam_id"]: x for x in rows(conn, "Exam")}
        self.rooms = {x["room_id"]: x for x in rows(conn, "Room")}
        self.staff = {x["invigilator_id"]: x for x in rows(conn, "Invigilator")}
        self.enrollments, self.support = defaultdict(list), defaultdict(list)
        self.capacity, self.opening, self.closure, self.availability = (defaultdict(list) for _ in range(4))
        self.exam_equipment, self.room_equipment = defaultdict(set), defaultdict(set)
        for x in rows(conn, "Enrollment"):
            self.enrollments[x["course_id"]].append(x)
        for x in rows(conn, "Accommodation"):
            self.support[x["student_id"]].append(x)
        for x in rows(conn, "RoomCapacity"):
            self.capacity[x["room_id"]].append(x)
        for table, key, dest in (("RoomOpening", "room_id", self.opening), ("RoomClosure", "room_id", self.closure),
                                  ("Availability", "invigilator_id", self.availability)):
            for x in rows(conn, table):
                if table != "Availability" or x["status"] == "AVAILABLE":
                    dest[x[key]].append((x["starts_at"], x["ends_at"]))
        for x in rows(conn, "ExamEquipmentRequirement"):
            self.exam_equipment[x["exam_id"]].add(x["equipment_id"])
        for x in rows(conn, "RoomEquipment"):
            self.room_equipment[x["room_id"]].add(x["equipment_id"])

    def requirements(self, eid, at_time):
        exam = self.exams[eid]
        students = set()
        for e in self.enrollments[exam["course_id"]]:
            s = self.students.get(e["student_id"])
            if (s and s["status"] == "ACTIVE" and e["status"] == "ACTIVE"
                    and e["effective_from"] <= at_time and (e["effective_to"] is None or e["effective_to"] > at_time)
                    and s["effective_from"] <= at_time and (s["effective_to"] is None or s["effective_to"] > at_time)):
                students.add(s["student_id"])
        obligations = [a for sid in sorted(students) for a in self.support[sid]
                       if a["status"] == "APPROVED" and (a["exam_id"] is None or a["exam_id"] == eid)
                       and a["effective_from"] <= at_time < a["effective_to"]]
        extra = max([a["extra_percent"] for a in obligations] + [0])
        duration = (exam["base_duration_minutes"] * (100 + extra) + 99) // 100
        return {"exam_id": eid, "enrolled_count": len(students), "duration_minutes": duration,
                "max_extra_percent": extra, "accessible_required": int(any(a["kind"] == "ACCESSIBLE_ROOM" for a in obligations)),
                "invigilators_required": (len(students)+39)//40}, students, obligations

    def effective_capacity(self, rid, start, end):
        versions = [c for c in self.capacity[rid] if c["effective_to"] > start and c["effective_from"] < end]
        if not covered([(c["effective_from"], c["effective_to"]) for c in versions], start, end):
            return None
        return min(c["seats"] for c in versions)


def detect(conn, assignments, *, expected_exam_ids=None):
    """Audit imported rows or DB decisions; never consult expected anomaly labels.

    expected_exam_ids=None audits a partial import. Production coverage is audited
    with ExamOutcome separately, because an honest unassigned result is legal.
    """
    source = AuditContext(conn)
    issues, valid = [], []

    def issue(rule, exam_ids, resources=(), detail=""):
        issues.append({"rule": rule, "exam_ids": sorted(set(exam_ids)), "resources": sorted(set(resources)), "detail": detail})

    seen_ids, seen_exams = set(), set()
    for index, a in enumerate(assignments):
        if not isinstance(a, dict):
            issue("INVALID_ASSIGNMENT", [], detail=f"Row {index} is not an object")
            continue
        required = ("assignment_id", "exam_id", "room_id", "starts_at", "ends_at", "invigilator_ids")
        eid = a.get("exam_id")
        if (any(k not in a for k in required) or any(not isinstance(a.get(k), str) for k in required[:-1])
                or not isinstance(a.get("invigilator_ids"), list) or any(not isinstance(s, str) for s in a.get("invigilator_ids", []))):
            issue("INVALID_ASSIGNMENT", [eid] if isinstance(eid, str) else [], detail=f"Malformed row {index}")
            continue
        if a["assignment_id"] in seen_ids or eid in seen_exams:
            issue("DUPLICATE_ASSIGNMENT", [eid])
        seen_ids.add(a["assignment_id"])
        seen_exams.add(eid)
        if a["assignment_id"] != f"ASN-{eid}-{a['room_id']}" or len(set(a["invigilator_ids"])) != len(a["invigilator_ids"]):
            issue("INVALID_ASSIGNMENT", [eid], detail="ID convention or duplicate invigilator allocation")
        unknown = ([eid] if eid not in source.exams else []) + ([a["room_id"]] if a["room_id"] not in source.rooms else [])
        unknown += [s for s in a["invigilator_ids"] if s not in source.staff]
        if unknown:
            issue("FOREIGN_KEY", [eid], unknown)
            continue
        start, end, rid = a["starts_at"], a["ends_at"], a["room_id"]
        try:
            if (dt(start).isoformat(timespec="seconds") != start or dt(end).isoformat(timespec="seconds") != end
                    or dt(end) <= dt(start) or (dt(end)-dt(start)).total_seconds() % 60):
                raise ValueError("Expected increasing whole-minute canonical timestamps")
        except (ValueError, TypeError):
            issue("INVALID_INTERVAL", [eid])
            continue
        req, students, obligations = source.requirements(eid, start)
        exam, room = source.exams[eid], source.rooms[rid]
        if exam["status"] != "PLANNED" or req["enrolled_count"] == 0:
            issue("EXAM_INELIGIBLE", [eid])
        if start < exam["window_start"] or end > exam["window_end"]:
            issue("EXAM_WINDOW", [eid])
        actual_duration = minutes(start, end)
        if actual_duration != req["duration_minutes"]:
            rule = "ACCOMMODATION_IGNORED" if actual_duration < req["duration_minutes"] and req["max_extra_percent"] else "DURATION_MISMATCH"
            issue(rule, [eid], detail=f"Actual {actual_duration}; required {req['duration_minutes']} minutes")
        if req["accessible_required"] and not room["accessible"]:
            issue("ACCOMMODATION_IGNORED", [eid], [rid], "Approved accessibility support requires an accessible room")
        if any(a["effective_to"] < end for a in obligations):
            issue("ACCOMMODATION_EFFECTIVE_INTERVAL", [eid])
        capacity = source.effective_capacity(rid, start, end)
        if capacity is None or capacity < req["enrolled_count"]:
            issue("ROOM_CAPACITY", [eid], [rid], f"Demand {req['enrolled_count']}; minimum effective seats {capacity}")
        missing = source.exam_equipment[eid] - source.room_equipment[rid]
        if missing:
            issue("EQUIPMENT_MISSING", [eid], sorted(missing))
        if (room["status"] != "OPEN" or room["effective_from"] > start
                or (room["effective_to"] is not None and room["effective_to"] < end)
                or not covered(source.opening[rid], start, end)
                or any(start < b and a < end for a, b in source.closure[rid])):
            issue("ROOM_UNAVAILABLE", [eid], [rid])
        if len(set(a["invigilator_ids"])) != req["invigilators_required"]:
            issue("INSUFFICIENT_INVIGILATORS", [eid], detail=f"Expected {req['invigilators_required']} distinct people")
        for staff_id in set(a["invigilator_ids"]):
            person = source.staff[staff_id]
            if (person["status"] != "ACTIVE" or person["effective_from"] > start
                    or (person["effective_to"] is not None and person["effective_to"] < end)
                    or not covered(source.availability[staff_id], start, end)):
                issue("INVIGILATOR_UNAVAILABLE", [eid], [staff_id])
        valid.append((a, students))
    # Pairwise audit is independent of the graph used during placement.
    for (left, ls), (right, rs) in combinations(valid, 2):
        if not (left["starts_at"] < right["ends_at"] and right["starts_at"] < left["ends_at"]):
            continue
        exams = [left["exam_id"], right["exam_id"]]
        shared = ls & rs
        if shared:
            issue("STUDENT_OVERLAP", exams, sorted(shared)[:5], f"{len(shared)} learner(s) have overlapping examinations")
        if left["room_id"] == right["room_id"]:
            issue("ROOM_DOUBLE_BOOKED", exams, [left["room_id"]])
        shared_staff = set(left["invigilator_ids"]) & set(right["invigilator_ids"])
        if shared_staff:
            issue("INVIGILATOR_DOUBLE_BOOKED", exams, sorted(shared_staff))
    if expected_exam_ids is not None and seen_exams != set(expected_exam_ids):
        issue("OUTCOME_COVERAGE", sorted(seen_exams ^ set(expected_exam_ids)), detail="Imported assignments differ from the expected scheduled exam set")
    return sorted(issues, key=canonical)


def validate_source(conn):
    errors, joins = [], []

    def error(rule, detail):
        errors.append({"rule": rule, "detail": detail})

    integrity = [r[0] for r in conn.execute("PRAGMA integrity_check")]
    if integrity != ["ok"]:
        error("SQLITE_INTEGRITY", str(integrity))
    for r in conn.execute("PRAGMA foreign_key_check"):
        error("FOREIGN_KEY", str(tuple(r)))
    for table in TABLES:
        data = rows(conn, table.name)
        seen = set()
        for r in data:
            pk = tuple(r[k] for k in table.pk)
            if pk in seen:
                error("DUPLICATE_PK", f"{table.name}: {pk}")
            seen.add(pk)
            for f in table.fields:
                value = r[f.name]
                if value is None:
                    if f.required:
                        error("REQUIRED_FIELD", f"{table.name}.{f.name}: {pk}")
                    continue
                if f.allowed and value not in f.allowed:
                    error("ENUM", f"{table.name}.{f.name}: {value}")
                if f.units == "Asia/Kolkata timestamp":
                    try:
                        if dt(value).isoformat(timespec="seconds") != value:
                            raise ValueError("noncanonical timestamp")
                    except (ValueError, TypeError):
                        error("INVALID_INTERVAL", f"{table.name}.{f.name}: {pk}")
                if f.name.endswith("_json"):
                    try:
                        json.loads(value)
                    except (ValueError, TypeError):
                        error("INVALID_JSON", f"{table.name}.{f.name}: {pk}")
            for left, right in (("effective_from", "effective_to"), ("starts_at", "ends_at"), ("window_start", "window_end")):
                if left in r and r.get(right) is not None and r[right] <= r[left]:
                    error("INVALID_INTERVAL", f"{table.name}: {pk}")
        # Explicitly validate every join, including all composite/optional FKs.
        for child, parent, parent_col in table.foreign:
            cc, pc = child.split(","), parent_col.split(",")
            nonnull = " AND ".join(f'c."{c}" IS NOT NULL' for c in cc)
            predicate = " AND ".join(f'c."{c}" = p."{p}"' for c, p in zip(cc, pc))
            total = conn.execute(f'SELECT count(*) FROM "{table.name}" c WHERE {nonnull}').fetchone()[0]
            matched = conn.execute(f'SELECT count(*) FROM "{table.name}" c JOIN "{parent}" p ON {predicate} WHERE {nonnull}').fetchone()[0]
            joins.append({"relationship": f"{table.name}({child})->{parent}({parent_col})", "referencing_rows": total, "joined_rows": matched, "passed": total == matched})
            if total != matched:
                error("JOIN_RECONCILIATION", joins[-1]["relationship"])
    patterns = {"Student": ("student_id", r"STU-\d{6,}"), "Exam": ("exam_id", r"EXAM-2026-\d{6,}"),
                "Room": ("room_id", r"ROOM-\d{6,}"), "Invigilator": ("invigilator_id", r"INV-\d{6,}")}
    for table, (col, pattern) in patterns.items():
        if any(not re.fullmatch(pattern, r[col]) for r in rows(conn, table)):
            error("ID_CONVENTION", table)
    source = AuditContext(conn)
    stored = {r["exam_id"]: r for r in rows(conn, "ExamRequirement")}
    if set(stored) != set(source.exams):
        error("REQUIREMENT_COVERAGE", "Exactly one derived requirement is required per exam")
    for eid, exam in source.exams.items():
        expected = source.requirements(eid, exam["window_start"])[0]
        if stored.get(eid) != expected:
            error("DERIVED_REQUIREMENT", eid)
    for rid, versions in source.capacity.items():
        for a, b in combinations(versions, 2):
            if overlaps(a["effective_from"], a["effective_to"], b["effective_from"], b["effective_to"]):
                error("CAPACITY_VERSION_OVERLAP", rid)
        for start, end in source.opening[rid]:
            if not covered([(c["effective_from"], c["effective_to"]) for c in versions], start, end):
                error("CAPACITY_VERSION_GAP", rid)
    for table, key in (("RoomOpening", "room_id"), ("Availability", "invigilator_id")):
        by_resource = defaultdict(list)
        for r in rows(conn, table):
            if r.get("status", "AVAILABLE") == "AVAILABLE":
                by_resource[r[key]].append(r)
        for resource, intervals in by_resource.items():
            for a, b in combinations(intervals, 2):
                if overlaps(a["starts_at"], a["ends_at"], b["starts_at"], b["ends_at"]):
                    error("OVERLAPPING_AVAILABILITY", resource)
    # This dataset deliberately freezes enrollment/support state within exam windows.
    # Different input data must regenerate requirements / graph for each window.
    for exam in source.exams.values():
        for e in source.enrollments[exam["course_id"]]:
            for value in (e["effective_from"], e["effective_to"]):
                if value and exam["window_start"] < value < exam["window_end"]:
                    error("UNSUPPORTED_MID_WINDOW_CHANGE", e["enrollment_id"])
            student = source.students[e["student_id"]]
            for value in (student["effective_from"], student["effective_to"]):
                if value and exam["window_start"] < value < exam["window_end"]:
                    error("UNSUPPORTED_MID_WINDOW_CHANGE", student["student_id"])
        for a in (a for values in source.support.values() for a in values if a["status"] == "APPROVED" and a["exam_id"] in (None, exam["exam_id"])):
            if any(exam["window_start"] < value < exam["window_end"] for value in (a["effective_from"], a["effective_to"])):
                error("UNSUPPORTED_MID_WINDOW_CHANGE", a["accommodation_id"])
    events = defaultdict(list)
    event_keys = {"student_id": ("Student", "ACTIVE", {("ACTIVE", "INACTIVE")}),
                  "enrollment_id": ("Enrollment", "ACTIVE", {("ACTIVE", "WITHDRAWN")}),
                  "exam_id": ("Exam", "PLANNED", {("PLANNED", "CANCELLED")}),
                  "room_id": ("Room", "OPEN", {("OPEN", "RETIRED")}),
                  "invigilator_id": ("Invigilator", "ACTIVE", {("ACTIVE", "INACTIVE")}),
                  "availability_id": ("Availability", "AVAILABLE", {("AVAILABLE", "CANCELLED")}),
                  "accommodation_id": ("Accommodation", "PENDING", {("PENDING", "APPROVED"), ("PENDING", "REJECTED")})}
    for e in rows(conn, "LifecycleEvent"):
        linked = [k for k in event_keys if e[k] is not None]
        if len(linked) != 1:
            error("LIFECYCLE_REFERENCE", e["event_id"])
            continue
        events[(linked[0], e[linked[0]])].append(e)
    for key, (table, initial, transitions) in event_keys.items():
        for entity in rows(conn, table):
            chain = sorted(events[(key, entity[key])], key=lambda e: (e["occurred_at"], e["event_id"]))
            current = None
            if not chain:
                error("LIFECYCLE_MISSING", entity[key])
            for e in chain:
                if (e["from_state"] != current or (current is None and e["to_state"] != initial)
                        or (current is not None and (current, e["to_state"]) not in transitions)):
                    error("LIFECYCLE_TRANSITION", e["event_id"])
                current = e["to_state"]
            if current != entity["status"]:
                error("LIFECYCLE_CURRENT_STATE", entity[key])
            if entity["status"] in ("WITHDRAWN", "RETIRED") and chain and entity["effective_to"] != chain[-1]["occurred_at"]:
                error("LIFECYCLE_EFFECTIVE_DATE", entity[key])
    for r in rows(conn, "Enrollment"):
        if r["status"] == "ACTIVE":
            course = conn.execute("SELECT category,cohort_id FROM Course WHERE course_id=?", (r["course_id"],)).fetchone()
            if course and course["category"] == "CORE" and source.students[r["student_id"]]["cohort_id"] != course["cohort_id"]:
                error("COHORT_ENROLLMENT", r["enrollment_id"])
    config = json.loads(conn.execute("SELECT config_json FROM Dataset").fetchone()[0])
    for key, table in (("students", "Student"), ("exams", "Exam"), ("rooms", "Room"), ("invigilators", "Invigilator")):
        if conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] != config[key]:
            error("SOURCE_VOLUME", table)
    triggers = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    for table in HISTORY_TABLES:
        for op in ("update", "delete"):
            if f"immutable_{table}_{op}" not in triggers:
                error("APPEND_ONLY_GUARD", table)
    for table in TABLES:
        if f"immutable_pk_{table.name}" not in triggers:
            error("ID_IMMUTABILITY_GUARD", table.name)
    return {"passed": not errors, "errors": errors, "join_checks": joins, "sqlite_integrity": integrity,
            "checks": ["primary keys", "foreign keys and every join", "required fields/enums/JSON", "date ordering and timezone",
                       "effective capacity versions", "lifecycle transitions", "cached derived requirements", "source volumes", "append-only guards"]}


def validate_run(conn, run_id, assignments):
    source_report = validate_source(conn)
    issues = detect(conn, assignments)
    outcomes = [dict(r) for r in conn.execute("SELECT * FROM ExamOutcome WHERE run_id=?", (run_id,))]
    exams = {r[0] for r in conn.execute("SELECT exam_id FROM Exam WHERE status='PLANNED'")}
    actual = {o["exam_id"] for o in outcomes}

    def issue(rule, detail):
        issues.append({"rule": rule, "exam_ids": [], "resources": [], "detail": detail})

    if actual != exams or len(outcomes) != len(exams):
        issue("OUTCOME_COVERAGE", "Each planned exam must have exactly one persisted outcome; cancelled exams have none")
    by_exam = {a["exam_id"]: a for a in assignments}
    for o in outcomes:
        a = by_exam.get(o["exam_id"])
        if o["status"] == "SCHEDULED":
            if not a or a["assignment_id"] != o["assignment_id"]:
                issue("OUTCOME_RECONCILIATION", o["exam_id"])
        elif a or not o["reason_code"] or not json.loads(o["evidence_json"]).get("explanation"):
            issue("UNASSIGNED_EVIDENCE", o["exam_id"])
    if set(by_exam) != {o["exam_id"] for o in outcomes if o["status"] == "SCHEDULED"}:
        issue("OUTCOME_RECONCILIATION", "Assignment and scheduled-outcome sets differ")
    events = [dict(r) for r in conn.execute("SELECT * FROM DecisionEvent WHERE run_id=? ORDER BY event_id", (run_id,))]
    counts = Counter(e["kind"] for e in events)
    if counts["RUN_STARTED"] != 1 or counts["RUN_COMPLETED"] != 1 or len(events) != len(outcomes)+2:
        issue("DECISION_HISTORY", "Exactly one start, completion, and event per exam outcome required")
    for o in outcomes:
        matched = [e for e in events if e["exam_id"] == o["exam_id"]]
        if len(matched) != 1:
            issue("DECISION_HISTORY", o["exam_id"])
            continue
        event = matched[0]
        payload = json.loads(event["payload_json"])
        if o["status"] == "SCHEDULED":
            a = by_exam.get(o["exam_id"], {})
            stored = payload.get("assignment", {})
            if (event["kind"] != "EXAM_ASSIGNED" or any(a.get(k) != stored.get(k) for k in
                    ("assignment_id", "exam_id", "room_id", "starts_at", "ends_at"))
                    or sorted(a.get("invigilator_ids", [])) != sorted(stored.get("invigilator_ids", []))):
                issue("DECISION_HISTORY", o["exam_id"])
        elif event["kind"] != "EXAM_UNASSIGNED" or payload.get("reason_code") != o["reason_code"]:
            issue("DECISION_HISTORY", o["exam_id"])
    room_minutes = sum(minutes(a["starts_at"], a["ends_at"]) for a in assignments)
    staff_minutes = sum(minutes(a["starts_at"], a["ends_at"]) * len(a["invigilator_ids"]) for a in assignments)
    sql_room = conn.execute("SELECT coalesce(sum(round((julianday(ends_at)-julianday(starts_at))*1440)),0) FROM ScheduleAssignment WHERE run_id=?", (run_id,)).fetchone()[0]
    sql_staff = conn.execute("SELECT coalesce(sum(round((julianday(a.ends_at)-julianday(a.starts_at))*1440)),0) FROM InvigilatorAllocation i JOIN ScheduleAssignment a ON a.run_id=i.run_id AND a.assignment_id=i.assignment_id WHERE i.run_id=?", (run_id,)).fetchone()[0]
    if room_minutes != sql_room or staff_minutes != sql_staff:
        issue("USAGE_RECONCILIATION", "Independent Python totals and joined SQL totals differ")
    return {"passed": source_report["passed"] and not issues, "run_id": run_id, "source": source_report,
            "hard_constraint_violations": issues, "violation_count": len(issues),
            "usage_reconciliation": {"passed": room_minutes == sql_room and staff_minutes == sql_staff,
                                     "room_minutes": room_minutes, "sql_room_minutes": sql_room,
                                     "staff_minutes": staff_minutes, "sql_staff_minutes": sql_staff},
            "eligible_exam_count": len(exams), "outcome_count": len(outcomes)}

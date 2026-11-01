"""Deterministic, synthetic-only generation; parents precede all dependents."""
from collections import Counter
from contextlib import closing
from math import ceil
from pathlib import Path
import random
import sqlite3

from .common import APPROVAL_DATE, CAPACITY_CHANGE, HORIZON_END, HORIZON_START, ORIGIN, at, canonical, days
from .domain import Facts
from .schema import SCHEMA_VERSION, connect, schema_sql

PROFILES = {"starter": {"students": 250, "exams": 30, "rooms": 12, "invigilators": 24},
            "full": {"students": 5000, "exams": 300, "rooms": 100, "invigilators": 200}}


def configuration(profile="full", scale=1.0, seed=20261022):
    if profile not in PROFILES or not (0 < scale <= 10) or seed < 0:
        raise ValueError("Use starter/full, 0 < scale <= 10, and a nonnegative seed")
    counts = {k: int(v * scale + 0.5) for k, v in PROFILES[profile].items()}
    if counts["students"] < 50 or counts["exams"] < 12 or counts["rooms"] < 8 or counts["invigilators"] < 12:
        raise ValueError("Scaled datasets require >=50 students, 12 exams, 8 rooms, and 12 invigilators")
    return {"schema_version": SCHEMA_VERSION, "profile": profile, "scale": float(scale), "seed": seed, **counts}


def generate(path, config):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with closing(connect(path)) as conn:
            try:
                record = conn.execute("SELECT config_json FROM Dataset").fetchone()
            except sqlite3.Error as exc:
                raise ValueError("Existing file is not an ExamFlow database; choose a new path") from exc
            if record is None or record[0] != canonical(config):
                raise ValueError("Refusing to replace a database with different source configuration; use another output directory")
        return path  # Retain immutable source and all previous runs.
    rng = random.Random(config["seed"])
    conn = connect(path)
    try:
        conn.executescript(schema_sql())
        with conn:
            _populate(conn, config, rng)
    except Exception:
        conn.close()
        path.unlink(missing_ok=True)  # Only a newly-created, incomplete database is removed.
        raise
    finally:
        conn.close()
    return path


def _populate(conn, config, rng):
    def insert(table, data):
        if not data:
            return
        fields = list(data[0])
        conn.executemany(f'INSERT INTO "{table}" ({",".join(fields)}) VALUES ({",".join("?" for _ in fields)})',
                         [tuple(r[k] for k in fields) for r in data])

    history = []

    def event(key, value, to_state, when=ORIGIN, from_state=None):
        e = {"event_id": f"LFE-{len(history)+1:06d}",
             **{k: None for k in ("student_id", "enrollment_id", "exam_id", "room_id", "invigilator_id", "availability_id", "accommodation_id")},
             "from_state": from_state, "to_state": to_state, "occurred_at": when}
        e[key] = value
        history.append(e)

    insert("Dataset", [{"dataset_id": "DATASET-000001", "schema_version": SCHEMA_VERSION, "seed": config["seed"],
                        "profile": config["profile"], "scale": config["scale"], "config_json": canonical(config),
                        "timezone": "Asia/Kolkata", "generated_at": "2026-10-22T00:00:00+05:30"}])
    ncohorts = max(2, config["exams"] // 6)
    cohorts = [{"cohort_id": f"COH-{i+1:06d}", "name": f"Synthetic cohort {i+1:03d}"} for i in range(ncohorts)]
    insert("Cohort", cohorts)
    students = []
    for i in range(config["students"]):
        sid = f"STU-{i+1:06d}"
        students.append({"student_id": sid, "synthetic_name": f"Synthetic learner {i+1:06d}",
                         "cohort_id": cohorts[i % ncohorts]["cohort_id"], "status": "ACTIVE", "effective_from": ORIGIN, "effective_to": None})
        event("student_id", sid, "ACTIVE")
    insert("Student", students)
    courses = []
    for i in range(config["exams"]):
        core = i < ncohorts * 5
        courses.append({"course_id": f"CRS-{i+1:06d}", "title": f"{'Core subject' if core else 'Shared elective'} {i+1:03d}",
                        "category": "CORE" if core else "ELECTIVE", "cohort_id": cohorts[i // 5]["cohort_id"] if core else None})
    insert("Course", courses)
    elective_ids = [c["course_id"] for c in courses if c["category"] == "ELECTIVE"]
    core_by_cohort = {c["cohort_id"]: [x["course_id"] for x in courses if x["cohort_id"] == c["cohort_id"]] for c in cohorts}
    enrollments = []
    for s in students:
        selected = core_by_cohort[s["cohort_id"]] + [rng.choice(elective_ids)]
        withdrawn = rng.random() < 0.035 and len(elective_ids) > 1
        if withdrawn:
            selected.append(next(x for x in elective_ids if x != selected[-1]))
        for j, cid in enumerate(selected):
            is_withdrawn = withdrawn and j == len(selected) - 1
            eid = f"ENR-{len(enrollments)+1:06d}"
            enrollments.append({"enrollment_id": eid, "student_id": s["student_id"], "course_id": cid,
                                "status": "WITHDRAWN" if is_withdrawn else "ACTIVE", "effective_from": ORIGIN,
                                "effective_to": APPROVAL_DATE if is_withdrawn else None})
            event("enrollment_id", eid, "ACTIVE")
            if is_withdrawn:
                event("enrollment_id", eid, "WITHDRAWN", APPROVAL_DATE, "ACTIVE")
    insert("Enrollment", enrollments)
    exams = []
    for i, c in enumerate(courses):
        eid = f"EXAM-2026-{i+1:06d}"
        cancelled = i == len(courses) - 1
        exams.append({"exam_id": eid, "course_id": c["course_id"], "title": c["title"] + " examination",
                      "base_duration_minutes": rng.choice([90, 120, 120, 150, 180]),
                      "window_start": HORIZON_START, "window_end": HORIZON_END, "status": "CANCELLED" if cancelled else "PLANNED"})
        event("exam_id", eid, "PLANNED")
        if cancelled:
            event("exam_id", eid, "CANCELLED", "2026-11-01T00:00:00+05:30", "PLANNED")
    insert("Exam", exams)
    equipments = [("EQ-COMPUTER", "Computer laboratory"), ("EQ-PROJECTOR", "Projection system"),
                  ("EQ-LAB", "Laboratory benches"), ("EQ-SECURE", "Secure specialist terminal")]
    insert("Equipment", [{"equipment_id": k, "name": v} for k, v in equipments])
    exam_eq = []
    for i, e in enumerate(exams):
        eq = "EQ-SECURE" if i == len(exams) - 2 else ("EQ-COMPUTER" if i % 10 == 0 else ("EQ-PROJECTOR" if i % 10 == 1 else ("EQ-LAB" if i % 20 == 2 else None)))
        if eq:
            exam_eq.append({"exam_id": e["exam_id"], "equipment_id": eq})
    insert("ExamEquipmentRequirement", exam_eq)
    accommodations = []

    def accommodate(sid, kind, status="APPROVED", exam_id=None, extra=0, end=HORIZON_END):
        aid = f"ACC-{len(accommodations)+1:06d}"
        accommodations.append({"accommodation_id": aid, "student_id": sid, "exam_id": exam_id, "kind": kind,
                               "extra_percent": extra, "status": status, "effective_from": APPROVAL_DATE, "effective_to": end})
        event("accommodation_id", aid, "PENDING", APPROVAL_DATE)
        if status != "PENDING":
            event("accommodation_id", aid, status, "2026-10-02T00:00:00+05:30", "PENDING")

    for i, s in enumerate(students):
        if i == 0 or rng.random() < 0.045:
            scoped = f"EXAM-2026-{(i % ncohorts)*5+1:06d}" if i != 0 and rng.random() < 0.15 else None
            accommodate(s["student_id"], "EXTRA_TIME", exam_id=scoped, extra=50 if i == 0 else rng.choice([25, 25, 50]))
            if i == 0 or rng.random() < 0.3:
                accommodate(s["student_id"], "ACCESSIBLE_ROOM", exam_id=scoped)
        elif rng.random() < 0.012:
            accommodate(s["student_id"], "EXTRA_TIME", status=rng.choice(["PENDING", "REJECTED"]), extra=50)
    # Expired approval is retained but has no effect on November requirements.
    accommodate(students[0]["student_id"], "EXTRA_TIME", extra=25, end="2026-11-15T00:00:00+05:30")
    insert("Accommodation", accommodations)
    demand = Counter(e["course_id"] for e in enrollments if e["status"] == "ACTIVE")
    core_size = ceil(config["students"] / ncohorts)
    max_demand = max(demand.values())
    room_records, capacities, room_eq, openings, closures = [], [], [], [], []
    exam_days = list(days())
    for i in range(config["rooms"]):
        rid = f"ROOM-{i+1:06d}"
        retired = i >= 8 and i == config["rooms"] - 1
        room_records.append({"room_id": rid, "name": f"Hall {i+1:03d}", "accessible": int(i < 5 or rng.random() < 0.65),
                             "status": "RETIRED" if retired else "OPEN", "effective_from": ORIGIN,
                             "effective_to": "2026-11-01T00:00:00+05:30" if retired else None})
        event("room_id", rid, "OPEN")
        if retired:
            event("room_id", rid, "RETIRED", "2026-11-01T00:00:00+05:30", "OPEN")
        seats = ([max_demand+40, 1, core_size, max_demand+20, core_size][i] if i < 5
                 else rng.choice([max(10, core_size//2), core_size, core_size+20, core_size+60, core_size*2]))
        for start, end, number in ((HORIZON_START, CAPACITY_CHANGE, seats),
                                   (CAPACITY_CHANGE, HORIZON_END, max(1, seats-10) if i == 4 or (i >= 5 and i % 7 == 0) else seats)):
            capacities.append({"capacity_id": f"CAP-{len(capacities)+1:06d}", "room_id": rid, "seats": number,
                               "effective_from": start, "effective_to": end})
        for key, _ in equipments[:3]:
            if i < 5 or rng.random() < 0.42:
                room_eq.append({"room_id": rid, "equipment_id": key})
        for day in exam_days:
            openings.append({"opening_id": f"OPN-{len(openings)+1:06d}", "room_id": rid, "starts_at": at(day, 8), "ends_at": at(day, 18)})
        if i >= 5 and not retired:
            day = rng.choice(exam_days)
            whole_day = rng.random() < 0.3
            closures.append({"closure_id": f"CLS-{len(closures)+1:06d}", "room_id": rid,
                             "starts_at": at(day, 8 if whole_day else 12), "ends_at": at(day, 18 if whole_day else 14),
                             "reason": "CAMPUS_EVENT" if whole_day else "MAINTENANCE"})
    for table, data in (("Room", room_records), ("RoomCapacity", capacities), ("RoomEquipment", room_eq),
                        ("RoomOpening", openings), ("RoomClosure", closures)):
        insert(table, data)
    invigilators, availability = [], []
    reserve = min(16, config["invigilators"])
    for i in range(config["invigilators"]):
        iid = f"INV-{i+1:06d}"
        invigilators.append({"invigilator_id": iid, "synthetic_name": f"Synthetic invigilator {i+1:06d}",
                             "status": "ACTIVE", "effective_from": ORIGIN, "effective_to": None})
        event("invigilator_id", iid, "ACTIVE")
        for day in exam_days:
            if i >= reserve and rng.random() < 0.15:
                continue
            shift = "all" if i < reserve else rng.choice(["all", "all", "am", "pm"])
            cancelled = i >= reserve and rng.random() < 0.02
            aid = f"AVL-{len(availability)+1:06d}"
            availability.append({"availability_id": aid, "invigilator_id": iid,
                                 "starts_at": at(day, 7 if i < reserve else (13 if shift == "pm" else 8)),
                                 "ends_at": at(day, 20 if i < reserve else (13 if shift == "am" else 18)),
                                 "status": "CANCELLED" if cancelled else "AVAILABLE"})
            event("availability_id", aid, "AVAILABLE")
            if cancelled:
                event("availability_id", aid, "CANCELLED", "2026-11-01T00:00:00+05:30", "AVAILABLE")
    insert("Invigilator", invigilators)
    insert("Availability", availability)
    facts = Facts(conn)
    insert("ExamRequirement", [facts.derive(e["exam_id"])[0] for e in exams])
    insert("LifecycleEvent", history)

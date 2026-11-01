"""Controlled negative schedules and neutral clean controls, stored separately.

Labels follow construction proofs, not detector predictions or random draws.
Only evaluate() opens ground_truth.json. Scheduler/detector never receive it.
"""
from pathlib import Path
import csv
import json

from .common import at, canonical, days, overlaps, plus
from .domain import Facts
from .validate import RULES, detect


def fixture_payload(conn):
    facts = Facts(conn)
    day = next(days())
    start = at(day, 8)
    core = [r[0] for r in conn.execute("SELECT e.exam_id FROM Exam e JOIN Course c ON c.course_id=e.course_id WHERE c.category='CORE' AND e.status='PLANNED' ORDER BY e.exam_id")]
    first = next(e for e in core if facts.derive(e)[0]["max_extra_percent"] > 0)
    first_students = facts.derive(first)[1]
    shared = next(e for e in core if e != first and facts.derive(e)[1] & first_students)
    disjoint = next(e for e in core if not (facts.derive(e)[1] & first_students))
    staff = sorted(facts.staff)

    def make(eid, room="ROOM-000001", begin=start, offset=0, duration=None):
        req = facts.derive(eid, begin)[0]
        return {"assignment_id": f"ASN-{eid}-{room}", "exam_id": eid, "room_id": room, "starts_at": begin,
                "ends_at": plus(begin, req["duration_minutes"] if duration is None else duration),
                "invigilator_ids": staff[offset:offset+req["invigilators_required"]]}

    first_req = facts.derive(first)[0]
    clean = make(first)
    overlap = [clean, make(shared, "ROOM-000004", offset=first_req["invigilators_required"])]
    capacity = make(first, "ROOM-000002")
    double_staff = [clean, make(disjoint, "ROOM-000004")]
    shortened = make(first, duration=facts.exams[first]["base_duration_minutes"])
    early = make(first, begin=at(day, 7))
    adjacent = [clean, make(shared, begin=clean["ends_at"])]
    exact = make(core[0], "ROOM-000003")
    exact_req = facts.derive(core[0])[0]
    exact_seats = facts.capacity(exact["room_id"], exact["starts_at"], exact["ends_at"])
    assert exact_seats == exact_req["enrolled_count"]
    assert first_students & facts.derive(shared)[1]
    assert not (first_students & facts.derive(disjoint)[1])
    assert not overlaps(adjacent[0]["starts_at"], adjacent[0]["ends_at"], adjacent[1]["starts_at"], adjacent[1]["ends_at"])
    definitions = [
        (overlap, ["STUDENT_OVERLAP"], "Two core courses share their cohort; distinct rooms/staff remove unrelated resource conflicts.",
         {"shared_student_count": len(first_students & facts.derive(shared)[1])}),
        ([capacity], ["ROOM_CAPACITY"], "The selected room has one usable seat, below the source enrollment demand.",
         {"demand": first_req["enrolled_count"], "seats": 1}),
        (double_staff, ["INVIGILATOR_DOUBLE_BOOKED"], "Disjoint learner cohorts use different rooms, but concurrent allocations reuse the same staff.",
         {"shared_staff": sorted(set(clean["invigilator_ids"]) & set(double_staff[1]["invigilator_ids"]))}),
        ([shortened], ["ACCOMMODATION_IGNORED"], "End time uses base duration despite an effective approved extra-time allowance.",
         {"actual_minutes": facts.exams[first]["base_duration_minutes"], "required_minutes": first_req["duration_minutes"]}),
        ([early], ["ROOM_UNAVAILABLE"], "Exam begins at 07:00, before the room opens at 08:00; reserve invigilators are available from 07:00.",
         {"room_opens": at(day, 8), "assignment_starts": at(day, 7)}),
        ([clean], [], "Unmodified, fully feasible source-derived assignment.", {}),
        (adjacent, [], "Same learners, room and staff have adjacent half-open intervals; equality at the boundary is legal.", {}),
        ([exact], [], "Demand equals the effective room capacity; equality is legal.", {"demand": exact_req["enrolled_count"], "seats": exact_seats}),
    ]
    cases, truth = [], []
    for i, (assignments, rules, rationale, proof) in enumerate(definitions, 1):
        cid = f"CASE-{i:06d}"
        cases.append({"case_id": cid, "assignments": assignments})
        truth.append({"case_id": cid, "expected_rules": rules, "issue_type": "NORMAL" if not rules else rules[0],
                      "rationale": rationale, "source_proof": proof})
    impossible = []
    all_equipment = set().union(*facts.room_equipment.values())
    for eid, exam in sorted(facts.exams.items()):
        missing = facts.exam_equipment[eid] - all_equipment
        if exam["status"] == "PLANNED" and missing:
            impossible.append({"exam_id": eid, "expected_status": "UNASSIGNED", "expected_reason": "NO_COMPATIBLE_ROOM",
                               "proof": {"equipment_absent_from_all_rooms": sorted(missing)}})
    assert impossible, "The demonstration must include a provably infeasible demand"
    return {"schema_version": "1.0", "cases": cases}, {"schema_version": "1.0", "cases": truth, "expected_decisions": impossible}


def write_fixtures(conn, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    inputs, truth = fixture_payload(conn)
    (folder / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n", encoding="utf-8")
    (folder / "ground_truth.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
    with (folder / "ground_truth.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=("case_id", "issue_type", "expected_rules", "rationale", "source_proof"))
        writer.writeheader()
        for record in truth["cases"]:
            writer.writerow({**record, "expected_rules": ";".join(record["expected_rules"]), "source_proof": canonical(record["source_proof"])})
    return inputs, truth


def evaluate(conn, folder, run_id):
    folder = Path(folder)
    inputs = json.loads((folder / "inputs.json").read_text(encoding="utf-8"))
    truth = json.loads((folder / "ground_truth.json").read_text(encoding="utf-8"))
    expected = {r["case_id"]: set(r["expected_rules"]) for r in truth["cases"]}
    if len(expected) != len(truth["cases"]) or {c["case_id"] for c in inputs["cases"]} != set(expected):
        raise ValueError("Fixture and ground-truth case IDs must match uniquely")
    per_rule = {rule: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for rule in RULES}
    cases = []
    for c in inputs["cases"]:
        # Crucially, the detector receives only assignments and valid source facts.
        violations = detect(conn, c["assignments"])
        predicted, target = {v["rule"] for v in violations}, expected[c["case_id"]]
        for rule in RULES:
            outcome = "tp" if rule in target and rule in predicted else ("fp" if rule in predicted else ("fn" if rule in target else "tn"))
            per_rule[rule][outcome] += 1
        cases.append({"case_id": c["case_id"], "expected_rules": sorted(target), "detected_rules": sorted(predicted),
                      "passed": predicted == target, "violations": violations})
    total = {key: sum(x[key] for x in per_rule.values()) for key in ("tp", "fp", "fn", "tn")}

    def rates(record):
        return {**record, "precision": record["tp"] / (record["tp"]+record["fp"]) if record["tp"]+record["fp"] else None,
                "recall": record["tp"] / (record["tp"]+record["fn"]) if record["tp"]+record["fn"] else None}

    decisions = []
    for e in truth["expected_decisions"]:
        actual = conn.execute("SELECT status,reason_code FROM ExamOutcome WHERE run_id=? AND exam_id=?", (run_id, e["exam_id"])).fetchone()
        decisions.append({"exam_id": e["exam_id"], "passed": bool(actual and actual[0] == e["expected_status"] and actual[1] == e["expected_reason"]),
                          "expected_status": e["expected_status"], "expected_reason": e["expected_reason"], "actual": list(actual) if actual else None})
    return {"passed": all(c["passed"] for c in cases) and all(d["passed"] for d in decisions),
            "unit": "(case, rule) binary decisions; duplicate findings of the same rule in one case count once",
            "micro": rates(total), "per_rule": {k: rates(v) for k, v in per_rule.items()}, "cases": cases,
            "expected_decisions": decisions,
            "scope": "Eight hand-crafted cases: five anomalies, one clean control, two boundary controls. This is regression coverage, not a population accuracy estimate."}

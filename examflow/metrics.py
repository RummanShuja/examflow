"""Operational metrics derived from persisted sources and accepted decisions."""
from collections import Counter, defaultdict

from .common import HORIZON_END, HORIZON_START, covered, minutes, overlaps, rows
from .domain import Facts, conflict_graph


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def _usable_room_segments(facts, rid):
    room = facts.rooms[rid]
    if room["status"] != "OPEN":
        return []
    intervals = facts.openings[rid] + facts.closures[rid]
    intervals += [(c["effective_from"], c["effective_to"]) for c in facts.capacities[rid]]
    points = {HORIZON_START, HORIZON_END, room["effective_from"]}
    if room["effective_to"]:
        points.add(room["effective_to"])
    for a, b in intervals:
        points.update((a, b))
    points = sorted(p for p in points if HORIZON_START <= p <= HORIZON_END)
    result = []
    for a, b in zip(points, points[1:]):
        capacity = facts.capacity(rid, a, b)
        if (a >= room["effective_from"] and (room["effective_to"] is None or b <= room["effective_to"])
                and covered(facts.openings[rid], a, b) and not any(overlaps(a, b, c, d) for c, d in facts.closures[rid])
                and capacity is not None):
            result.append((a, b, capacity))
    return result


def calculate(conn, run_id, assignments):
    facts = Facts(conn)
    graph, edges = conflict_graph(facts)
    outcomes = [dict(r) for r in conn.execute("SELECT * FROM ExamOutcome WHERE run_id=?", (run_id,))]
    reasons = Counter(o["reason_code"] for o in outcomes if o["status"] == "UNASSIGNED")
    by_exam = {a["exam_id"]: a for a in assignments}
    room_use, staff_use, learner_minutes, occupied_capacity = Counter(), Counter(), Counter(), Counter()
    extra_room_minutes = extra_staff_minutes = 0
    for a in assignments:
        eid, rid = a["exam_id"], a["room_id"]
        duration = minutes(a["starts_at"], a["ends_at"])
        req = facts.derive(eid, a["starts_at"])[0]
        room_use[rid] += duration
        learner_minutes[rid] += req["enrolled_count"] * duration
        occupied_capacity[rid] += facts.capacity(rid, a["starts_at"], a["ends_at"]) * duration
        overhead = duration - facts.exams[eid]["base_duration_minutes"]
        extra_room_minutes += overhead
        extra_staff_minutes += overhead * len(a["invigilator_ids"])
        for iid in a["invigilator_ids"]:
            staff_use[iid] += duration
    rooms = []
    for rid in sorted(facts.rooms):
        segments = _usable_room_segments(facts, rid)
        available = sum(minutes(a, b) for a, b, _ in segments)
        seats = sum(minutes(a, b) * c for a, b, c in segments)
        rooms.append({"room_id": rid, "available_minutes": available, "used_minutes": room_use[rid],
                      "available_seat_minutes": seats, "used_student_seat_minutes": learner_minutes[rid],
                      "allocated_seat_minutes": occupied_capacity[rid], "time_utilization": ratio(room_use[rid], available)})
    staff = []
    for iid, person in sorted(facts.staff.items()):
        # Availability sources are validated as non-overlapping; union preserves boundaries.
        boundaries = sorted({p for a, b in facts.availability[iid] for p in (max(a, HORIZON_START, person["effective_from"]),
            min(b, HORIZON_END, person["effective_to"] or HORIZON_END)) if HORIZON_START <= p <= HORIZON_END})
        available = sum(minutes(a, b) for a, b in zip(boundaries, boundaries[1:])
                        if person["status"] == "ACTIVE" and a >= person["effective_from"]
                        and (person["effective_to"] is None or b <= person["effective_to"])
                        and covered(facts.availability[iid], a, b))
        staff.append({"invigilator_id": iid, "available_minutes": available, "used_minutes": staff_use[iid],
                      "utilization": ratio(staff_use[iid], available)})
    required_all = required_scheduled = fulfilled = 0
    for eid in graph:
        _, _, support = facts.derive(eid)
        required_all += len(support)
        if eid in by_exam:
            a = by_exam[eid]
            required_scheduled += len(support)
            for s in support:
                req = facts.derive(eid, a["starts_at"])[0]
                if (s["effective_from"] <= a["starts_at"] and a["ends_at"] <= s["effective_to"]
                        and (s["kind"] != "ACCESSIBLE_ROOM" or facts.rooms[a["room_id"]]["accessible"])
                        and minutes(a["starts_at"], a["ends_at"]) >= req["duration_minutes"]):
                    fulfilled += 1
    room_available = sum(x["available_minutes"] for x in rooms)
    room_used = sum(x["used_minutes"] for x in rooms)
    seat_available = sum(x["available_seat_minutes"] for x in rooms)
    seat_used = sum(x["used_student_seat_minutes"] for x in rooms)
    allocated = sum(x["allocated_seat_minutes"] for x in rooms)
    staff_available = sum(x["available_minutes"] for x in staff)
    staff_used = sum(x["used_minutes"] for x in staff)
    return {"run_id": run_id, "timezone": "Asia/Kolkata", "horizon": [HORIZON_START, HORIZON_END],
            "source_counts": {t: conn.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for t in
                              ("Student", "Course", "Enrollment", "Exam", "Room", "Invigilator", "Accommodation")},
            "scheduled": len(assignments), "unassigned": len(outcomes)-len(assignments), "eligible": len(graph),
            "cancelled": sum(e["status"] == "CANCELLED" for e in facts.exams.values()),
            "scheduling_rate": ratio(len(assignments), len(graph)), "unassigned_reasons": dict(sorted(reasons.items())),
            "conflict_graph": {"vertices": len(graph), "edges": len(edges), "max_degree": max(map(len, graph.values()), default=0)},
            "room_time": {"used_minutes": room_used, "available_minutes": room_available, "utilization": ratio(room_used, room_available)},
            "seat_time": {"used_student_seat_minutes": seat_used, "available_seat_minutes": seat_available,
                          "allocated_seat_minutes": allocated, "utilization": ratio(seat_used, seat_available), "occupied_room_fill": ratio(seat_used, allocated)},
            "invigilator_time": {"used_minutes": staff_used, "available_minutes": staff_available, "utilization": ratio(staff_used, staff_available)},
            "accommodations": {"required_student_exam_support_records_all": required_all, "required_scheduled": required_scheduled,
                               "fulfilled": fulfilled, "coverage_scheduled": ratio(fulfilled, required_scheduled),
                               "coverage_all_eligible": ratio(fulfilled, required_all), "extra_room_minutes": extra_room_minutes,
                               "extra_staff_minutes": extra_staff_minutes},
            "rooms": rooms, "invigilators": staff,
            "definitions": {
                "scheduling_rate": "scheduled / all PLANNED exams; CANCELLED excluded, honest unassigned included",
                "room_time": "accepted room-minutes / open, effective, non-closed room-minutes in the full ten-weekday horizon",
                "seat_time": "enrolled learner-minutes / effective seat-minutes of all usable rooms in the horizon",
                "occupied_room_fill": "enrolled learner-minutes / capacity-minutes of occupied rooms",
                "invigilator_time": "allocated invigilator-minutes / effective AVAILABLE invigilator-minutes in the horizon",
                "coverage_scheduled": "fulfilled approved student-exam support records / required support records for scheduled exams",
                "coverage_all_eligible": "fulfilled approved student-exam support records / required support records for all planned exams",
                "extra_room_minutes": "sum of whole-exam duration minus base duration; the price of the simple accommodation policy"}}

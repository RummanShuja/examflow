"""Deterministic graph-degree greedy placement; no access to evaluation labels."""
from collections import Counter, defaultdict

from .common import at, canonical, covered, days, overlaps, plus
from .domain import Facts, conflict_graph

STARTS = ((8, 0), (10, 30), (13, 0), (15, 30))


def schedule(conn):
    """Append one complete, atomic run. Never erase or replace earlier decisions."""
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        sequence = conn.execute("SELECT count(*) + 1 FROM SchedulingRun").fetchone()[0]
        run_id = f"RUN-{sequence:06d}"
        facts = Facts(conn)
        graph, edges = conflict_graph(facts)
        requirements = {eid: facts.derive(eid)[0] for eid in graph}
        order = sorted(graph, key=lambda eid: (-len(graph[eid]), -requirements[eid]["duration_minutes"],
                                               -requirements[eid]["enrolled_count"], eid))
        assigned, outcomes = {}, []
        room_busy, staff_busy, workload = defaultdict(list), defaultdict(list), Counter()
        candidates = [at(day, h, m) for day in days() for h, m in STARTS]
        for rank, eid in enumerate(order, 1):
            exam, req = facts.exams[eid], requirements[eid]
            rejection = Counter()
            if req["enrolled_count"] == 0:
                outcomes.append((eid, None, "NO_ENROLLMENTS", {"explanation": "No active enrolled learners at the scheduling horizon.", "rank": rank}))
                continue
            compatible = [rid for rid, room in sorted(facts.rooms.items())
                          if room["status"] == "OPEN" and facts.exam_equipment[eid] <= facts.room_equipment[rid]
                          and (not req["accessible_required"] or room["accessible"])
                          and any(c["seats"] >= req["enrolled_count"] for c in facts.capacities[rid])]
            if not compatible:
                missing = sorted(facts.exam_equipment[eid] - set().union(*facts.room_equipment.values()))
                outcomes.append((eid, None, "NO_COMPATIBLE_ROOM", {
                    "explanation": "No room satisfies static equipment, accessibility and capacity requirements under the one-room policy.",
                    "required_equipment": sorted(facts.exam_equipment[eid]), "equipment_absent_from_all_rooms": missing,
                    "demand": req["enrolled_count"], "accessible_required": req["accessible_required"],
                    "rooms_considered": len(facts.rooms), "rank": rank}))
                continue
            selected = None
            for start in candidates:
                end = plus(start, req["duration_minutes"])
                if start < exam["window_start"] or end > exam["window_end"]:
                    rejection["EXAM_WINDOW"] += 1
                    continue
                if any(other in assigned and overlaps(start, end, assigned[other]["starts_at"], assigned[other]["ends_at"])
                       for other in graph[eid]):
                    rejection["STUDENT_CONFLICT"] += 1
                    continue
                _, _, obligations = facts.derive(eid, start)
                if any(a["effective_to"] < end for a in obligations):
                    rejection["ACCOMMODATION_EFFECTIVE_INTERVAL"] += 1
                    continue
                fitting = []
                for rid in compatible:
                    room = facts.rooms[rid]
                    cap = facts.capacity(rid, start, end)
                    if cap is None or cap < req["enrolled_count"]:
                        rejection["CAPACITY"] += 1
                    elif (room["effective_from"] > start or (room["effective_to"] is not None and room["effective_to"] < end)
                          or not covered(facts.openings[rid], start, end)
                          or any(overlaps(start, end, a, b) for a, b in facts.closures[rid])):
                        rejection["ROOM_AVAILABILITY"] += 1
                    elif any(overlaps(start, end, a, b) for a, b in room_busy[rid]):
                        rejection["ROOM_BUSY"] += 1
                    else:
                        fitting.append((cap - req["enrolled_count"], rid))
                if not fitting:
                    continue
                available = []
                for iid in sorted(facts.staff, key=lambda k: (workload[k], k)):
                    inv = facts.staff[iid]
                    if (inv["status"] == "ACTIVE" and inv["effective_from"] <= start
                            and (inv["effective_to"] is None or end <= inv["effective_to"])
                            and covered(facts.availability[iid], start, end)
                            and not any(overlaps(start, end, a, b) for a, b in staff_busy[iid])):
                        available.append(iid)
                        if len(available) == req["invigilators_required"]:
                            break
                if len(available) < req["invigilators_required"]:
                    rejection["INSUFFICIENT_AVAILABLE_INVIGILATORS"] += 1
                    continue
                rid = min(fitting)[1]
                selected = {"assignment_id": f"ASN-{eid}-{rid}", "exam_id": eid, "room_id": rid,
                            "starts_at": start, "ends_at": end, "invigilator_ids": available}
                break
            evidence = {"rank": rank, "degree": len(graph[eid]), "candidate_start_count": len(candidates),
                        "rejection_counts": dict(sorted(rejection.items()))}
            if selected:
                assigned[eid] = selected
                room_busy[selected["room_id"]].append((selected["starts_at"], selected["ends_at"]))
                for iid in selected["invigilator_ids"]:
                    staff_busy[iid].append((selected["starts_at"], selected["ends_at"]))
                    workload[iid] += req["duration_minutes"]
                evidence["explanation"] = "First feasible candidate start, smallest sufficient room, then least-used available staff; ID breaks ties."
                outcomes.append((eid, selected, None, evidence))
            else:
                evidence["explanation"] = "Greedy candidate-start policy found no feasible placement; this is not a proof that all continuous-time schedules are impossible."
                outcomes.append((eid, None, "NO_FEASIBLE_SLOT", evidence))
        # Logical times are reproducible simulation metadata, never artifact timestamps.
        logical_start = plus("2026-11-01T12:00:00+05:30", sequence - 1)
        logical_end = plus(logical_start, 1)
        conn.execute("INSERT INTO SchedulingRun VALUES (?, ?, ?, ?, ?, ?)",
                     (run_id, "degree-greedy-v1", "COMPLETED", logical_start, logical_end,
                      canonical({"candidate_starts_local": [f"{h:02d}:{m:02d}" for h, m in STARTS], "room_policy": "single", "ratio": 40})))
        event_counter = 0

        def decision(kind, eid, payload, when=logical_start):
            nonlocal event_counter
            event_counter += 1
            conn.execute("INSERT INTO DecisionEvent VALUES (?, ?, ?, ?, ?, ?)",
                         (f"DEC-{run_id}-{event_counter:06d}", run_id, eid, kind, when, canonical(payload)))

        decision("RUN_STARTED", None, {"graph_vertices": len(graph), "graph_edges": len(edges), "ordering": "degree,duration,demand descending; exam_id ascending"})
        for eid, assignment, reason, evidence in outcomes:
            if assignment:
                a = assignment
                conn.execute("INSERT INTO ScheduleAssignment VALUES (?, ?, ?, ?, ?, ?, ?)",
                             (run_id, a["assignment_id"], eid, a["room_id"], a["starts_at"], a["ends_at"], "ACCEPTED"))
                conn.executemany("INSERT INTO InvigilatorAllocation VALUES (?, ?, ?)",
                                 [(run_id, a["assignment_id"], iid) for iid in a["invigilator_ids"]])
                conn.execute("INSERT INTO ExamOutcome VALUES (?, ?, ?, ?, ?, ?)",
                             (run_id, eid, "SCHEDULED", a["assignment_id"], None, canonical(evidence)))
                decision("EXAM_ASSIGNED", eid, {**evidence, "assignment": a})
            else:
                conn.execute("INSERT INTO ExamOutcome VALUES (?, ?, ?, ?, ?, ?)",
                             (run_id, eid, "UNASSIGNED", None, reason, canonical(evidence)))
                decision("EXAM_UNASSIGNED", eid, {**evidence, "reason_code": reason})
        decision("RUN_COMPLETED", None, {"scheduled": len(assigned), "unassigned": len(outcomes)-len(assigned)}, logical_end)
    return run_id


def read_assignments(conn, run_id):
    result = []
    for row in conn.execute("SELECT * FROM ScheduleAssignment WHERE run_id=? ORDER BY exam_id", (run_id,)):
        a = dict(row)
        a["invigilator_ids"] = [r[0] for r in conn.execute(
            "SELECT invigilator_id FROM InvigilatorAllocation WHERE run_id=? AND assignment_id=? ORDER BY invigilator_id",
            (run_id, a["assignment_id"]))]
        result.append(a)
    return result

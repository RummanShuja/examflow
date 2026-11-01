"""Source facts and conflict graph used by the scheduler (not the detector)."""
from collections import defaultdict
from itertools import combinations
from math import ceil

from .common import covered, rows


class Facts:
    def __init__(self, conn):
        self.students = {r["student_id"]: r for r in rows(conn, "Student")}
        self.exams = {r["exam_id"]: r for r in rows(conn, "Exam")}
        self.requirements = {r["exam_id"]: r for r in rows(conn, "ExamRequirement")}
        self.rooms = {r["room_id"]: r for r in rows(conn, "Room")}
        self.staff = {r["invigilator_id"]: r for r in rows(conn, "Invigilator")}
        self.enrollments = defaultdict(list)
        self.accommodations = defaultdict(list)
        for r in rows(conn, "Enrollment"):
            self.enrollments[r["course_id"]].append(r)
        for r in rows(conn, "Accommodation"):
            self.accommodations[r["student_id"]].append(r)
        self.capacities = defaultdict(list)
        self.openings = defaultdict(list)
        self.closures = defaultdict(list)
        self.availability = defaultdict(list)
        self.room_equipment = defaultdict(set)
        self.exam_equipment = defaultdict(set)
        for r in rows(conn, "RoomCapacity"):
            self.capacities[r["room_id"]].append(r)
        for table, group in (("RoomOpening", self.openings), ("RoomClosure", self.closures)):
            for r in rows(conn, table):
                group[r["room_id"]].append((r["starts_at"], r["ends_at"]))
        for r in rows(conn, "Availability"):
            if r["status"] == "AVAILABLE":
                self.availability[r["invigilator_id"]].append((r["starts_at"], r["ends_at"]))
        for r in rows(conn, "RoomEquipment"):
            self.room_equipment[r["room_id"]].add(r["equipment_id"])
        for r in rows(conn, "ExamEquipmentRequirement"):
            self.exam_equipment[r["exam_id"]].add(r["equipment_id"])

    def derive(self, exam_id, start=None):
        exam = self.exams[exam_id]
        start = start or exam["window_start"]
        learners = set()
        for e in self.enrollments[exam["course_id"]]:
            s = self.students[e["student_id"]]
            if (e["status"] == s["status"] == "ACTIVE" and e["effective_from"] <= start
                    and (e["effective_to"] is None or start < e["effective_to"])
                    and s["effective_from"] <= start and (s["effective_to"] is None or start < s["effective_to"])):
                learners.add(s["student_id"])
        extra, accessible, obligations = 0, 0, []
        for sid in sorted(learners):
            for a in self.accommodations[sid]:
                if (a["status"] == "APPROVED" and a["exam_id"] in (None, exam_id)
                        and a["effective_from"] <= start < a["effective_to"]):
                    obligations.append(a)
                    extra = max(extra, a["extra_percent"])
                    accessible |= a["kind"] == "ACCESSIBLE_ROOM"
        return {"exam_id": exam_id, "enrolled_count": len(learners), "max_extra_percent": extra,
                "duration_minutes": ceil(exam["base_duration_minutes"] * (100 + extra) / 100),
                "accessible_required": int(accessible), "invigilators_required": ceil(len(learners) / 40)}, learners, obligations

    def capacity(self, room_id, start, end):
        relevant = [c for c in self.capacities[room_id] if c["effective_from"] < end and start < c["effective_to"]]
        if not covered([(c["effective_from"], c["effective_to"]) for c in relevant], start, end):
            return None
        return min(c["seats"] for c in relevant)


def conflict_graph(facts):
    graph = {eid: set() for eid, e in facts.exams.items() if e["status"] == "PLANNED"}
    student_exams = defaultdict(list)
    for eid in sorted(graph):
        for sid in facts.derive(eid)[1]:
            student_exams[sid].append(eid)
    weights = defaultdict(int)
    for exams in student_exams.values():
        for left, right in combinations(sorted(exams), 2):
            graph[left].add(right)
            graph[right].add(left)
            weights[(left, right)] += 1
    edges = [{"exam_a": a, "exam_b": b, "shared_students": n} for (a, b), n in sorted(weights.items())]
    return graph, edges

"""Constraint-focused regression tests, including full-scale acceptance."""
from contextlib import closing
import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from examflow.common import at, covered, days, minutes, overlaps, plus
from examflow.domain import Facts, conflict_graph
from examflow.export import export_all, table_checksums
from examflow.fixtures import evaluate, fixture_payload, write_fixtures
from examflow.generate import configuration, generate
from examflow.metrics import calculate
from examflow.reproduce import reproduce
from examflow.schema import connect, TABLES
from examflow.scheduler import read_assignments, schedule
from examflow.validate import detect, validate_run, validate_source


class StarterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="examflow-tests-")
        cls.folder = Path(cls.temp.name)
        cls.path = cls.folder / "source.sqlite3"
        generate(cls.path, configuration("starter"))
        cls.source = connect(cls.path)
        cls.run_id = schedule(cls.source)
        cls.assignments = read_assignments(cls.source, cls.run_id)
        cls.inputs, cls.truth = fixture_payload(cls.source)

    @classmethod
    def tearDownClass(cls):
        cls.source.close()
        cls.temp.cleanup()

    def setUp(self):
        # Isolate deliberate source mutations from baseline and other tests.
        self.conn = connect(":memory:")
        self.source.backup(self.conn)
        self.cases = copy.deepcopy(self.inputs["cases"])

    def tearDown(self):
        self.conn.close()

    def rules(self, assignments):
        return {r["rule"] for r in detect(self.conn, assignments)}

    def test_starter_schedule_has_no_hard_violations(self):
        report = validate_run(self.conn, self.run_id, self.assignments)
        self.assertTrue(report["passed"], report)
        self.assertEqual(len(self.assignments), 28)
        self.assertEqual(report["usage_reconciliation"]["staff_minutes"], report["usage_reconciliation"]["sql_staff_minutes"])

    def test_all_five_negative_rules_and_three_controls(self):
        for case, truth in zip(self.cases, self.truth["cases"]):
            with self.subTest(case=case["case_id"]):
                self.assertEqual(self.rules(case["assignments"]), set(truth["expected_rules"]))

    def test_adjacent_intervals_are_not_overlapping(self):
        a, b = self.cases[6]["assignments"]
        self.assertEqual(a["ends_at"], b["starts_at"])
        self.assertFalse(overlaps(a["starts_at"], a["ends_at"], b["starts_at"], b["ends_at"]))
        self.assertEqual(self.rules([a, b]), set())

    def test_exact_capacity_is_valid(self):
        assignment = self.cases[7]["assignments"][0]
        f = Facts(self.conn)
        self.assertEqual(f.capacity(assignment["room_id"], assignment["starts_at"], assignment["ends_at"]), f.derive(assignment["exam_id"])[0]["enrolled_count"])
        self.assertEqual(self.rules([assignment]), set())

    def test_effective_capacity_switch_at_midnight(self):
        a = copy.deepcopy(self.cases[7]["assignments"][0])
        a["room_id"] = "ROOM-000005"
        a["assignment_id"] = f"ASN-{a['exam_id']}-{a['room_id']}"
        duration = minutes(a["starts_at"], a["ends_at"])
        a["starts_at"] = "2026-11-20T08:00:00+05:30"
        a["ends_at"] = plus(a["starts_at"], duration)
        self.assertEqual(self.rules([a]), set())
        a["starts_at"] = "2026-11-23T08:00:00+05:30"
        a["ends_at"] = plus(a["starts_at"], duration)
        self.assertEqual(self.rules([a]), {"ROOM_CAPACITY"})

    def test_room_closure_is_checked_for_entire_interval(self):
        a = self.cases[5]["assignments"][0]
        self.conn.execute("INSERT INTO RoomClosure VALUES (?,?,?,?,?)", ("CLS-TEST", a["room_id"], plus(a["starts_at"], 1), plus(a["starts_at"], 2), "MAINTENANCE"))
        self.assertEqual(self.rules([a]), {"ROOM_UNAVAILABLE"})

    def test_closure_touching_end_is_legal(self):
        a = self.cases[5]["assignments"][0]
        self.conn.execute("INSERT INTO RoomClosure VALUES (?,?,?,?,?)", ("CLS-TEST", a["room_id"], a["ends_at"], plus(a["ends_at"], 30), "MAINTENANCE"))
        self.assertEqual(self.rules([a]), set())

    def test_missing_equipment_detected(self):
        a = self.cases[5]["assignments"][0]
        equipment = self.conn.execute("SELECT equipment_id FROM ExamEquipmentRequirement WHERE exam_id=?", (a["exam_id"],)).fetchone()[0]
        self.conn.execute("DELETE FROM RoomEquipment WHERE room_id=? AND equipment_id=?", (a["room_id"], equipment))
        self.assertEqual(self.rules([a]), {"EQUIPMENT_MISSING"})

    def test_invigilator_availability_must_cover_end(self):
        a = self.cases[5]["assignments"][0]
        self.conn.execute("UPDATE Availability SET ends_at=? WHERE invigilator_id=? AND starts_at LIKE '2026-11-16%'",
                          (plus(a["starts_at"], 1), a["invigilator_ids"][0]))
        self.assertEqual(self.rules([a]), {"INVIGILATOR_UNAVAILABLE"})

    def test_distinct_staff_count_and_duplicates(self):
        a = self.cases[5]["assignments"][0]
        a["invigilator_ids"] = [a["invigilator_ids"][0]] * 2
        self.assertEqual(self.rules([a]), {"INVALID_ASSIGNMENT", "INSUFFICIENT_INVIGILATORS"})

    def test_room_double_booking_with_disjoint_students(self):
        a, b = self.cases[2]["assignments"]
        b["room_id"] = a["room_id"]
        b["assignment_id"] = f"ASN-{b['exam_id']}-{b['room_id']}"
        b["invigilator_ids"] = [f"INV-{i+1+len(a['invigilator_ids']):06d}" for i in range(len(b["invigilator_ids"]))]
        self.assertEqual(self.rules([a, b]), {"ROOM_DOUBLE_BOOKED"})

    def test_only_approved_accommodations_apply(self):
        a = self.cases[3]["assignments"][0]
        self.assertEqual(self.rules([a]), {"ACCOMMODATION_IGNORED"})
        self.conn.execute("UPDATE Accommodation SET status='PENDING'")
        self.assertEqual(self.rules([a]), set())

    def test_unavailable_room_and_exam_window_are_distinct(self):
        a = self.cases[5]["assignments"][0]
        duration = minutes(a["starts_at"], a["ends_at"])
        a["starts_at"] = "2026-11-15T08:00:00+05:30"
        a["ends_at"] = plus(a["starts_at"], duration)
        self.assertIn("EXAM_WINDOW", self.rules([a]))

    def test_bad_foreign_key_in_import(self):
        a = self.cases[5]["assignments"][0]
        a["room_id"] = "ROOM-999999"
        a["assignment_id"] = f"ASN-{a['exam_id']}-{a['room_id']}"
        self.assertEqual(self.rules([a]), {"FOREIGN_KEY"})

    def test_invalid_interval_and_wrong_timezone_rejected(self):
        a = self.cases[5]["assignments"][0]
        a["ends_at"] = a["starts_at"]
        self.assertEqual(self.rules([a]), {"INVALID_INTERVAL"})
        a["ends_at"] = "2026-11-16T11:00:00+00:00"
        self.assertEqual(self.rules([a]), {"INVALID_INTERVAL"})

    def test_duplicate_import_and_incomplete_import(self):
        a = self.cases[5]["assignments"][0]
        self.assertIn("DUPLICATE_ASSIGNMENT", self.rules([a, a]))
        report = detect(self.conn, [a], expected_exam_ids={a["exam_id"], "EXAM-2026-000002"})
        self.assertIn("OUTCOME_COVERAGE", {x["rule"] for x in report})

    def test_sqlite_constraints_and_foreign_key_enforcement(self):
        self.assertEqual(self.conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO Enrollment VALUES ('ENR-TEST','STU-999999','CRS-000001','ACTIVE','2026-07-01T00:00:00+05:30',NULL)")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO Student SELECT * FROM Student LIMIT 1")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE Student SET status='UNKNOWN' WHERE student_id='STU-000001'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE RoomCapacity SET seats=0 WHERE capacity_id='CAP-000001'")

    def test_history_is_append_only(self):
        for table in ("ScheduleAssignment", "ExamOutcome", "DecisionEvent", "LifecycleEvent", "SchedulingRun", "InvigilatorAllocation"):
            with self.subTest(table=table), self.assertRaises(sqlite3.IntegrityError):
                self.conn.execute(f"DELETE FROM {table}")

    def test_primary_keys_are_immutable_even_without_children(self):
        self.conn.execute("INSERT INTO Equipment VALUES ('EQ-UNREFERENCED','Test equipment')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE Equipment SET equipment_id='EQ-CHANGED' WHERE equipment_id='EQ-UNREFERENCED'")

    def test_second_run_retains_first_run(self):
        original = read_assignments(self.conn, self.run_id)
        second = schedule(self.conn)
        self.assertEqual(second, "RUN-000002")
        self.assertEqual(read_assignments(self.conn, self.run_id), original)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM SchedulingRun").fetchone()[0], 2)
        strip = lambda data: [{k: v for k, v in a.items() if k != "run_id"} for a in data]
        self.assertEqual(strip(original), strip(read_assignments(self.conn, second)))
        self.assertTrue(validate_run(self.conn, second, read_assignments(self.conn, second))["passed"])

    def test_illegal_lifecycle_event_is_detected(self):
        self.conn.execute("""INSERT INTO LifecycleEvent(event_id,student_id,from_state,to_state,occurred_at)
                          VALUES ('LFE-TEST','STU-000001','ACTIVE','WITHDRAWN','2026-11-01T00:00:00+05:30')""")
        errors = validate_source(self.conn)["errors"]
        self.assertIn("LIFECYCLE_TRANSITION", {r["rule"] for r in errors})

    def test_cached_derived_values_are_recalculated(self):
        self.conn.execute("UPDATE ExamRequirement SET enrolled_count=enrolled_count+1 WHERE exam_id='EXAM-2026-000001'")
        self.assertIn("DERIVED_REQUIREMENT", {r["rule"] for r in validate_source(self.conn)["errors"]})
        # Independent assignment detection does not trust the tampered cache.
        self.assertEqual(self.rules(self.cases[5]["assignments"]), set())

    def test_cancelled_exam_not_scheduled(self):
        cancelled = self.conn.execute("SELECT exam_id FROM Exam WHERE status='CANCELLED'").fetchone()[0]
        self.assertNotIn(cancelled, {a["exam_id"] for a in self.assignments})
        self.assertEqual(self.conn.execute("SELECT count(*) FROM ExamOutcome WHERE exam_id=?", (cancelled,)).fetchone()[0], 0)

    def test_infeasible_demand_has_rule_derived_reason(self):
        expected = self.truth["expected_decisions"][0]
        actual = self.conn.execute("SELECT status,reason_code,evidence_json FROM ExamOutcome WHERE run_id=? AND exam_id=?", (self.run_id, expected["exam_id"])).fetchone()
        self.assertEqual(tuple(actual[:2]), ("UNASSIGNED", "NO_COMPATIBLE_ROOM"))
        self.assertEqual(json.loads(actual[2])["equipment_absent_from_all_rooms"], ["EQ-SECURE"])

    def test_labels_are_absent_from_inputs_and_not_read_by_detector(self):
        serialized = json.dumps(self.inputs)
        for label in ("expected_rules", "issue_type", "rationale", "ground_truth"):
            self.assertNotIn(label, serialized)
        with patch("pathlib.Path.read_text", side_effect=AssertionError("Detector attempted file read")):
            self.assertEqual(self.rules(self.cases[5]["assignments"]), set())

    def test_evaluator_counts_clean_controls(self):
        folder = self.folder / "fixtures"
        write_fixtures(self.conn, folder)
        result = evaluate(self.conn, folder, self.run_id)
        self.assertTrue(result["passed"])
        self.assertEqual((result["micro"]["tp"], result["micro"]["fp"], result["micro"]["fn"]), (5, 0, 0))
        self.assertEqual(len(result["cases"]), 8)

    def test_every_graph_edge_is_source_derived(self):
        facts = Facts(self.conn)
        graph, edges = conflict_graph(facts)
        for edge in edges:
            self.assertEqual(edge["shared_students"], len(facts.derive(edge["exam_a"])[1] & facts.derive(edge["exam_b"])[1]))
        self.assertEqual(len(graph), 29)

    def test_adjacent_availability_records_form_full_coverage(self):
        self.assertTrue(covered([("a", "b"), ("b", "c")], "a", "c"))
        self.assertFalse(covered([("a", "b"), ("c", "d")], "a", "d"))

    def test_source_reuse_preserves_runs_and_rejects_new_seed(self):
        generate(self.path, configuration("starter"))
        with closing(connect(self.path)) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM SchedulingRun").fetchone()[0], 1)
        with self.assertRaises(ValueError):
            generate(self.path, configuration("starter", seed=123))

    def test_two_independent_builds_match_every_table(self):
        report = reproduce(configuration("starter"), self.folder / "reproduce.json")
        self.assertTrue(report["passed"])
        self.assertEqual(set(report["tables"]), {t.name for t in TABLES})
        self.assertEqual(report["excluded_columns"], [])

    def test_sql_export_roundtrip_preserves_all_tables(self):
        metrics = calculate(self.conn, self.run_id, self.assignments)
        folder = self.folder / "roundtrip"
        export_all(self.conn, self.run_id, self.assignments, folder, metrics)
        with closing(connect(":memory:")) as restored:
            restored.executescript((folder / "exports/database_seed.sql").read_text(encoding="utf-8"))
            self.assertEqual(table_checksums(self.conn), table_checksums(restored))
            self.assertEqual(restored.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_import_failure_produces_nonzero_cli_exit(self):
        path = self.folder / "bad_import.json"
        path.write_text(json.dumps(self.cases[1]["assignments"]), encoding="utf-8")
        completed = subprocess.run([sys.executable, "-m", "examflow", "validate", "--db", str(self.path),
                                    "--assignments", str(path), "--allow-partial", "--output", str(self.folder / "bad_report.json")],
                                   capture_output=True, text=True)
        self.assertEqual(completed.returncode, 2, completed.stdout+completed.stderr)
        self.assertFalse(json.loads((self.folder / "bad_report.json").read_text())["passed"])

    def test_scaled_configuration_uses_same_generation_contract(self):
        config = configuration("full", scale=0.1)
        self.assertEqual((config["students"], config["exams"], config["rooms"], config["invigilators"]), (500, 30, 10, 20))
        path = self.folder / "scaled.sqlite3"
        generate(path, config)
        with closing(connect(path)) as conn:
            rid = schedule(conn)
            self.assertTrue(validate_run(conn, rid, read_assignments(conn, rid))["passed"])


class FullScaleAcceptance(unittest.TestCase):
    def test_required_volumes_and_zero_constraint_violations(self):
        with tempfile.TemporaryDirectory(prefix="examflow-full-test-") as temporary:
            path = Path(temporary) / "full.sqlite3"
            generate(path, configuration("full"))
            with closing(connect(path)) as conn:
                self.assertEqual([conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                                  for table in ("Student", "Exam", "Room", "Invigilator")], [5000, 300, 100, 200])
                rid = schedule(conn)
                assignments = read_assignments(conn, rid)
                result = validate_run(conn, rid, assignments)
                self.assertTrue(result["passed"], result)
                self.assertEqual(len(assignments), 298)
                metrics = calculate(conn, rid, assignments)
                self.assertEqual(metrics["accommodations"]["coverage_scheduled"], 1.0)
                self.assertLessEqual(metrics["room_time"]["used_minutes"], metrics["room_time"]["available_minutes"])
                self.assertEqual(sum(r["used_minutes"] for r in metrics["invigilators"]), result["usage_reconciliation"]["staff_minutes"])


if __name__ == "__main__":
    unittest.main()

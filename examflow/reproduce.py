"""Two independent builds compare every table and deterministic scheduling."""
from contextlib import closing
from pathlib import Path
import tempfile

from .common import digest
from .export import table_checksums, write_json
from .fixtures import fixture_payload
from .generate import generate
from .schema import connect
from .scheduler import read_assignments, schedule
from .validate import validate_run


def reproduce(config, output):
    builds = []
    with tempfile.TemporaryDirectory(prefix="examflow-repro-") as temporary:
        for i in range(2):
            path = Path(temporary) / f"independent-{i+1}.sqlite3"
            generate(path, config)
            with closing(connect(path)) as conn:
                rid = schedule(conn)
                assignments = read_assignments(conn, rid)
                check = validate_run(conn, rid, assignments)
                fixtures = fixture_payload(conn)
                builds.append({"tables": table_checksums(conn), "schedule_sha256": digest(assignments),
                               "fixture_input_sha256": digest(fixtures[0]), "ground_truth_sha256": digest(fixtures[1]),
                               "validation_passed": check["passed"]})
    comparisons = {table: {"build_1": builds[0]["tables"][table], "build_2": builds[1]["tables"][table],
                           "matched": builds[0]["tables"][table] == builds[1]["tables"][table]} for table in builds[0]["tables"]}
    schedule_match = builds[0]["schedule_sha256"] == builds[1]["schedule_sha256"]
    fixture_match = all(builds[0][key] == builds[1][key] for key in ("fixture_input_sha256", "ground_truth_sha256"))
    report = {"passed": all(c["matched"] for c in comparisons.values()) and schedule_match and fixture_match
                        and all(b["validation_passed"] for b in builds),
              "configuration": config, "independent_builds": 2, "tables": comparisons,
              "schedule_matched": schedule_match, "schedule_sha256": [b["schedule_sha256"] for b in builds],
              "fixtures_matched": fixture_match, "both_validated": all(b["validation_passed"] for b in builds),
              "excluded_columns": [], "scope": "Two fresh databases each have one run. Existing user databases and their run history are never replaced.",
              "checksum_contract": "Every table: primary-key order, canonical sorted-key JSON records, UTF-8, one LF per record; SHA-256."}
    write_json(output, report)
    return report

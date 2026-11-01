"""Cross-platform regression tests for SQLite handles blocking Windows cleanup."""
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

import examflow.generate as generator
import examflow.reproduce as reproducibility
from examflow.schema import connect


class ConnectionLifecycleTests(unittest.TestCase):
    def assert_all_closed(self, handles):
        self.assertTrue(handles, "No SQLite handles were observed")
        for handle in handles:
            with self.assertRaises(sqlite3.ProgrammingError, msg="SQLite handle still open before directory cleanup"):
                handle.execute("SELECT 1")

    def test_reused_source_lookup_closes_on_success_and_error(self):
        with tempfile.TemporaryDirectory(prefix="examflow-reuse-handles-") as directory:
            path = Path(directory) / "source.sqlite3"
            generator.generate(path, generator.configuration("starter"))
            handles = []

            def track(path):
                handle = connect(path)
                handles.append(handle)  # Keep references: do not rely on garbage collection.
                return handle

            try:
                with patch("examflow.generate.connect", side_effect=track):
                    generator.generate(path, generator.configuration("starter"))
                    self.assert_all_closed(handles)
                    with self.assertRaises(ValueError):
                        generator.generate(path, generator.configuration("starter", seed=1))
                    self.assert_all_closed(handles)
            finally:
                for handle in handles:
                    handle.close()

    def test_reproduction_closes_handles_before_temp_cleanup_even_on_error(self):
        real_temporary_directory = tempfile.TemporaryDirectory
        for fail_validation in (False, True):
            with self.subTest(fail_validation=fail_validation), real_temporary_directory() as output_directory:
                handles = []

                def track(path):
                    handle = connect(path)
                    handles.append(handle)
                    return handle

                test = self

                class CheckedDirectory:
                    def __init__(self, *args, **kwargs):
                        self.actual = real_temporary_directory(*args, **kwargs)

                    def __enter__(self):
                        return self.actual.__enter__()

                    def __exit__(self, exc_type, exc, traceback):
                        try:
                            # Linux permits unlinking an open file; inspect handles directly
                            # to enforce the same close-before-delete requirement as Windows.
                            test.assert_all_closed(handles)
                        finally:
                            for handle in handles:
                                handle.close()
                            self.actual.__exit__(exc_type, exc, traceback)
                        return False

                with patch("examflow.reproduce.tempfile.TemporaryDirectory", CheckedDirectory), \
                     patch("examflow.generate.connect", side_effect=track), \
                     patch("examflow.reproduce.connect", side_effect=track):
                    output = Path(output_directory) / "reproducibility.json"
                    if fail_validation:
                        with patch("examflow.reproduce.validate_run", side_effect=RuntimeError("injected validation failure")):
                            with self.assertRaisesRegex(RuntimeError, "injected validation failure"):
                                reproducibility.reproduce(generator.configuration("starter"), output)
                    else:
                        report = reproducibility.reproduce(generator.configuration("starter"), output)
                        self.assertTrue(report["passed"])

    def test_connection_configuration_failure_closes_handle(self):
        handle = Mock()
        handle.execute.return_value.fetchone.return_value = (0,)
        with patch("examflow.schema.sqlite3.connect", return_value=handle):
            with self.assertRaisesRegex(RuntimeError, "foreign-key enforcement"):
                connect(":memory:")
        handle.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()

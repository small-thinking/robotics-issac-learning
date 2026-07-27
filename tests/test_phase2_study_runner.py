from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.run_phase2_study import sha256_file, write_json


class Phase2StudyRunnerTest(unittest.TestCase):
    def test_write_json_is_atomic_and_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            write_json(path, {"b": 2, "a": 1})
            self.assertEqual(path.read_text(), '{\n  "a": 1,\n  "b": 2\n}\n')
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_sha256_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.txt"
            path.write_text("cartpole\n")
            self.assertEqual(
                sha256_file(path),
                "e790cbd57afdaacb14adb2bbd48a512c4cbc12fcf230148b67c8f375293d875a",
            )


if __name__ == "__main__":
    unittest.main()

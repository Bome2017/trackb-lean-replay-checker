# SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / ".lake" / "build" / "bin" / "trackb-replay-check"
WORKFLOW = ROOT / "fixtures" / "unsafe_workflow.json"
RESULT = ROOT / "fixtures" / "unsafe_result.json"
WRAPPER = ROOT / "scripts" / "check_pair.py"


class EndToEndTests(unittest.TestCase):
    def run_checker(self, workflow: Path, result: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(CHECKER), str(workflow), str(result)],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_valid_runtime_pair_passes(self) -> None:
        completed = self.run_checker(WORKFLOW, RESULT)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("PASS workflow=unauthorized_send", completed.stdout)

    def test_tampered_transition_fails(self) -> None:
        payload = json.loads(RESULT.read_text(encoding="utf-8"))
        payload["trace"][1]["state_after"]["sent"] = False
        with tempfile.TemporaryDirectory() as temp_name:
            tampered = Path(temp_name) / "tampered_result.json"
            tampered.write_text(json.dumps(payload), encoding="utf-8")
            completed = self.run_checker(WORKFLOW, tampered)
        self.assertEqual(completed.returncode, 1)
        self.assertIn("not a valid bounded counterexample", completed.stderr)

    def test_workflow_result_binding_fails_closed(self) -> None:
        payload = json.loads(WORKFLOW.read_text(encoding="utf-8"))
        payload["bound"] = 0
        with tempfile.TemporaryDirectory() as temp_name:
            tampered = Path(temp_name) / "tampered_workflow.json"
            tampered.write_text(json.dumps(payload), encoding="utf-8")
            completed = self.run_checker(tampered, RESULT)
        self.assertEqual(completed.returncode, 1)

    def test_safe_result_is_out_of_scope(self) -> None:
        payload = json.loads(RESULT.read_text(encoding="utf-8"))
        payload["status"] = "SAFE_WITHIN_BOUND"
        payload["violation"] = None
        payload["trace"] = None
        with tempfile.TemporaryDirectory() as temp_name:
            safe_result = Path(temp_name) / "safe_result.json"
            safe_result.write_text(json.dumps(payload), encoding="utf-8")
            completed = self.run_checker(WORKFLOW, safe_result)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("outside this checker", completed.stderr)

    def test_receipt_binds_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            receipt = Path(temp_name) / "receipt.json"
            completed = subprocess.run(
                [
                    "python3",
                    str(WRAPPER),
                    str(WORKFLOW),
                    str(RESULT),
                    "--receipt",
                    str(receipt),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(payload["verdict"], "PASS")
        self.assertEqual(
            payload["inputs"]["workflow"]["sha256"],
            hashlib.sha256(WORKFLOW.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            payload["inputs"]["result"]["sha256"],
            hashlib.sha256(RESULT.read_bytes()).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()

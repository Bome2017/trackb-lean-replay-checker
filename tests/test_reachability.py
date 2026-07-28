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
BIN = ROOT / ".lake" / "build" / "bin"
SEARCH = BIN / "trackb-reachability"
REPLAY_CHECKER = BIN / "trackb-replay-check"
SAFETY_CHECKER = BIN / "trackb-global-safety-check"
FIXTURE_CHECKER = BIN / "trackb-guarded-fixture-check"
UNSAFE_WORKFLOW = ROOT / "fixtures" / "unsafe_workflow.json"

GUARDED_FIXTURES = {
    "agent_email_requires_approval": {
        "path": (
            ROOT
            / "fixtures"
            / "guarded"
            / "agent_email_requires_approval"
            / "workflow.json"
        ),
        "sha256": (
            "88fc0c4eb52487cf00a8dda32fb9dc14473b44ab694919ca82cbdf50097dabf9"
        ),
        "closure": 6,
    },
    "agent_delete_requires_confirmation": {
        "path": (
            ROOT
            / "fixtures"
            / "guarded"
            / "agent_delete_requires_confirmation"
            / "workflow.json"
        ),
        "sha256": (
            "2c1adc8dfaac1ae2b16bf53115305024bdcee9b2ed9900927c4f557fa0836acd"
        ),
        "closure": 5,
    },
    "agent_vendor_payment_guarded": {
        "path": (
            ROOT
            / "fixtures"
            / "guarded"
            / "agent_vendor_payment_guarded"
            / "workflow.json"
        ),
        "sha256": (
            "39a0ebcd1de6ba8ff673a98414b65ee344a22d2089a997e32822f6a673f4f740"
        ),
        "closure": 16,
    },
}


def run(*args: Path | str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(arg) for arg in args],
        check=False,
        capture_output=True,
        text=True,
    )


class ReachabilityTests(unittest.TestCase):
    def test_generated_unsafe_result_passes_native_replay_checker(self) -> None:
        searched = run(SEARCH, UNSAFE_WORKFLOW)
        self.assertEqual(searched.returncode, 0, searched.stderr)
        result = json.loads(searched.stdout)
        self.assertEqual(result["status"], "UNSAFE")

        with tempfile.TemporaryDirectory() as temp_name:
            result_path = Path(temp_name) / "generated_result.json"
            result_path.write_text(searched.stdout, encoding="utf-8")
            checked = run(REPLAY_CHECKER, UNSAFE_WORKFLOW, result_path)

        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertIn("PASS workflow=unauthorized_send", checked.stdout)

    def test_safe_within_bound_is_distinct_from_global_safety(self) -> None:
        workflow = {
            "schema_version": "0.1",
            "name": "bad_after_horizon",
            "bound": 0,
            "state_variables": {"bad": "bool"},
            "initial_state": {"bad": False},
            "actions": [
                {
                    "name": "make_bad",
                    "pre": {},
                    "effects": {"bad": True},
                }
            ],
            "forbidden": {"all": {"bad": True}},
        }
        with tempfile.TemporaryDirectory() as temp_name:
            workflow_path = Path(temp_name) / "workflow.json"
            workflow_path.write_text(
                json.dumps(workflow),
                encoding="utf-8",
            )
            searched = run(SEARCH, workflow_path)

        self.assertEqual(searched.returncode, 0, searched.stderr)
        result = json.loads(searched.stdout)
        self.assertEqual(result["status"], "SAFE_WITHIN_BOUND")
        self.assertIn("does not prove global safety", result["claim_boundary"])
        self.assertEqual(len(result["visited"]), 1)
        self.assertEqual(len(result["frontier"]), 1)

    def test_guarded_fixtures_bind_and_have_checked_global_certificates(
        self,
    ) -> None:
        for name, fixture in GUARDED_FIXTURES.items():
            with self.subTest(workflow=name):
                path = fixture["path"]
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    fixture["sha256"],
                )

                correspondence = run(FIXTURE_CHECKER, path)
                self.assertEqual(
                    correspondence.returncode,
                    0,
                    correspondence.stderr,
                )
                self.assertIn("model=exact", correspondence.stdout)

                searched = run(SEARCH, path)
                self.assertEqual(searched.returncode, 0, searched.stderr)
                result = json.loads(searched.stdout)
                self.assertEqual(result["status"], "GLOBALLY_SAFE")
                self.assertEqual(len(result["closure"]), fixture["closure"])

                with tempfile.TemporaryDirectory() as temp_name:
                    result_path = Path(temp_name) / "global_result.json"
                    result_path.write_text(
                        searched.stdout,
                        encoding="utf-8",
                    )
                    checked = run(SAFETY_CHECKER, path, result_path)
                self.assertEqual(checked.returncode, 0, checked.stderr)
                self.assertIn(f"PASS workflow={name}", checked.stdout)

    def test_incomplete_global_closure_is_rejected(self) -> None:
        fixture = GUARDED_FIXTURES["agent_email_requires_approval"]["path"]
        searched = run(SEARCH, fixture)
        self.assertEqual(searched.returncode, 0, searched.stderr)
        result = json.loads(searched.stdout)
        result["closure"].pop()

        with tempfile.TemporaryDirectory() as temp_name:
            result_path = Path(temp_name) / "incomplete_closure.json"
            result_path.write_text(json.dumps(result), encoding="utf-8")
            checked = run(SAFETY_CHECKER, fixture, result_path)

        self.assertEqual(checked.returncode, 1)
        self.assertIn("not a valid closed-state", checked.stderr)

    def test_guarded_fixture_correspondence_mismatch_fails(self) -> None:
        fixture = GUARDED_FIXTURES["agent_email_requires_approval"]["path"]
        workflow = json.loads(fixture.read_text(encoding="utf-8"))
        workflow["actions"][0]["effects"]["has_customer_data"] = False

        with tempfile.TemporaryDirectory() as temp_name:
            changed = Path(temp_name) / "changed_workflow.json"
            changed.write_text(json.dumps(workflow), encoding="utf-8")
            checked = run(FIXTURE_CHECKER, changed)

        self.assertEqual(checked.returncode, 1)
        self.assertIn("differs from the frozen theorem model", checked.stderr)

    def test_forbidden_sibling_key_is_rejected(self) -> None:
        fixture = GUARDED_FIXTURES["agent_delete_requires_confirmation"]["path"]
        workflow = json.loads(fixture.read_text(encoding="utf-8"))
        workflow["forbidden"]["any"] = {}

        with tempfile.TemporaryDirectory() as temp_name:
            malformed = Path(temp_name) / "malformed_workflow.json"
            malformed.write_text(json.dumps(workflow), encoding="utf-8")
            searched = run(SEARCH, malformed)

        self.assertEqual(searched.returncode, 2)
        self.assertIn("forbidden: expected exactly keys", searched.stderr)


if __name__ == "__main__":
    unittest.main()

# SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
# SPDX-License-Identifier: Apache-2.0
"""Regression tests for the proof-bound SAFE_WITHIN_BOUND emission path."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEARCH = ROOT / ".lake" / "build" / "bin" / "trackb-reachability"
REPORT = ROOT / "validation" / "bounded_result_emission_report.json"

CLAIM_BOUNDARY = (
    "SAFE_WITHIN_BOUND means no bad replay exists at or below the configured "
    "bound in the exact TrackB Boolean workflow model. It does not prove "
    "global safety or safety of undeclared runtime behavior."
)

WORKFLOW = {
    "schema_version": "0.1",
    "name": "bounded_emission_binding",
    "bound": 1,
    "state_variables": {
        "stage_one": "bool",
        "stage_two": "bool",
        "bad": "bool",
    },
    "initial_state": {
        "stage_one": False,
        "stage_two": False,
        "bad": False,
    },
    "actions": [
        {
            "name": "advance_one",
            "pre": {"stage_one": False},
            "effects": {"stage_one": True},
        },
        {
            "name": "advance_two",
            "pre": {"stage_one": True, "stage_two": False},
            "effects": {"stage_two": True},
        },
        {
            "name": "violate",
            "pre": {"stage_two": True, "bad": False},
            "effects": {"bad": True},
        },
    ],
    "forbidden": {"all": {"bad": True}},
}

EXPECTED_RESULT = {
    "workflow": "bounded_emission_binding",
    "schema_version": "0.1",
    "bound": 1,
    "status": "SAFE_WITHIN_BOUND",
    "visited": [
        {"stage_one": False, "stage_two": False, "bad": False},
        {"stage_one": True, "stage_two": False, "bad": False},
    ],
    "frontier": [
        {"stage_one": True, "stage_two": False, "bad": False},
    ],
    "claim_boundary": CLAIM_BOUNDARY,
}

SUBSTITUTED_FIELDS = (
    "workflow",
    "schema_version",
    "bound",
    "visited",
    "frontier",
    "status",
    "claim_boundary",
)

PROBE_SOURCE = r"""
import TrackBResults

open Lean
open TrackBReplay

private theorem packageEvidence
    {workflow : Workflow}
    {compiled : CompiledWorkflow workflow}
    (generated : CheckedGeneratedBoundedSafety workflow compiled) :
    reachabilityEngine compiled.kernel workflow.bound =
        .safeWithinBound generated.visited generated.frontier ∧
      generated.result =
        makeBoundedSafetyResult
          workflow generated.visited generated.frontier ∧
      ¬∃ trace,
        BoundedCounterexample
          compiled.kernel workflow.bound trace := by
  exact ⟨generated.engine, generated.generated, generated.semantic⟩

private def readAndParseWorkflow (path : System.FilePath) : IO Workflow := do
  let text ← IO.FS.readFile path
  IO.ofExcept (parseWorkflowText text)

private def inspectWorkflow (workflow : Workflow) : IO UInt32 := do
  let compiled ← IO.ofExcept workflow.compileChecked
  match runCheckedReachability workflow compiled with
  | .error message =>
      IO.eprintln s!"ERROR: {message}"
      return 2
  | .ok outcome =>
      match outcome with
      | .safeWithinBound generated =>
          let _evidence := packageEvidence generated
          let rebuilt :=
            makeBoundedSafetyResult
              workflow generated.visited generated.frontier
          let changedWorkflow : BoundedSafetyResult :=
            {
              generated.result with
              workflow := generated.result.workflow ++ "_substituted"
            }
          let changedSchema : BoundedSafetyResult :=
            {
              generated.result with
              schemaVersion := generated.result.schemaVersion ++ "_substituted"
            }
          let changedBound : BoundedSafetyResult :=
            {
              generated.result with
              bound := generated.result.bound + 1
            }
          let changedVisited : BoundedSafetyResult :=
            {
              generated.result with
              visited := generated.result.visited ++ [[]]
            }
          let changedFrontier : BoundedSafetyResult :=
            {
              generated.result with
              frontier := generated.result.frontier ++ [[]]
            }
          let changedStatus : BoundedSafetyResult :=
            {
              generated.result with
              status := generated.result.status ++ "_substituted"
            }
          let changedClaimBoundary : BoundedSafetyResult :=
            {
              generated.result with
              claimBoundary :=
                generated.result.claimBoundary ++ "_substituted"
            }
          let substitutions := Json.mkObj [
            (
              "workflow",
              Json.bool (decide (changedWorkflow = generated.result))
            ),
            (
              "schema_version",
              Json.bool (decide (changedSchema = generated.result))
            ),
            (
              "bound",
              Json.bool (decide (changedBound = generated.result))
            ),
            (
              "visited",
              Json.bool (decide (changedVisited = generated.result))
            ),
            (
              "frontier",
              Json.bool (decide (changedFrontier = generated.result))
            ),
            (
              "status",
              Json.bool (decide (changedStatus = generated.result))
            ),
            (
              "claim_boundary",
              Json.bool (decide (changedClaimBoundary = generated.result))
            )
          ]
          let report := Json.mkObj [
            (
              "carried_result",
              boundedSafetyResultToJson generated.result
            ),
            (
              "rebuilt_from_carried_lists",
              boundedSafetyResultToJson rebuilt
            ),
            (
              "engine_lists_match",
              Json.bool <| decide (
                reachabilityEngine compiled.kernel workflow.bound =
                  .safeWithinBound
                    generated.visited generated.frontier
              )
            ),
            (
              "generated_result_matches_carried_lists",
              Json.bool <| decide (generated.result = rebuilt)
            ),
            ("substitutions_equal_carried", substitutions)
          ]
          IO.println report.pretty
          return 0
      | .counterexample _ _ _ =>
          IO.eprintln "ERROR: expected SAFE_WITHIN_BOUND, found UNSAFE"
          return 2
      | .globallySafe _ _ _ =>
          IO.eprintln "ERROR: expected SAFE_WITHIN_BOUND, found GLOBALLY_SAFE"
          return 2

def main (args : List String) : IO UInt32 := do
  match args with
  | [workflowPath] =>
      try
        inspectWorkflow (← readAndParseWorkflow workflowPath)
      catch error =>
        IO.eprintln s!"ERROR: {error}"
        return 2
  | _ =>
      IO.eprintln "usage: bounded-result-probe WORKFLOW.json"
      return 2
"""


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def run(*args: Path | str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def expected_report() -> dict:
    return {
        "schema_version": "trackb.bounded-result-emission-report.v1",
        "result": "PASS",
        "release_version": "0.2.1",
        "test": "tests/test_bounded_result_emission.py",
        "fixture": {
            "name": WORKFLOW["name"],
            "canonical_input_sha256": canonical_sha256(WORKFLOW),
            "expected_carried_result": EXPECTED_RESULT,
            "canonical_result_sha256": canonical_sha256(EXPECTED_RESULT),
        },
        "checks": {
            "checked_outcome_contains_engine_equality": "PASS",
            "checked_outcome_contains_generated_equality": "PASS",
            "checked_outcome_contains_semantic_evidence": "PASS",
            "engine_lists_equal_carried_lists": "PASS",
            "generated_result_equals_constructor_on_carried_lists": "PASS",
            "search_executable_equals_carried_result": "PASS",
            "search_main_uses_generated_result_directly": "PASS",
            "search_main_has_no_bounded_result_constructor_call": "PASS",
        },
        "field_substitutions": {
            field: "DISTINCT_FROM_CARRIED_RESULT"
            for field in SUBSTITUTED_FIELDS
        },
        "bounded_checker_disposition": "DEFERRED",
        "scope": (
            "The in-process executable emits the exact BoundedSafetyResult "
            "carried by the checked SAFE_WITHIN_BOUND outcome."
        ),
        "nonclaims": [
            (
                "No independently recheckable parser or checker for supplied "
                "bounded-result JSON is implemented in v0.2.1."
            ),
            (
                "The substitution checks establish inequality with the carried "
                "object; they do not establish external rejection of supplied JSON."
            ),
            (
                "SAFE_WITHIN_BOUND is bounded no-counterexample evidence, not "
                "global safety."
            ),
        ],
    }


class BoundedResultEmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not SEARCH.is_file():
            raise AssertionError(
                "trackb-reachability is not built; run "
                "`lake build trackb-reachability` before this test"
            )

        cls.temporary = tempfile.TemporaryDirectory()
        temporary_root = Path(cls.temporary.name)
        cls.workflow_path = temporary_root / "workflow.json"
        cls.probe_path = temporary_root / "BoundedResultProbe.lean"
        cls.workflow_path.write_text(
            json.dumps(WORKFLOW, indent=2) + "\n",
            encoding="utf-8",
        )
        cls.probe_path.write_text(
            textwrap.dedent(PROBE_SOURCE).lstrip(),
            encoding="utf-8",
        )

        probed = run(
            "lake",
            "env",
            "lean",
            "--run",
            cls.probe_path,
            cls.workflow_path,
        )
        if probed.returncode != 0:
            raise AssertionError(probed.stdout + probed.stderr)
        cls.probe = json.loads(probed.stdout)

        searched = run(SEARCH, cls.workflow_path)
        if searched.returncode != 0:
            raise AssertionError(searched.stdout + searched.stderr)
        cls.emitted = json.loads(searched.stdout)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_checked_package_binds_engine_result_and_semantics(self) -> None:
        self.assertTrue(self.probe["engine_lists_match"])
        self.assertTrue(
            self.probe["generated_result_matches_carried_lists"]
        )
        self.assertEqual(
            self.probe["rebuilt_from_carried_lists"],
            self.probe["carried_result"],
        )

    def test_emitted_object_is_the_exact_carried_result(self) -> None:
        self.assertEqual(self.emitted, self.probe["carried_result"])
        self.assertEqual(self.emitted, EXPECTED_RESULT)

    def test_every_required_emitted_field_matches_engine_fixture(self) -> None:
        for field in (
            "workflow",
            "schema_version",
            "bound",
            "status",
            "visited",
            "frontier",
            "claim_boundary",
        ):
            with self.subTest(field=field):
                self.assertEqual(self.emitted[field], EXPECTED_RESULT[field])
        self.assertEqual(set(self.emitted), set(EXPECTED_RESULT))

    def test_field_substitutions_are_not_the_carried_object(self) -> None:
        observed = self.probe["substitutions_equal_carried"]
        self.assertEqual(set(observed), set(SUBSTITUTED_FIELDS))
        for field in SUBSTITUTED_FIELDS:
            with self.subTest(field=field):
                self.assertFalse(observed[field])

    def test_search_main_serializes_the_carried_result_directly(self) -> None:
        source = (ROOT / "SearchMain.lean").read_text(encoding="utf-8")
        normalized = " ".join(source.split())
        self.assertIn(
            "| .safeWithinBound generated => emitJson <| "
            "boundedSafetyResultToJson generated.result",
            normalized,
        )
        self.assertNotIn("makeBoundedSafetyResult", source)

        results_source = (ROOT / "TrackBResults.lean").read_text(
            encoding="utf-8"
        )
        results_normalized = " ".join(results_source.split())
        self.assertIn(
            "| .safeWithinBound visited frontier => .ok <| "
            ".safeWithinBound <| packageGeneratedBoundedSafety "
            "workflow compiled visited frontier hengine",
            results_normalized,
        )

    def test_deterministic_report_matches_live_validation(self) -> None:
        observed_report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(observed_report, expected_report())


if __name__ == "__main__":
    unittest.main()

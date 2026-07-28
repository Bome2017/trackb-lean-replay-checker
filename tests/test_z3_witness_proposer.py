# SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from scripts import z3_witness_proposer as proposer


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "fixtures" / "unsafe_workflow.json"


def candidate_result() -> dict:
    return json.loads((ROOT / "fixtures" / "unsafe_result.json").read_text())


class FakeEngine:
    def __init__(self, outcome: proposer.EngineOutcome) -> None:
        self.outcome = outcome
        self.calls = []

    def propose(self, workflow, *, workflow_digest, timeout_ms):
        self.calls.append(
            {
                "workflow": workflow,
                "workflow_digest": workflow_digest,
                "timeout_ms": timeout_ms,
            }
        )
        return self.outcome


def accepted_checker(checker_path, workflow_path, candidate_path, timeout_ms):
    del checker_path, timeout_ms
    assert workflow_path.read_bytes() == WORKFLOW.read_bytes()
    assert json.loads(candidate_path.read_text())["status"] == "UNSAFE"
    return proposer.CheckerOutcome(exit_code=0, stdout="PASS")


def rejected_checker(checker_path, workflow_path, candidate_path, timeout_ms):
    del checker_path, workflow_path, candidate_path, timeout_ms
    return proposer.CheckerOutcome(
        exit_code=1,
        stderr="not a valid bounded counterexample",
    )


class Z3WitnessProposerTests(unittest.TestCase):
    def make_outcome(
        self,
        kind,
        *,
        reason_unknown=None,
        candidate=None,
        error=None,
    ):
        return proposer.EngineOutcome(
            kind=kind,
            solver_version="fake-z3-1.2.3",
            query_digest="a" * 64,
            queried_depths=(0, 1),
            reason_unknown=reason_unknown,
            candidate_result=candidate,
            error=error,
        )

    def run_main(self, engine, checker_runner=accepted_checker):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        output = root / "proposal.json"
        candidate = root / "candidate.json"
        with redirect_stdout(StringIO()):
            exit_code = proposer.main(
                [
                    str(WORKFLOW),
                    "--output",
                    str(output),
                    "--candidate-result",
                    str(candidate),
                    "--checker",
                    str(root / "fake-checker"),
                    "--timeout-ms",
                    "1234",
                ],
                engine=engine,
                checker_runner=checker_runner,
            )
        record = json.loads(output.read_text())
        return exit_code, record, candidate

    def test_sat_candidate_requires_and_records_lean_acceptance(self):
        engine = FakeEngine(
            self.make_outcome("sat", candidate=candidate_result())
        )
        exit_code, record, candidate = self.run_main(engine)

        self.assertEqual(exit_code, proposer.EXIT_OK)
        self.assertEqual(record["status"], proposer.CANDIDATE_UNSAFE)
        self.assertEqual(record["comparison"]["status"], "match")
        self.assertEqual(record["checker"]["exit_code"], 0)
        self.assertTrue(candidate.exists())
        self.assertEqual(record["solver"]["version"], "fake-z3-1.2.3")
        self.assertEqual(record["query"]["timeout_ms_per_query"], 1234)
        self.assertEqual(record["query"]["sha256"], "a" * 64)
        self.assertEqual(
            record["workflow"]["sha256"],
            proposer.sha256(WORKFLOW.read_bytes()),
        )
        self.assertEqual(engine.calls[0]["timeout_ms"], 1234)

    def test_sat_candidate_crosses_the_real_lean_checker_interface(self):
        engine = FakeEngine(
            self.make_outcome("sat", candidate=candidate_result())
        )
        outcome = proposer.run_pipeline(
            workflow_path=WORKFLOW,
            checker_path=proposer.DEFAULT_CHECKER,
            timeout_ms=1234,
            checker_timeout_ms=30_000,
            engine=engine,
            checker_runner=proposer.invoke_lean_checker,
        )

        self.assertEqual(outcome.exit_code, proposer.EXIT_OK)
        self.assertEqual(outcome.record["status"], proposer.CANDIDATE_UNSAFE)
        self.assertEqual(outcome.record["checker"]["exit_code"], 0)
        self.assertIsNotNone(outcome.candidate_bytes)

    def test_unsat_is_advisory_and_never_safe(self):
        engine = FakeEngine(self.make_outcome("unsat"))
        exit_code, record, candidate = self.run_main(engine)

        self.assertEqual(exit_code, proposer.EXIT_OK)
        self.assertEqual(record["status"], proposer.NO_CANDIDATE_ADVISORY)
        self.assertNotIn("safe", record["status"].lower())
        self.assertFalse(candidate.exists())
        self.assertIsNone(record["checker"])

    def test_unknown_is_inconclusive_and_nonzero(self):
        engine = FakeEngine(
            self.make_outcome(
                proposer.INCONCLUSIVE_UNKNOWN,
                reason_unknown="incomplete theory",
            )
        )
        exit_code, record, candidate = self.run_main(engine)

        self.assertEqual(exit_code, proposer.EXIT_UNKNOWN)
        self.assertNotEqual(exit_code, 0)
        self.assertEqual(record["status"], proposer.INCONCLUSIVE_UNKNOWN)
        self.assertEqual(record["solver"]["reason_unknown"], "incomplete theory")
        self.assertFalse(candidate.exists())

    def test_solver_timeout_is_explicit_and_nonzero(self):
        engine = FakeEngine(
            self.make_outcome(
                proposer.TIMEOUT,
                reason_unknown="timeout",
            )
        )
        exit_code, record, candidate = self.run_main(engine)

        self.assertEqual(exit_code, proposer.EXIT_TIMEOUT)
        self.assertNotEqual(exit_code, 0)
        self.assertEqual(record["status"], proposer.TIMEOUT)
        self.assertFalse(candidate.exists())

    def test_solver_error_is_explicit_and_nonzero(self):
        engine = FakeEngine(
            self.make_outcome(
                proposer.ERROR,
                error="optional solver unavailable",
            )
        )
        exit_code, record, candidate = self.run_main(engine)

        self.assertEqual(exit_code, proposer.EXIT_ERROR)
        self.assertNotEqual(exit_code, 0)
        self.assertEqual(record["status"], proposer.ERROR)
        self.assertEqual(record["error"], "optional solver unavailable")
        self.assertFalse(candidate.exists())

    def test_lean_rejection_is_comparison_mismatch_and_nonzero(self):
        engine = FakeEngine(
            self.make_outcome("sat", candidate=candidate_result())
        )
        exit_code, record, candidate = self.run_main(
            engine,
            checker_runner=rejected_checker,
        )

        self.assertEqual(exit_code, proposer.EXIT_COMPARISON_MISMATCH)
        self.assertNotEqual(exit_code, 0)
        self.assertEqual(record["status"], proposer.ERROR)
        self.assertEqual(record["comparison"]["status"], "mismatch")
        self.assertFalse(candidate.exists())

    def test_checker_timeout_is_explicit_and_nonzero(self):
        engine = FakeEngine(
            self.make_outcome("sat", candidate=candidate_result())
        )

        def timed_out(*_args):
            return proposer.CheckerOutcome(
                exit_code=None,
                error="Lean checker timed out",
                timed_out=True,
            )

        exit_code, record, candidate = self.run_main(
            engine,
            checker_runner=timed_out,
        )
        self.assertEqual(exit_code, proposer.EXIT_TIMEOUT)
        self.assertEqual(record["status"], proposer.TIMEOUT)
        self.assertFalse(candidate.exists())


if __name__ == "__main__":
    unittest.main()

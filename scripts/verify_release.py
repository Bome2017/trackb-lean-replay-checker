#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed release gate for the narrow TrackB Lean package."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MODULES = {
    "AxiomCheck.lean",
    "FixtureMain.lean",
    "GuardedExamples.lean",
    "Main.lean",
    "SafetyMain.lean",
    "SearchMain.lean",
    "TrackBReplay.lean",
    "TrackBResults.lean",
    "TrackBSafety.lean",
    "TrackBSearch.lean",
    "TrackBSemantics.lean",
}
EXPECTED_AXIOM_THEOREMS = {
    "TrackBReplay.KernelState.toBoolMap_keys",
    "TrackBReplay.KernelState.toKernelState_toBoolMap",
    "TrackBReplay.Kernel.transitionB_iff",
    "TrackBReplay.SafetyCertificate.check_iff",
    "TrackBReplay.SafetyCertificate.check_sound",
    "TrackBReplay.SemanticTrace.validB_iff",
    "TrackBReplay.SemanticTrace.states_ne_nil",
    "TrackBReplay.SemanticTrace.priorSafeB_iff",
    "TrackBReplay.boundedCounterexampleB_iff",
    "TrackBReplay.Kernel.mem_stateLayer_iff",
    "TrackBReplay.SemanticTrace.Valid.reachableAt",
    "TrackBReplay.Kernel.stateLayer_mem_stateLayers_of_le",
    "TrackBReplay.Kernel.mem_coveredStates_of_reachableAt",
    "TrackBReplay.findBadState?_none_no_boundedCounterexample",
    "TrackBReplay.SemanticTrace.valid_mem_traceLayer",
    "TrackBReplay.SemanticTrace.valid_mem_tracesUpTo",
    "TrackBReplay.findBoundedCounterexample?_sound",
    "TrackBReplay.findBoundedCounterexample?_complete",
    "TrackBReplay.findBoundedCounterexample?_none_iff",
    "TrackBReplay.reachabilityEngine_unsafe_sound",
    "TrackBReplay.reachabilityEngine_bounded_complete",
    "TrackBReplay.reachabilityEngine_not_unsafe_complete",
    "TrackBReplay.reachabilityEngine_safeWithinBound_sound",
    "TrackBReplay.reachabilityEngine_globallySafe_no_boundedCounterexample",
    "TrackBReplay.reachabilityEngine_globallySafe_sound",
    "TrackBReplay.check_iff",
    "TrackBReplay.check_sound",
    "TrackBReplay.check_complete",
    "TrackBReplay.GlobalSafetyResult.check_sound",
    "TrackBReplay.generated_global_result_is_globally_safe",
    "TrackBReplay.checked_unsafe_endToEnd",
    "TrackBReplay.checked_bounded_safe_endToEnd",
    "TrackBReplay.checked_global_endToEnd",
    "TrackBReplay.GuardedExamples.globallySafe_of_certificate",
    (
        "TrackBReplay.GuardedExamples."
        "invalidWorkflow_not_globally_safe"
    ),
    "TrackBReplay.GuardedExamples.emailFixture_compile",
    "TrackBReplay.GuardedExamples.emailCertificate_check",
    (
        "TrackBReplay.GuardedExamples."
        "email_requires_approval_globally_safe"
    ),
    "TrackBReplay.GuardedExamples.deleteFixture_compile",
    "TrackBReplay.GuardedExamples.deleteCertificate_check",
    (
        "TrackBReplay.GuardedExamples."
        "delete_requires_confirmation_globally_safe"
    ),
    "TrackBReplay.GuardedExamples.vendorPaymentFixture_compile",
    "TrackBReplay.GuardedExamples.vendorPaymentCertificate_check",
    (
        "TrackBReplay.GuardedExamples."
        "vendor_payment_guarded_globally_safe"
    ),
}
ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}
PROOF_DECLARATION = re.compile(
    r"^[ \t]*(?:@\[[^\n]*\][ \t]*)*"
    r"(?:(?:private|protected|local)[ \t]+)*"
    r"(?:theorem|lemma)[ \t]+([A-Za-z_][A-Za-z0-9_?'.]*)",
    re.MULTILINE,
)
PROHIBITED_LEAN_TOKENS = re.compile(
    r"\b(sorry|admit|axiom|unsafe|native_decide)\b"
)
EXPECTED_FIXTURE_SHA256 = {
    (
        "fixtures/guarded/agent_email_requires_approval/workflow.json"
    ): "88fc0c4eb52487cf00a8dda32fb9dc14473b44ab694919ca82cbdf50097dabf9",
    (
        "fixtures/guarded/agent_delete_requires_confirmation/workflow.json"
    ): "2c1adc8dfaac1ae2b16bf53115305024bdcee9b2ed9900927c4f557fa0836acd",
    (
        "fixtures/guarded/agent_vendor_payment_guarded/workflow.json"
    ): "39a0ebcd1de6ba8ff673a98414b65ee344a22d2089a997e32822f6a673f4f740",
}
EXPECTED_TEST_COUNT = 19


def run(command: list[str], *, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    output = completed.stdout + completed.stderr
    if completed.returncode != 0:
        sys.stderr.write(output)
        raise SystemExit(
            f"release gate command failed ({completed.returncode}): {' '.join(command)}"
        )
    return output


def verify_source_boundary() -> None:
    modules = {path.name for path in ROOT.glob("*.lean")}
    if modules != EXPECTED_MODULES:
        raise SystemExit(
            f"Lean source boundary changed: expected {sorted(EXPECTED_MODULES)}, "
            f"found {sorted(modules)}"
        )

    for path in ROOT.rglob("*"):
        if ".lake" in path.parts:
            continue
        if path.is_symlink():
            raise SystemExit(f"source-tree symlink is not allowed: {path}")

    manifest = json.loads((ROOT / "lake-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("name") != "trackb_lean_replay_checker":
        raise SystemExit("Lake manifest root name mismatch")
    if manifest.get("packages") != []:
        raise SystemExit("unexpected Lake dependency; update third-party review first")

    lakefile = (ROOT / "lakefile.toml").read_text(encoding="utf-8")
    if 'version = "0.2.1"' not in lakefile:
        raise SystemExit("Lake package version is not frozen at 0.2.1")

    observed_theorem_leaves: Counter[str] = Counter()
    for path in ROOT.glob("*.lean"):
        if path.name == "AxiomCheck.lean":
            continue
        text = path.read_text(encoding="utf-8")
        observed_theorem_leaves.update(
            declaration.rsplit(".", 1)[-1]
            for declaration in PROOF_DECLARATION.findall(text)
        )
    expected_theorem_leaves = Counter(
        theorem.rsplit(".", 1)[-1]
        for theorem in EXPECTED_AXIOM_THEOREMS
    )
    if observed_theorem_leaves != expected_theorem_leaves:
        raise SystemExit(
            "explicit theorem/lemma inventory differs from the complete "
            "axiom gate: "
            f"expected {sorted(expected_theorem_leaves.elements())}, "
            f"found {sorted(observed_theorem_leaves.elements())}"
        )

    for path in ROOT.glob("*.lean"):
        text = path.read_text(encoding="utf-8")
        match = PROHIBITED_LEAN_TOKENS.search(text)
        if match:
            line = text.count("\n", 0, match.start()) + 1
            raise SystemExit(
                f"prohibited Lean token {match.group(1)!r} in {path.name}:{line}"
            )

    for relative, expected in EXPECTED_FIXTURE_SHA256.items():
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f"required guarded fixture is missing: {relative}")
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
        if observed != expected:
            raise SystemExit(
                f"guarded fixture digest mismatch for {relative}: "
                f"expected {expected}, found {observed}"
            )


def verify_guarded_fixture_correspondence() -> None:
    checker = ROOT / ".lake" / "build" / "bin" / "trackb-guarded-fixture-check"
    for relative in EXPECTED_FIXTURE_SHA256:
        output = run([str(checker), str(ROOT / relative)])
        if "model=exact" not in output:
            raise SystemExit(
                f"guarded fixture correspondence marker missing: {relative}"
            )


def verify_axioms() -> None:
    output = run(["lake", "env", "lean", "AxiomCheck.lean"])
    observed: dict[str, set[str]] = {}
    pattern = re.compile(r"'([^']+)' depends on axioms: \[([^\]]*)\]")
    for theorem, raw_axioms in pattern.findall(output):
        observed[theorem] = {
            item.strip() for item in raw_axioms.split(",") if item.strip()
        }

    if set(observed) != EXPECTED_AXIOM_THEOREMS:
        raise SystemExit(
            "axiom report theorem set mismatch: "
            f"expected {sorted(EXPECTED_AXIOM_THEOREMS)}, found {sorted(observed)}"
        )

    unexpected = {
        theorem: sorted(axioms - ALLOWED_AXIOMS)
        for theorem, axioms in observed.items()
        if axioms - ALLOWED_AXIOMS
    }
    if unexpected:
        raise SystemExit(f"unexpected theorem axioms: {unexpected}")

    print(output.strip())


def main() -> int:
    verify_source_boundary()
    print(run(["lake", "build"]).strip())
    verify_guarded_fixture_correspondence()

    test_env = dict(os.environ)
    test_env["PYTHONDONTWRITEBYTECODE"] = "1"
    test_output = run(
        ["python3", "-m", "unittest", "discover", "-s", "tests", "-v"],
        env=test_env,
    )
    test_counts = re.findall(
        r"^Ran ([0-9]+) tests? in ",
        test_output,
        re.MULTILINE,
    )
    if len(test_counts) != 1 or int(test_counts[0]) != EXPECTED_TEST_COUNT:
        observed = "missing-or-ambiguous" if len(test_counts) != 1 else test_counts[0]
        raise SystemExit(
            "release test inventory changed: "
            f"expected {EXPECTED_TEST_COUNT}, observed {observed}"
        )
    if len(re.findall(r"^OK$", test_output, re.MULTILINE)) != 1:
        raise SystemExit(
            "release tests must end in exactly one plain OK status "
            "without skips or expected/unexpected-success qualifications"
        )
    print(test_output.strip())
    verify_axioms()
    print("RELEASE_GATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

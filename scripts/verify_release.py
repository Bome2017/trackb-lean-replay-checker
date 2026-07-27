#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed release gate for the narrow TrackB Lean package."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MODULES = {"TrackBReplay.lean", "AxiomCheck.lean", "Main.lean"}
EXPECTED_AXIOM_THEOREMS = {
    "TrackBReplay.check_iff",
    "TrackBReplay.check_sound",
    "TrackBReplay.check_complete",
}
ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}
PROHIBITED_LEAN_TOKENS = re.compile(r"\b(sorry|admit|axiom|unsafe)\b")


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

    for path in ROOT.glob("*.lean"):
        text = path.read_text(encoding="utf-8")
        match = PROHIBITED_LEAN_TOKENS.search(text)
        if match:
            line = text.count("\n", 0, match.start()) + 1
            raise SystemExit(
                f"prohibited Lean token {match.group(1)!r} in {path.name}:{line}"
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

    test_env = dict(os.environ)
    test_env["PYTHONDONTWRITEBYTECODE"] = "1"
    print(
        run(
            ["python3", "-m", "unittest", "discover", "-s", "tests", "-v"],
            env=test_env,
        ).strip()
    )
    verify_axioms()
    print("RELEASE_GATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

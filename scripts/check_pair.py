#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
# SPDX-License-Identifier: Apache-2.0
"""Bind exact TrackB inputs to a Lean counterexample-checking receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKER = PACKAGE_ROOT / ".lake" / "build" / "bin" / "trackb-replay-check"
TOOLCHAIN = (PACKAGE_ROOT / "lean-toolchain").read_text(encoding="utf-8").strip()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Lean TrackB v0.1 counterexample checker on immutable copies "
            "and write a SHA-256-bound JSON receipt."
        )
    )
    parser.add_argument("workflow", type=Path)
    parser.add_argument("result", type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--checker", type=Path, default=DEFAULT_CHECKER)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workflow_bytes = args.workflow.read_bytes()
    result_bytes = args.result.read_bytes()
    checker_bytes = args.checker.read_bytes()

    with tempfile.TemporaryDirectory(prefix="trackb-lean-inputs-") as temp_name:
        temp_root = Path(temp_name)
        workflow_copy = temp_root / "workflow.json"
        result_copy = temp_root / "result.json"
        workflow_copy.write_bytes(workflow_bytes)
        result_copy.write_bytes(result_bytes)

        if workflow_copy.read_bytes() != workflow_bytes:
            raise RuntimeError("workflow immutable-copy check failed")
        if result_copy.read_bytes() != result_bytes:
            raise RuntimeError("result immutable-copy check failed")

        completed = subprocess.run(
            [str(args.checker), str(workflow_copy), str(result_copy)],
            check=False,
            capture_output=True,
            text=True,
        )

    receipt = {
        "receipt_schema": "trackb-lean-replay-receipt/0.1",
        "verdict": "PASS" if completed.returncode == 0 else "FAIL",
        "checker_exit_code": completed.returncode,
        "claim": (
            "The exact workflow/result pair contains a valid TrackB v0.1 "
            "counterexample trace under the parsed bounded Boolean semantics."
            if completed.returncode == 0
            else "The exact workflow/result pair was not certified."
        ),
        "nonclaims": [
            "No global safety claim.",
            "No SAFE_WITHIN_BOUND proof.",
            "No proof that the Python BFS or Z3 search is complete or globally first.",
            "No production certification.",
        ],
        "inputs": {
            "workflow": {
                "name": args.workflow.name,
                "sha256": sha256(workflow_bytes),
                "bytes": len(workflow_bytes),
            },
            "result": {
                "name": args.result.name,
                "sha256": sha256(result_bytes),
                "bytes": len(result_bytes),
            },
        },
        "checker": {
            "sha256": sha256(checker_bytes),
            "bytes": len(checker_bytes),
            "lean_toolchain": TOOLCHAIN,
        },
        "checker_stdout": completed.stdout.strip(),
        "checker_stderr": completed.stderr.strip(),
        "trusted_boundary": [
            "Lean compiler, kernel, code generator, runtime, and JSON parser",
            "Operating-system file I/O and process execution",
            "This Python wrapper for SHA-256 calculation and immutable-copy launch",
        ],
    }

    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())

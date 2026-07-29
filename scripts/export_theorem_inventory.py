#!/usr/bin/env python3
"""Run the Lean environment inventory and hash its exact JSON bytes.

This is deliberately only an invocation and receipt wrapper.  The authoritative
declaration discovery, ownership filtering, authorship classification, and
axiom collection all happen in TheoremInventory.lean.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=REPOSITORY_ROOT,
        help="Lake project whose compiled modules will be loaded",
    )
    parser.add_argument(
        "--tool",
        type=Path,
        default=REPOSITORY_ROOT / "TheoremInventory.lean",
        help="absolute or project-relative path to the Lean inventory source",
    )
    parser.add_argument("--import", dest="imports", action="append", default=[])
    parser.add_argument(
        "--owned-module", dest="owned_modules", action="append", default=[]
    )
    parser.add_argument(
        "--allowed-axiom", dest="allowed_axioms", action="append", default=[]
    )
    parser.add_argument(
        "--classification",
        type=Path,
        default=REPOSITORY_ROOT / "docs" / "theorem_inventory_classification.json",
    )
    parser.add_argument(
        "--no-classification",
        action="store_true",
        help="use the Lean tool's intentional default classification policy",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / "validation" / "theorem_inventory.json",
    )
    parser.add_argument(
        "--sha256-output",
        type=Path,
        default=REPOSITORY_ROOT / "validation" / "theorem_inventory.sha256",
    )
    return parser.parse_args()


def absolute_from(base: Path, path: Path) -> Path:
    return path if path.is_absolute() else base / path


def atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    tool = absolute_from(project_root, args.tool).resolve()
    output = absolute_from(project_root, args.output).resolve()
    sha256_output = absolute_from(project_root, args.sha256_output).resolve()
    if output == sha256_output:
        print(
            "inventory JSON and SHA-256 outputs must be distinct",
            file=sys.stderr,
        )
        return 2

    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        dir=output.parent,
    )
    os.close(descriptor)
    temporary_output = Path(temporary_name)

    command = ["lake", "env", "lean", "--run", str(tool)]
    for module_name in args.imports:
        command.extend(["--import", module_name])
    for module_name in args.owned_modules:
        command.extend(["--owned-module", module_name])
    for axiom_name in args.allowed_axioms:
        command.extend(["--allowed-axiom", axiom_name])
    if not args.no_classification:
        classification = absolute_from(project_root, args.classification).resolve()
        command.extend(["--classification", str(classification)])
    command.extend(["--output", str(temporary_output)])

    try:
        completed = subprocess.run(command, cwd=project_root, check=False)
        if completed.returncode != 0:
            return completed.returncode

        try:
            raw_inventory = temporary_output.read_bytes()
            payload = json.loads(raw_inventory.decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            print(f"invalid theorem inventory output: {error}", file=sys.stderr)
            return 2

        if payload.get("schemaVersion") != "trackb-theorem-inventory-v1":
            print("unexpected theorem inventory schema", file=sys.stderr)
            return 2
        if payload.get("checks", {}).get("result") != "PASS":
            print(
                "theorem inventory reported a non-PASS result",
                file=sys.stderr,
            )
            return 1

        digest = hashlib.sha256(raw_inventory).hexdigest()
        atomic_write(output, raw_inventory)
        atomic_write(
            sha256_output,
            f"{digest}  {output.name}\n".encode("utf-8"),
        )
        print(
            f"THEOREM_INVENTORY=PASS "
            f"theorems={payload['theoremCount']} "
            f"authored={payload['authoredTheoremCount']} "
            f"generated={payload['generatedTheoremCount']} "
            f"sha256={digest}"
        )
        return 0
    finally:
        try:
            temporary_output.unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

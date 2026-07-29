#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
# SPDX-License-Identifier: Apache-2.0
"""Assemble and finalize an immutable local TrackB release package.

The ``prepare`` command consumes already-produced release-gate evidence.  It
does not run the gate, build an archive, create a commit or tag, contact a
remote, or push anything.  It verifies the supplied evidence against one clean
Git identity and atomically installs a package outside the repository.

The ``finalize`` command is deliberately narrower: it reads an existing local
annotated tag, records the tag object and peeled identity in
``validation/RELEASE_MANIFEST.json``, and regenerates ``SHA256SUMS``.  The
release receipt is byte-checked before and after and is never rewritten.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERSION = "v0.2.1"
LOCAL_CANDIDATE_TAG = "v0.2.1-local-release-candidate"
GATE_SCHEMA = "trackb-release-gate-summary-v1"
RECEIPT_SCHEMA = "trackb-release-receipt-v1"
MANIFEST_SCHEMA = "trackb-release-manifest-v1"
INVENTORY_SCHEMA_PREFIX = "trackb-theorem-inventory-v"

RECEIPT_RELATIVE = PurePosixPath(
    "validation/trackb-v0.2.1-release-receipt.json"
)
RECEIPT_SHA_RELATIVE = PurePosixPath(
    "validation/trackb-v0.2.1-release-receipt.sha256"
)
CHECKSUMS_RELATIVE = PurePosixPath("validation/SHA256SUMS")
INVENTORY_SHA_RELATIVE = PurePosixPath(
    "validation/theorem_inventory.sha256"
)
RELEASE_MANIFEST_RELATIVE = PurePosixPath(
    "validation/RELEASE_MANIFEST.json"
)
GATE_SUMMARY_RELATIVE = PurePosixPath(
    "validation/release-gate-summary.json"
)
SOURCE_ONLY_GATE_SUMMARY_RELATIVE = PurePosixPath(
    "validation/source-only-release-gate-summary.json"
)

RESERVED_VALIDATION_PATHS = {
    RECEIPT_RELATIVE.as_posix(),
    RECEIPT_SHA_RELATIVE.as_posix(),
    CHECKSUMS_RELATIVE.as_posix(),
    INVENTORY_SHA_RELATIVE.as_posix(),
    RELEASE_MANIFEST_RELATIVE.as_posix(),
    GATE_SUMMARY_RELATIVE.as_posix(),
    SOURCE_ONLY_GATE_SUMMARY_RELATIVE.as_posix(),
}
REQUIRED_CHECKS = (
    "build",
    "tests",
    "hostile_theorem_inventory",
    "bounded_output_regression",
    "semantic_theorem",
    "metadata_theorem",
)
REQUIRED_CLAIM_BOUNDARIES = {
    "UNSAFE",
    "SAFE_WITHIN_BOUND",
    "GLOBALLY_SAFE",
}
HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
GIT_OBJECT = re.compile(r"^[0-9a-f]{40,64}$")
WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
LOCAL_ABSOLUTE_IN_TEXT = re.compile(
    r"(?<![A-Za-z0-9])/(?:Users|home|private/tmp|var/folders)/"
)


class ReleasePreparationError(Exception):
    """A fail-closed release preparation error."""


def fail(message: str) -> None:
    raise ReleasePreparationError(message)


def command_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for key in list(environment):
        if key.startswith("GIT_"):
            environment.pop(key, None)
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONHASHSEED"] = "0"
    return environment


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_bytes(path: Path, label: str) -> bytes:
    if path.is_symlink():
        fail(f"{label} must not be a symlink: {path}")
    if not path.is_file():
        fail(f"{label} is not a regular file: {path}")
    return path.read_bytes()


def read_json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        fail(f"{label} is not valid UTF-8 JSON: {error}")
    if not isinstance(value, dict):
        fail(f"{label} must be a JSON object")
    return value


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{label} must be a JSON object")
    return value


def require_array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        fail(f"{label} must be a JSON array")
    return value


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        fail(f"{label} must be a nonempty string")
    return value


def require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        fail(f"{label} must be a Boolean")
    return value


def require_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        fail(f"{label} must be an integer")
    return value


def require_sha256(value: Any, label: str) -> str:
    digest = require_string(value, label)
    if not HEX_DIGEST.fullmatch(digest):
        fail(f"{label} must be a lowercase SHA-256 digest")
    return digest


def require_git_object(value: Any, label: str) -> str:
    object_name = require_string(value, label)
    if not GIT_OBJECT.fullmatch(object_name):
        fail(f"{label} must be a full lowercase Git object id")
    return object_name


def require_pass(value: Any, label: str) -> None:
    if value != "PASS":
        fail(f"{label} must be exactly PASS")


def require_timestamp(value: Any, label: str) -> tuple[str, datetime]:
    text = require_string(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        fail(f"{label} is not an ISO-8601 timestamp: {error}")
    if parsed.tzinfo is None:
        fail(f"{label} must include an explicit timezone")
    return text, parsed


def safe_relative_path(
    value: Any,
    label: str,
    *,
    required_parent: str | None = None,
    basename_only: bool = False,
) -> PurePosixPath:
    text = require_string(value, label)
    if "\\" in text or "\x00" in text or "\n" in text or "\r" in text:
        fail(f"{label} is not a safe POSIX relative path")
    path = PurePosixPath(text)
    if path.is_absolute() or text in {".", ".."} or ".." in path.parts:
        fail(f"{label} is not a safe relative path")
    if path.as_posix() != text:
        fail(f"{label} must be a normalized POSIX relative path")
    if basename_only and len(path.parts) != 1:
        fail(f"{label} must be a basename")
    if required_parent is not None:
        if len(path.parts) < 2 or path.parts[0] != required_parent:
            fail(f"{label} must be below {required_parent}/")
    return path


def ensure_public_safe_json(value: Any, label: str = "JSON") -> None:
    """Reject host-local absolute paths from package-facing JSON."""

    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                fail(f"{label} contains a non-string object key")
            ensure_public_safe_json(nested, f"{label}.{key}")
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            ensure_public_safe_json(nested, f"{label}[{index}]")
        return
    if not isinstance(value, str):
        return
    if (
        value.startswith(("/", "~/", "file://"))
        or WINDOWS_ABSOLUTE.match(value)
        or LOCAL_ABSOLUTE_IN_TEXT.search(value)
    ):
        fail(f"{label} contains a host-local absolute path")


def absolute_without_symlink(path: Path, label: str) -> Path:
    absolute = Path(os.path.abspath(os.fspath(path.expanduser())))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if current.exists() and current.is_symlink():
            fail(f"{label} traverses a symlink: {current}")
    return absolute


def assert_outside_repository(path: Path, repository: Path, label: str) -> None:
    if path == repository or repository in path.parents:
        fail(f"{label} must be outside the repository")


def run_git(
    repository: Path,
    arguments: list[str],
    *,
    text: bool = True,
) -> str | bytes:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        env=command_environment(),
        check=False,
        capture_output=True,
        text=text,
    )
    if completed.returncode != 0:
        stderr = completed.stderr if text else completed.stderr.decode(
            "utf-8", errors="replace"
        )
        fail(
            f"Git command failed ({' '.join(arguments)}): "
            f"{stderr.strip()}"
        )
    return completed.stdout


def current_repository_fingerprint(
    repository: Path,
) -> dict[str, Any]:
    status_raw = run_git(
        repository,
        ["status", "--porcelain=v1", "--untracked-files=all"],
        text=False,
    )
    index_raw = run_git(
        repository, ["ls-files", "-s", "-z"], text=False
    )
    assert isinstance(status_raw, bytes)
    assert isinstance(index_raw, bytes)
    source_records: list[dict[str, Any]] = []
    for record in index_raw.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, _object_id, stage = metadata.decode("ascii").split(" ")
        if stage != "0" or mode not in {"100644", "100755"}:
            fail("repository index contains an unsupported release entry")
        path_text = raw_path.decode("utf-8")
        path = repository / path_text
        raw = read_bytes(path, f"tracked source {path_text}")
        actual_mode = (
            "0755" if path.stat().st_mode & stat.S_IXUSR else "0644"
        )
        expected_mode = "0755" if mode == "100755" else "0644"
        if actual_mode != expected_mode:
            fail(f"tracked source mode differs from index: {path_text}")
        source_records.append(
            {
                "mode": actual_mode,
                "path": path_text,
                "sha256": sha256_bytes(raw),
                "size": len(raw),
            }
        )
    source_records.sort(key=lambda entry: entry["path"])
    return {
        "branch": str(
            run_git(repository, ["branch", "--show-current"])
        ).strip(),
        "clean": status_raw == b"",
        "commit": str(run_git(repository, ["rev-parse", "HEAD"])).strip(),
        "index_sha256": sha256_bytes(index_raw),
        "source_sha256": sha256_bytes(
            canonical_json_bytes(source_records)
        ),
        "status_sha256": sha256_bytes(status_raw),
        "tree": str(
            run_git(repository, ["rev-parse", "HEAD^{tree}"])
        ).strip(),
    }


def verify_repository(
    repository_argument: Path,
    summary_repository: dict[str, Any],
) -> tuple[Path, dict[str, str], dict[str, Any], dict[str, Any]]:
    expected_repository_keys = {
        "after_fingerprint",
        "before_fingerprint",
        "branch",
        "clean",
        "commit",
        "mode",
        "no_local_alternates",
        "remote",
        "tree",
    }
    if set(summary_repository) != expected_repository_keys:
        fail("Git-mode repository evidence schema changed")
    if summary_repository.get("mode") != "git":
        fail("repository evidence must be from the Git-mode release gate")
    if require_bool(
        summary_repository.get("no_local_alternates"),
        "repository.no_local_alternates",
    ) is not True:
        fail("repository.no_local_alternates must be true")
    repository = absolute_without_symlink(
        repository_argument, "repository"
    )
    if not repository.is_dir():
        fail(f"repository is not a directory: {repository}")
    top_level = Path(
        str(run_git(repository, ["rev-parse", "--show-toplevel"])).strip()
    ).resolve()
    if top_level != repository.resolve():
        fail(
            "repository argument must be the exact Git top level: "
            f"{top_level}"
        )

    branch = require_string(
        summary_repository.get("branch"), "repository.branch"
    )
    commit = require_git_object(
        summary_repository.get("commit"), "repository.commit"
    )
    tree = require_git_object(
        summary_repository.get("tree"), "repository.tree"
    )
    remote = require_string(
        summary_repository.get("remote"), "repository.remote"
    )
    ensure_public_safe_json(remote, "repository.remote")
    if require_bool(
        summary_repository.get("clean"), "repository.clean"
    ) is not True:
        fail("repository.clean must be true")

    observed_status = str(
        run_git(
            repository,
            ["status", "--porcelain=v1", "--untracked-files=all"],
        )
    )
    if observed_status:
        fail("repository worktree is not exactly clean")
    observed_branch = str(
        run_git(repository, ["symbolic-ref", "--short", "HEAD"])
    ).strip()
    observed_commit = str(
        run_git(repository, ["rev-parse", "HEAD"])
    ).strip()
    observed_tree = str(
        run_git(repository, ["rev-parse", "HEAD^{tree}"])
    ).strip()
    observed_remote = str(
        run_git(repository, ["remote", "get-url", "origin"])
    ).strip()
    expected = {
        "branch": branch,
        "commit": commit,
        "tree": tree,
        "remote": remote,
    }
    observed = {
        "branch": observed_branch,
        "commit": observed_commit,
        "tree": observed_tree,
        "remote": observed_remote,
    }
    if observed != expected:
        fail(
            "clean Git identity differs from gate summary: "
            f"expected {expected}, observed {observed}"
        )

    before = require_object(
        summary_repository.get("before_fingerprint"),
        "repository.before_fingerprint",
    )
    after = require_object(
        summary_repository.get("after_fingerprint"),
        "repository.after_fingerprint",
    )
    ensure_public_safe_json(before, "repository.before_fingerprint")
    ensure_public_safe_json(after, "repository.after_fingerprint")
    if before != after:
        fail("before and after worktree fingerprints differ")
    expected_fingerprint_keys = {
        "branch",
        "clean",
        "commit",
        "index_sha256",
        "source_sha256",
        "status_sha256",
        "tree",
    }
    if set(before) != expected_fingerprint_keys:
        fail("repository fingerprint schema changed")
    for key in ("index_sha256", "source_sha256", "status_sha256"):
        require_sha256(before.get(key), f"repository fingerprint {key}")
    if (
        before.get("branch") != branch
        or before.get("commit") != commit
        or before.get("tree") != tree
        or before.get("clean") is not True
    ):
        fail("repository fingerprint identity fields are inconsistent")
    current_fingerprint = current_repository_fingerprint(repository)
    if current_fingerprint != before:
        fail("current repository fingerprint differs from gate evidence")
    return repository, expected, before, after


def git_tracked_bytes(
    repository: Path,
    commit: str,
    relative: PurePosixPath,
    label: str,
) -> bytes:
    relative_text = relative.as_posix()
    run_git(
        repository,
        ["ls-files", "--error-unmatch", "--", relative_text],
    )
    committed = run_git(
        repository,
        ["cat-file", "blob", f"{commit}:{relative_text}"],
        text=False,
    )
    assert isinstance(committed, bytes)
    worktree_path = repository / relative_text
    current = read_bytes(worktree_path, label)
    if current != committed:
        fail(f"{label} differs from the exact committed blob: {relative_text}")
    return current


def tracked_root_lean_modules(
    repository: Path, commit: str
) -> list[str]:
    output = run_git(
        repository, ["ls-tree", "-r", "--name-only", "-z", commit], text=False
    )
    assert isinstance(output, bytes)
    paths = [
        item.decode("utf-8")
        for item in output.split(b"\0")
        if item
    ]
    return sorted(
        path
        for path in paths
        if "/" not in path and path.endswith(".lean")
    )


def verify_modules(
    repository: Path,
    commit: str,
    value: Any,
) -> list[dict[str, Any]]:
    modules = require_array(value, "modules")
    if not modules:
        fail("modules must not be empty")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(modules):
        entry = require_object(item, f"modules[{index}]")
        relative = safe_relative_path(
            entry.get("path"), f"modules[{index}].path"
        )
        if len(relative.parts) != 1 or relative.suffix != ".lean":
            fail(f"modules[{index}].path must name a root Lean module")
        expected_digest = require_sha256(
            entry.get("sha256"), f"modules[{index}].sha256"
        )
        raw = git_tracked_bytes(
            repository,
            commit,
            relative,
            f"module {relative.as_posix()}",
        )
        observed_digest = sha256_bytes(raw)
        if observed_digest != expected_digest:
            fail(
                f"module digest mismatch for {relative}: "
                f"expected {expected_digest}, found {observed_digest}"
            )
        normalized.append(
            {"path": relative.as_posix(), "sha256": observed_digest}
        )
    names = [entry["path"] for entry in normalized]
    if names != sorted(set(names)):
        fail("modules must be sorted by unique path")
    tracked_modules = tracked_root_lean_modules(repository, commit)
    if names != tracked_modules:
        fail(
            "module list is not the complete tracked root Lean surface: "
            f"expected {tracked_modules}, found {names}"
        )
    return normalized


def verify_validation_reports(
    repository: Path,
    commit: str,
    value: Any,
) -> tuple[list[dict[str, str]], dict[str, bytes]]:
    reports = require_array(value, "validation_reports")
    if not reports:
        fail("validation_reports must not be empty")
    normalized: list[dict[str, str]] = []
    raw_by_path: dict[str, bytes] = {}
    for index, item in enumerate(reports):
        entry = require_object(item, f"validation_reports[{index}]")
        relative = safe_relative_path(
            entry.get("path"),
            f"validation_reports[{index}].path",
            required_parent="validation",
        )
        relative_text = relative.as_posix()
        if relative.suffix != ".json":
            fail(f"validation report must be JSON: {relative_text}")
        if relative_text in RESERVED_VALIDATION_PATHS:
            fail(f"validation report collides with generated asset: {relative_text}")
        expected_digest = require_sha256(
            entry.get("sha256"),
            f"validation_reports[{index}].sha256",
        )
        raw = git_tracked_bytes(
            repository,
            commit,
            relative,
            f"validation report {relative_text}",
        )
        observed_digest = sha256_bytes(raw)
        if observed_digest != expected_digest:
            fail(
                f"validation report digest mismatch for {relative_text}: "
                f"expected {expected_digest}, found {observed_digest}"
            )
        parsed = read_json_bytes(raw, f"validation report {relative_text}")
        ensure_public_safe_json(parsed, f"validation report {relative_text}")
        report_result = parsed.get("result")
        report_checks = parsed.get("checks")
        checks_result = (
            report_checks.get("result")
            if isinstance(report_checks, dict)
            else None
        )
        if report_result != "PASS" and checks_result != "PASS":
            fail(
                "tracked validation report has no top-level PASS result: "
                f"{relative_text}"
            )
        normalized.append(
            {"path": relative_text, "sha256": observed_digest}
        )
        raw_by_path[relative_text] = raw
    names = [entry["path"] for entry in normalized]
    if names != sorted(set(names)):
        fail("validation_reports must be sorted by unique path")
    return normalized, raw_by_path


def verify_inventory(
    inventory_summary_value: Any,
    report_bytes: dict[str, bytes],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary = require_object(
        inventory_summary_value, "theorem_inventory"
    )
    relative = safe_relative_path(
        summary.get("path"),
        "theorem_inventory.path",
        required_parent="validation",
    )
    relative_text = relative.as_posix()
    if relative_text not in report_bytes:
        fail("theorem inventory must be one of validation_reports")
    raw = report_bytes[relative_text]
    observed_digest = sha256_bytes(raw)
    expected_digest = require_sha256(
        summary.get("sha256"), "theorem_inventory.sha256"
    )
    if observed_digest != expected_digest:
        fail("theorem inventory hash differs from gate summary")
    inventory = read_json_bytes(raw, "theorem inventory")
    ensure_public_safe_json(inventory, "theorem inventory")
    schema = require_string(
        inventory.get("schemaVersion"), "inventory.schemaVersion"
    )
    if not schema.startswith(INVENTORY_SCHEMA_PREFIX):
        fail(f"unsupported theorem inventory schema: {schema}")
    checks = require_object(inventory.get("checks"), "inventory.checks")
    require_pass(checks.get("result"), "inventory.checks.result")
    if require_bool(
        checks.get("axiomGatePassed"),
        "inventory.checks.axiomGatePassed",
    ) is not True:
        fail("inventory axiom gate did not pass")

    theorem_count = require_integer(
        inventory.get("theoremCount"), "inventory.theoremCount"
    )
    authored_count = require_integer(
        inventory.get("authoredTheoremCount"),
        "inventory.authoredTheoremCount",
    )
    generated_count = require_integer(
        inventory.get("generatedTheoremCount"),
        "inventory.generatedTheoremCount",
    )
    if min(theorem_count, authored_count, generated_count) < 0:
        fail("inventory theorem counts must be nonnegative")
    if authored_count + generated_count != theorem_count:
        fail("inventory authored/generated counts do not sum to theoremCount")

    expected_counts = {
        "theorem_count": theorem_count,
        "authored_theorem_count": authored_count,
        "generated_theorem_count": generated_count,
    }
    for key, observed in expected_counts.items():
        if require_integer(
            summary.get(key), f"theorem_inventory.{key}"
        ) != observed:
            fail(f"theorem_inventory.{key} differs from inventory")

    allowed_axioms_raw = require_array(
        inventory.get("allowedAxioms"), "inventory.allowedAxioms"
    )
    if not all(isinstance(item, str) and item for item in allowed_axioms_raw):
        fail("inventory.allowedAxioms must contain nonempty strings")
    allowed_axioms = list(allowed_axioms_raw)
    if allowed_axioms != sorted(set(allowed_axioms)):
        fail("inventory.allowedAxioms must be sorted and unique")
    summary_allowed = require_array(
        summary.get("allowed_axioms"),
        "theorem_inventory.allowed_axioms",
    )
    if summary_allowed != allowed_axioms:
        fail("gate-summary allowed axioms differ from inventory")

    owned_modules_raw = require_array(
        inventory.get("ownedModules"), "inventory.ownedModules"
    )
    if not all(
        isinstance(module, str) and module for module in owned_modules_raw
    ):
        fail("inventory.ownedModules must contain nonempty strings")
    owned_modules = list(owned_modules_raw)
    if owned_modules != sorted(set(owned_modules)):
        fail("inventory.ownedModules must be sorted and unique")

    entries = require_array(inventory.get("theorems"), "inventory.theorems")
    if len(entries) != theorem_count:
        fail("inventory.theoremCount differs from the theorem array length")

    axiom_results: list[dict[str, Any]] = []
    names: list[str] = []
    counted_authored = 0
    for index, item in enumerate(entries):
        entry = require_object(item, f"inventory.theorems[{index}]")
        name = require_string(
            entry.get("name"), f"inventory.theorems[{index}].name"
        )
        origin = require_string(
            entry.get("originModule"),
            f"inventory.theorems[{index}].originModule",
        )
        if origin not in owned_modules:
            fail(f"inventory theorem has a foreign origin module: {name}")
        authored = require_bool(
            entry.get("authoredDeclaration"),
            f"inventory.theorems[{index}].authoredDeclaration",
        )
        if require_bool(
            entry.get("authored"),
            f"inventory.theorems[{index}].authored",
        ) is not authored:
            fail(
                f"inventory theorem authorship fields differ: {name}"
            )
        classification = require_object(
            entry.get("classification"),
            f"inventory.theorems[{index}].classification",
        )
        if set(classification) != {
            "category",
            "exampleTheorem",
            "externallyCited",
            "internalHelper",
            "publicApi",
        }:
            fail(f"inventory theorem classification shape changed: {name}")
        flags = {
            key: require_bool(
                classification.get(key),
                f"inventory.theorems[{index}].classification.{key}",
            )
            for key in (
                "exampleTheorem",
                "externallyCited",
                "internalHelper",
                "publicApi",
            )
        }
        primary = (
            flags["publicApi"],
            flags["internalHelper"],
            flags["exampleTheorem"],
        )
        if authored:
            if sum(primary) != 1:
                fail(
                    "authored theorem classification is not a partition: "
                    f"{name}"
                )
            expected_category = (
                "internal_helper"
                if flags["internalHelper"]
                else (
                    "example_theorem"
                    if flags["exampleTheorem"]
                    else "public_api"
                )
            )
        else:
            if any(flags.values()):
                fail(
                    "generated theorem has an authored classification: "
                    f"{name}"
                )
            expected_category = "generated"
        if classification.get("category") != expected_category:
            fail(f"inventory theorem category is inconsistent: {name}")
        ensure_public_safe_json(
            classification,
            f"inventory.theorems[{index}].classification",
        )
        provenance = require_object(
            entry.get("environmentProvenance"),
            f"inventory.theorems[{index}].environmentProvenance",
        )
        if set(provenance) != {
            "exactDeclarationRange",
            "generatedProjection",
            "kind",
        }:
            fail(f"inventory theorem provenance shape changed: {name}")
        exact_range = require_bool(
            provenance.get("exactDeclarationRange"),
            f"inventory.theorems[{index}].exactDeclarationRange",
        )
        generated_projection = require_bool(
            provenance.get("generatedProjection"),
            f"inventory.theorems[{index}].generatedProjection",
        )
        if provenance.get("kind") != (
            "authored" if authored else "generated"
        ):
            fail(f"inventory theorem provenance kind differs: {name}")
        if authored and (not exact_range or generated_projection):
            fail(f"authored theorem lacks exact provenance: {name}")
        type_representation = require_string(
            entry.get("typeRepresentation"),
            f"inventory.theorems[{index}].typeRepresentation",
        )
        if entry.get("typeRepresentationFormat") != "Lean.Expr.repr-v1":
            fail(
                "inventory theorem type representation format changed: "
                f"{name}"
            )
        type_digest = sha256_bytes(type_representation.encode("utf-8"))
        axioms_raw = require_array(
            entry.get("transitiveAxioms"),
            f"inventory.theorems[{index}].transitiveAxioms",
        )
        if not all(isinstance(axiom, str) and axiom for axiom in axioms_raw):
            fail(
                f"inventory.theorems[{index}].transitiveAxioms "
                "must contain nonempty strings"
            )
        axioms = list(axioms_raw)
        if axioms != sorted(set(axioms)):
            fail(
                f"inventory theorem axioms must be sorted and unique: {name}"
            )
        forbidden = sorted(set(axioms) - set(allowed_axioms))
        if forbidden:
            fail(f"inventory theorem has forbidden axioms: {name}: {forbidden}")
        names.append(name)
        counted_authored += int(authored)
        axiom_results.append(
            {
                "name": name,
                "origin_module": origin,
                "authored": authored,
                "classification": copy.deepcopy(classification),
                "type_digest": type_digest,
                "transitive_axioms": axioms,
                "result": "PASS",
            }
        )
    if len(names) != len(set(names)):
        fail("inventory theorem names must be unique")
    if counted_authored != authored_count:
        fail("inventory authored theorem flags differ from authoredTheoremCount")

    normalized = {
        "path": relative_text,
        "sha256": observed_digest,
        "schema_version": schema,
        "sha256_path": INVENTORY_SHA_RELATIVE.as_posix(),
        "type_digest_algorithm": "sha256-utf8-Lean.Expr.repr-v1",
        "environment_theorem_count": theorem_count,
        "authored_theorem_count": authored_count,
        "generated_theorem_count": generated_count,
        "allowed_axioms": allowed_axioms,
    }
    return normalized, axiom_results


def verify_checks(value: Any) -> dict[str, Any]:
    checks = require_object(value, "checks")
    for key in REQUIRED_CHECKS:
        check = require_object(checks.get(key), f"checks.{key}")
        require_pass(check.get("result"), f"checks.{key}.result")
    tests = require_object(checks["tests"], "checks.tests")
    if require_integer(tests.get("count"), "checks.tests.count") <= 0:
        fail("checks.tests.count must be positive")
    ensure_public_safe_json(checks, "checks")
    return copy.deepcopy(checks)


def verify_claim_boundaries(value: Any) -> dict[str, str]:
    boundaries = require_object(value, "claim_boundaries")
    if set(boundaries) != REQUIRED_CLAIM_BOUNDARIES:
        fail(
            "claim_boundaries must contain exactly "
            f"{sorted(REQUIRED_CLAIM_BOUNDARIES)}"
        )
    normalized = {
        key: require_string(boundaries[key], f"claim_boundaries.{key}")
        for key in sorted(boundaries)
    }
    ensure_public_safe_json(normalized, "claim_boundaries")
    return normalized


def verify_toolchain(value: Any) -> dict[str, str]:
    toolchain = require_object(value, "toolchain")
    normalized = {
        key: require_string(toolchain.get(key), f"toolchain.{key}")
        for key in ("lean", "lean_commit", "pin", "lake")
    }
    ensure_public_safe_json(normalized, "toolchain")
    return normalized


def verify_archive_manifest(
    raw_archive: bytes,
    raw_manifest: bytes,
) -> dict[str, Any]:
    manifest = read_json_bytes(raw_manifest, "source archive manifest")
    ensure_public_safe_json(manifest, "source archive manifest")
    if (
        manifest.get("schema_version")
        != "trackb-source-archive-manifest-v1"
    ):
        fail("unsupported source archive manifest schema")
    prefix = safe_relative_path(
        manifest.get("archive_prefix"),
        "source archive manifest archive_prefix",
    )
    if len(prefix.parts) != 1:
        fail("source archive prefix must be one path component")
    files = require_array(manifest.get("files"), "archive manifest files")
    if require_integer(
        manifest.get("file_count"), "archive manifest file_count"
    ) != len(files):
        fail("archive manifest file_count differs from files length")

    expected: list[dict[str, Any]] = []
    for index, item in enumerate(files):
        entry = require_object(item, f"archive manifest files[{index}]")
        relative = safe_relative_path(
            entry.get("path"), f"archive manifest files[{index}].path"
        )
        mode_text = require_string(
            entry.get("mode"), f"archive manifest files[{index}].mode"
        )
        if mode_text not in {"0644", "0755"}:
            fail("archive manifest modes must be 0644 or 0755")
        size = require_integer(
            entry.get("size"), f"archive manifest files[{index}].size"
        )
        if size < 0:
            fail("archive manifest file sizes must be nonnegative")
        digest = require_sha256(
            entry.get("sha256"),
            f"archive manifest files[{index}].sha256",
        )
        expected.append(
            {
                "path": relative.as_posix(),
                "mode": int(mode_text, 8),
                "size": size,
                "sha256": digest,
            }
        )
    expected_paths = [entry["path"] for entry in expected]
    if expected_paths != sorted(set(expected_paths)):
        fail("archive manifest paths must be sorted and unique")

    if len(raw_archive) < 10 or raw_archive[:2] != b"\x1f\x8b":
        fail("source archive is not gzip")
    if raw_archive[4:8] != b"\x00\x00\x00\x00":
        fail("source archive gzip timestamp is not deterministic zero")

    try:
        archive = tarfile.open(fileobj=io.BytesIO(raw_archive), mode="r:gz")
    except tarfile.TarError as error:
        fail(f"source archive is not a valid tar.gz: {error}")
    observed: list[dict[str, Any]] = []
    with archive:
        for member in archive.getmembers():
            member_path = safe_relative_path(member.name, "archive member")
            if not member.isfile():
                fail(f"archive contains a non-regular member: {member.name}")
            if len(member_path.parts) < 2 or member_path.parts[0] != prefix.name:
                fail(f"archive member is outside its prefix: {member.name}")
            if (
                member.mtime != 0
                or member.uid != 0
                or member.gid != 0
                or member.uname not in {"", None}
                or member.gname not in {"", None}
            ):
                fail(f"archive member metadata is nondeterministic: {member.name}")
            extracted = archive.extractfile(member)
            if extracted is None:
                fail(f"archive member could not be read: {member.name}")
            raw = extracted.read()
            observed.append(
                {
                    "path": PurePosixPath(*member_path.parts[1:]).as_posix(),
                    "mode": stat.S_IMODE(member.mode),
                    "size": len(raw),
                    "sha256": sha256_bytes(raw),
                }
            )
    if observed != expected:
        fail("source archive contents do not exactly match its manifest")
    return manifest


def verify_archive_manifest_against_commit(
    repository: Path,
    commit: str,
    manifest: dict[str, Any],
) -> None:
    tree_raw = run_git(
        repository,
        ["ls-tree", "-r", "-z", commit],
        text=False,
    )
    assert isinstance(tree_raw, bytes)
    tracked: dict[str, tuple[str, bytes]] = {}
    for record in tree_raw.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, object_type, object_id = metadata.decode("ascii").split(" ")
        path = raw_path.decode("utf-8")
        if object_type != "blob" or mode not in {"100644", "100755"}:
            fail(f"unsupported tracked release entry: {path}")
        raw = run_git(
            repository,
            ["cat-file", "blob", object_id],
            text=False,
        )
        assert isinstance(raw, bytes)
        tracked[path] = (
            "0755" if mode == "100755" else "0644",
            raw,
        )

    files = require_array(manifest.get("files"), "archive manifest files")
    manifest_paths = [
        require_string(entry.get("path"), "archive manifest path")
        for entry in files
        if isinstance(entry, dict)
    ]
    if len(manifest_paths) != len(files):
        fail("archive manifest contains a non-object file entry")
    if manifest_paths != sorted(tracked):
        fail("source archive is not the exact committed tracked file set")
    for entry in files:
        assert isinstance(entry, dict)
        path = require_string(entry.get("path"), "archive manifest path")
        mode, raw = tracked[path]
        if entry.get("mode") != mode:
            fail(f"archive mode differs from committed mode: {path}")
        if entry.get("size") != len(raw):
            fail(f"archive size differs from committed blob: {path}")
        if entry.get("sha256") != sha256_bytes(raw):
            fail(f"archive digest differs from committed blob: {path}")


def verify_source_assets(
    repository: Path,
    commit: str,
    summary_value: Any,
    archive_argument: Path,
    manifest_argument: Path,
) -> tuple[dict[str, Any], bytes, bytes]:
    summary = require_object(summary_value, "source_archive")
    expected_archive_keys = {
        "deterministic_rebuild",
        "exact_source_equivalence",
        "file_count",
        "filename",
        "manifest_filename",
        "manifest_sha256",
        "no_cache_files",
        "no_git",
        "no_lake",
        "path_and_symlink_safety",
        "result",
        "sha256",
    }
    if set(summary) != expected_archive_keys:
        fail("Git-mode source archive evidence schema changed")
    for key in (
        "deterministic_rebuild",
        "exact_source_equivalence",
        "path_and_symlink_safety",
        "result",
    ):
        require_pass(summary.get(key), f"source_archive.{key}")
    for key in ("no_cache_files", "no_git", "no_lake"):
        if require_bool(summary.get(key), f"source_archive.{key}") is not True:
            fail(f"source_archive.{key} must be true")
    if require_integer(
        summary.get("file_count"), "source_archive.file_count"
    ) <= 0:
        fail("source_archive.file_count must be positive")
    archive_name = safe_relative_path(
        summary.get("filename"),
        "source_archive.filename",
        basename_only=True,
    )
    manifest_name = safe_relative_path(
        summary.get("manifest_filename"),
        "source_archive.manifest_filename",
        basename_only=True,
    )
    if archive_name == manifest_name:
        fail("source archive and archive manifest basenames must be distinct")
    archive_path = absolute_without_symlink(
        archive_argument, "source archive"
    )
    manifest_path = absolute_without_symlink(
        manifest_argument, "source archive manifest"
    )
    assert_outside_repository(
        archive_path, repository, "source archive"
    )
    assert_outside_repository(
        manifest_path, repository, "source archive manifest"
    )
    if archive_path.name != archive_name.name:
        fail("source archive basename differs from gate summary")
    if manifest_path.name != manifest_name.name:
        fail("source archive manifest basename differs from gate summary")
    raw_archive = read_bytes(archive_path, "source archive")
    raw_manifest = read_bytes(manifest_path, "source archive manifest")
    archive_digest = sha256_bytes(raw_archive)
    manifest_digest = sha256_bytes(raw_manifest)
    if archive_digest != require_sha256(
        summary.get("sha256"), "source_archive.sha256"
    ):
        fail("source archive SHA-256 differs from gate summary")
    if manifest_digest != require_sha256(
        summary.get("manifest_sha256"),
        "source_archive.manifest_sha256",
    ):
        fail("source archive manifest SHA-256 differs from gate summary")
    archive_manifest = verify_archive_manifest(raw_archive, raw_manifest)
    verify_archive_manifest_against_commit(
        repository, commit, archive_manifest
    )
    normalized = {
        "archive": {
            "path": archive_name.as_posix(),
            "sha256": archive_digest,
        },
        "archive_manifest": {
            "path": manifest_name.as_posix(),
            "sha256": manifest_digest,
        },
    }
    return normalized, raw_archive, raw_manifest


def verify_source_only_gate_summary(
    path_argument: Path,
    repository: Path,
    git_gate_summary: dict[str, Any],
    git_identity: dict[str, str],
) -> tuple[dict[str, str], bytes, str]:
    path = absolute_without_symlink(
        path_argument, "source-only gate summary"
    )
    assert_outside_repository(
        path, repository, "source-only gate summary"
    )
    raw = read_bytes(path, "source-only gate summary")
    summary = read_json_bytes(raw, "source-only gate summary")
    ensure_public_safe_json(summary, "source-only gate summary")
    if raw != canonical_json_bytes(summary):
        fail("source-only gate summary must be canonical JSON")
    if summary.get("schema_version") != GATE_SCHEMA:
        fail("source-only gate summary schema changed")
    require_pass(summary.get("result"), "source-only gate summary result")
    if summary.get("intended_version") != VERSION:
        fail(f"source-only gate intended_version must be {VERSION}")

    _, source_started = require_timestamp(
        summary.get("started_at"), "source-only gate summary started_at"
    )
    source_completed_at, source_completed = require_timestamp(
        summary.get("completed_at"), "source-only gate summary completed_at"
    )
    if source_completed < source_started:
        fail("source-only gate completed_at precedes started_at")
    _, git_completed = require_timestamp(
        git_gate_summary.get("completed_at"), "gate summary completed_at"
    )
    if source_started < git_completed:
        fail("source-only gate did not follow the Git-mode release gate")

    source_repository = require_object(
        summary.get("repository"), "source-only repository"
    )
    expected_source_repository_keys = {
        "after_fingerprint",
        "before_fingerprint",
        "branch",
        "clean",
        "commit",
        "mode",
        "no_local_alternates",
        "remote",
        "tree",
    }
    if set(source_repository) != expected_source_repository_keys:
        fail("source-only repository evidence schema changed")
    if require_bool(
        source_repository.get("clean"), "source-only repository.clean"
    ) is not True:
        fail("source-only repository.clean must be true")
    if require_bool(
        source_repository.get("no_local_alternates"),
        "source-only repository.no_local_alternates",
    ) is not True:
        fail("source-only repository.no_local_alternates must be true")
    expected_repository_fields = {
        "branch": None,
        "clean": True,
        "commit": git_identity["commit"],
        "mode": "source-only",
        "no_local_alternates": True,
        "remote": git_identity["remote"],
        "tree": git_identity["tree"],
    }
    observed_repository_fields = {
        key: source_repository.get(key)
        for key in expected_repository_fields
    }
    if observed_repository_fields != expected_repository_fields:
        fail(
            "source-only repository identity differs from the Git gate: "
            f"expected {expected_repository_fields}, "
            f"observed {observed_repository_fields}"
        )
    source_before = require_object(
        source_repository.get("before_fingerprint"),
        "source-only repository.before_fingerprint",
    )
    source_after = require_object(
        source_repository.get("after_fingerprint"),
        "source-only repository.after_fingerprint",
    )
    if source_before != source_after:
        fail("source-only before and after fingerprints differ")
    if set(source_before) != {"clean", "commit", "source_sha256", "tree"}:
        fail("source-only fingerprint schema changed")
    if (
        require_bool(
            source_before.get("clean"),
            "source-only repository fingerprint clean",
        )
        is not True
        or source_before.get("commit") is not None
        or source_before.get("tree") is not None
    ):
        fail("source-only fingerprint identity fields are inconsistent")
    source_fingerprint_digest = require_sha256(
        source_before.get("source_sha256"),
        "source-only repository fingerprint source_sha256",
    )
    git_repository = require_object(
        git_gate_summary.get("repository"), "Git gate repository"
    )
    git_before = require_object(
        git_repository.get("before_fingerprint"),
        "Git gate repository.before_fingerprint",
    )
    git_after = require_object(
        git_repository.get("after_fingerprint"),
        "Git gate repository.after_fingerprint",
    )
    if git_before != git_after:
        fail("Git gate before and after fingerprints differ")
    git_source_fingerprint_digest = require_sha256(
        git_before.get("source_sha256"),
        "Git gate repository fingerprint source_sha256",
    )
    if source_fingerprint_digest != git_source_fingerprint_digest:
        fail("source-only source fingerprint differs from the Git gate")

    equivalent_fields = (
        "toolchain",
        "modules",
        "theorem_inventory",
        "checks",
        "claim_boundaries",
        "bounded_checker_disposition",
        "validation_reports",
    )
    for field in equivalent_fields:
        if summary.get(field) != git_gate_summary.get(field):
            fail(
                "source-only gate differs from Git-mode evidence for "
                f"{field}"
            )

    source_archive = require_object(
        summary.get("source_archive"), "source-only source_archive"
    )
    expected_source_archive_keys = {
        "deterministic_rebuild",
        "exact_source_equivalence",
        "file_count",
        "filename",
        "manifest_filename",
        "manifest_sha256",
        "matches_expected_archive",
        "matches_expected_manifest",
        "no_cache_files",
        "no_git",
        "no_lake",
        "path_and_symlink_safety",
        "result",
        "sha256",
    }
    if set(source_archive) != expected_source_archive_keys:
        fail("source-only archive evidence schema changed")
    for key in ("no_cache_files", "no_git", "no_lake"):
        if require_bool(
            source_archive.get(key), f"source-only source_archive.{key}"
        ) is not True:
            fail(f"source-only source_archive.{key} must be true")
    git_archive = require_object(
        git_gate_summary.get("source_archive"), "Git gate source_archive"
    )
    common_archive_fields = (
        "filename",
        "file_count",
        "manifest_filename",
        "manifest_sha256",
        "result",
        "sha256",
        "deterministic_rebuild",
        "exact_source_equivalence",
        "no_cache_files",
        "no_git",
        "no_lake",
        "path_and_symlink_safety",
    )
    for field in common_archive_fields:
        if source_archive.get(field) != git_archive.get(field):
            fail(
                "source-only archive differs from Git-mode archive for "
                f"{field}"
            )
    require_pass(
        source_archive.get("matches_expected_archive"),
        "source-only archive expected-archive comparison",
    )
    require_pass(
        source_archive.get("matches_expected_manifest"),
        "source-only archive expected-manifest comparison",
    )

    return (
        {
            "path": SOURCE_ONLY_GATE_SUMMARY_RELATIVE.as_posix(),
            "sha256": sha256_bytes(raw),
        },
        raw,
        source_completed_at,
    )


def verify_package_layout(paths: list[str]) -> None:
    normalized = [
        safe_relative_path(path, "release package planned path")
        for path in paths
    ]
    rendered = [path.as_posix() for path in normalized]
    if len(rendered) != len(set(rendered)):
        fail("release package planned paths must be unique")
    for index, left in enumerate(normalized):
        for right in normalized[index + 1 :]:
            common = min(len(left.parts), len(right.parts))
            if left.parts[:common] == right.parts[:common]:
                fail(
                    "release package file/directory path collision: "
                    f"{left.as_posix()} and {right.as_posix()}"
                )


def atomic_write(path: Path, raw: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def package_file_map(package: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in package.rglob("*"):
        if path.is_symlink():
            fail(f"release package contains a symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            fail(f"release package contains a non-regular path: {path}")
        relative = PurePosixPath(path.relative_to(package).as_posix())
        safe_relative_path(relative.as_posix(), "package path")
        result[relative.as_posix()] = path
    return result


def render_sha256s(
    package: Path,
    *,
    overrides: dict[str, bytes] | None = None,
) -> bytes:
    overrides = overrides or {}
    files = package_file_map(package)
    names = sorted(
        (set(files) | set(overrides))
        - {CHECKSUMS_RELATIVE.as_posix()}
    )
    lines: list[str] = []
    for name in names:
        raw = overrides[name] if name in overrides else files[name].read_bytes()
        lines.append(f"{sha256_bytes(raw)}  {name}\n")
    return "".join(lines).encode("utf-8")


def directories_identical(left: Path, right: Path) -> bool:
    left_files = package_file_map(left)
    right_files = package_file_map(right)
    if set(left_files) != set(right_files):
        return False
    for name in left_files:
        if left_files[name].read_bytes() != right_files[name].read_bytes():
            return False
        if stat.S_IMODE(left_files[name].stat().st_mode) != stat.S_IMODE(
            right_files[name].stat().st_mode
        ):
            return False
    return True


def install_package_atomically(staging: Path, output: Path) -> str:
    if output.exists():
        if output.is_symlink() or not output.is_dir():
            fail("existing release output is not a regular directory")
        if not directories_identical(staging, output):
            fail("release output exists and is not byte-identical")
        return "IDENTICAL"
    os.replace(staging, output)
    descriptor = os.open(output.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return "CREATED"


def prepare(arguments: argparse.Namespace) -> int:
    raw_gate_summary = read_bytes(arguments.gate_summary, "gate summary")
    gate_summary = read_json_bytes(raw_gate_summary, "gate summary")
    ensure_public_safe_json(gate_summary, "gate summary")
    if raw_gate_summary != canonical_json_bytes(gate_summary):
        fail("gate summary must be canonical JSON")
    if gate_summary.get("schema_version") != GATE_SCHEMA:
        fail(f"unsupported gate summary schema: {gate_summary.get('schema_version')}")
    require_pass(gate_summary.get("result"), "gate summary result")
    if gate_summary.get("intended_version") != VERSION:
        fail(f"gate summary intended_version must be {VERSION}")
    started_at, started = require_timestamp(
        gate_summary.get("started_at"), "gate summary started_at"
    )
    completed_at, completed = require_timestamp(
        gate_summary.get("completed_at"), "gate summary completed_at"
    )
    if completed < started:
        fail("gate summary completed_at precedes started_at")

    summary_repository = require_object(
        gate_summary.get("repository"), "repository"
    )
    repository, git_identity, before, after = verify_repository(
        arguments.repository, summary_repository
    )
    output = absolute_without_symlink(arguments.output_dir, "output directory")
    assert_outside_repository(output, repository, "output directory")
    output.parent.mkdir(parents=True, exist_ok=True)

    toolchain = verify_toolchain(gate_summary.get("toolchain"))
    modules = verify_modules(
        repository, git_identity["commit"], gate_summary.get("modules")
    )
    validation_reports, report_bytes = verify_validation_reports(
        repository,
        git_identity["commit"],
        gate_summary.get("validation_reports"),
    )
    inventory, axiom_results = verify_inventory(
        gate_summary.get("theorem_inventory"), report_bytes
    )
    checks = verify_checks(gate_summary.get("checks"))
    claim_boundaries = verify_claim_boundaries(
        gate_summary.get("claim_boundaries")
    )
    bounded_checker_disposition = require_string(
        gate_summary.get("bounded_checker_disposition"),
        "bounded_checker_disposition",
    )
    ensure_public_safe_json(
        bounded_checker_disposition, "bounded_checker_disposition"
    )
    source_assets, raw_archive, raw_archive_manifest = verify_source_assets(
        repository,
        git_identity["commit"],
        gate_summary.get("source_archive"),
        arguments.source_archive,
        arguments.archive_manifest,
    )
    (
        source_only_gate,
        raw_source_only_gate,
        source_only_completed_at,
    ) = (
        verify_source_only_gate_summary(
            arguments.source_only_gate_summary,
            repository,
            gate_summary,
            git_identity,
        )
    )

    canonical_gate_summary = canonical_json_bytes(gate_summary)
    gate_summary_digest = sha256_bytes(canonical_gate_summary)
    evidence = [
        {
            "path": GATE_SUMMARY_RELATIVE.as_posix(),
            "sha256": gate_summary_digest,
        },
        copy.deepcopy(source_only_gate),
        *copy.deepcopy(validation_reports),
    ]
    evidence.sort(key=lambda entry: entry["path"])
    verify_package_layout(
        [
            source_assets["archive"]["path"],
            source_assets["archive_manifest"]["path"],
            RECEIPT_RELATIVE.as_posix(),
            RECEIPT_SHA_RELATIVE.as_posix(),
            CHECKSUMS_RELATIVE.as_posix(),
            INVENTORY_SHA_RELATIVE.as_posix(),
            RELEASE_MANIFEST_RELATIVE.as_posix(),
            *(entry["path"] for entry in evidence),
        ]
    )

    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "result": "PASS",
        "started_at": started_at,
        "completed_at": source_only_completed_at,
        "intended_version": VERSION,
        "repository": copy.deepcopy(git_identity),
        "toolchain": toolchain,
        "module_hashes": modules,
        "theorem_inventory": {
            **inventory,
            "theorem_axiom_results": axiom_results,
        },
        "checks": checks,
        "source_archive": copy.deepcopy(source_assets),
        "worktree_fingerprints": {
            "before": before,
            "after": after,
            "equal": True,
        },
        "claim_boundaries": claim_boundaries,
        "bounded_checker_disposition": bounded_checker_disposition,
        "validation_evidence": evidence,
        "gate_summary": {
            "path": GATE_SUMMARY_RELATIVE.as_posix(),
            "sha256": gate_summary_digest,
        },
        "source_only_gate_summary": {
            **copy.deepcopy(source_only_gate),
            "result": "PASS",
        },
    }
    ensure_public_safe_json(receipt, "release receipt")
    raw_receipt = canonical_json_bytes(receipt)
    receipt_digest = sha256_bytes(raw_receipt)

    release_manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "result": "PASS",
        "created_at": source_only_completed_at,
        "intended_version": VERSION,
        "repository": copy.deepcopy(git_identity),
        "receipt": {
            "path": RECEIPT_RELATIVE.as_posix(),
            "sha256": receipt_digest,
        },
        "source_assets": copy.deepcopy(source_assets),
        "validation_evidence": evidence,
        "checksums": {"path": CHECKSUMS_RELATIVE.as_posix()},
        "local_tag": None,
    }
    ensure_public_safe_json(release_manifest, "release manifest")
    raw_release_manifest = canonical_json_bytes(release_manifest)

    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{output.name}.staging-", dir=output.parent
        )
    )
    installed = False
    try:
        atomic_write(
            staging / source_assets["archive"]["path"], raw_archive
        )
        atomic_write(
            staging / source_assets["archive_manifest"]["path"],
            raw_archive_manifest,
        )
        atomic_write(
            staging / GATE_SUMMARY_RELATIVE.as_posix(),
            canonical_gate_summary,
        )
        atomic_write(
            staging / SOURCE_ONLY_GATE_SUMMARY_RELATIVE.as_posix(),
            raw_source_only_gate,
        )
        for report in validation_reports:
            atomic_write(
                staging / report["path"], report_bytes[report["path"]]
            )
        inventory_sha_line = (
            f"{inventory['sha256']}  "
            f"{PurePosixPath(inventory['path']).name}\n"
        ).encode("utf-8")
        atomic_write(
            staging / INVENTORY_SHA_RELATIVE.as_posix(),
            inventory_sha_line,
        )
        atomic_write(
            staging / RECEIPT_RELATIVE.as_posix(), raw_receipt
        )
        receipt_sha_line = (
            f"{receipt_digest}  {RECEIPT_RELATIVE.name}\n"
        ).encode("utf-8")
        atomic_write(
            staging / RECEIPT_SHA_RELATIVE.as_posix(),
            receipt_sha_line,
        )
        atomic_write(
            staging / RELEASE_MANIFEST_RELATIVE.as_posix(),
            raw_release_manifest,
        )
        atomic_write(
            staging / CHECKSUMS_RELATIVE.as_posix(),
            render_sha256s(staging),
        )
        (
            final_repository,
            final_identity,
            final_before,
            final_after,
        ) = verify_repository(repository, summary_repository)
        if (
            final_repository != repository
            or final_identity != git_identity
            or final_before != before
            or final_after != after
        ):
            fail("repository identity changed before package installation")
        disposition = install_package_atomically(staging, output)
        installed = disposition == "CREATED"
    finally:
        if not installed and staging.exists():
            shutil.rmtree(staging)

    print(
        json.dumps(
            {
                "output": str(output),
                "receipt_sha256": receipt_digest,
                "result": disposition,
                "source_archive_sha256": source_assets["archive"]["sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


def verify_checksum_file(package: Path) -> None:
    checksum_path = package / CHECKSUMS_RELATIVE.as_posix()
    observed = read_bytes(checksum_path, "SHA256SUMS")
    expected = render_sha256s(package)
    if observed != expected:
        fail("existing SHA256SUMS does not match the package")


def verify_manifest_bound_files(
    package: Path,
    manifest: dict[str, Any],
) -> set[str]:
    receipt = require_object(manifest.get("receipt"), "manifest.receipt")
    receipt_path = safe_relative_path(
        receipt.get("path"), "manifest.receipt.path"
    ).as_posix()
    receipt_digest = require_sha256(
        receipt.get("sha256"), "manifest.receipt.sha256"
    )
    receipt_raw = read_bytes(package / receipt_path, "release receipt")
    if sha256_bytes(receipt_raw) != receipt_digest:
        fail("manifest receipt hash does not match the receipt")
    receipt_json = read_json_bytes(receipt_raw, "release receipt")
    if receipt_json.get("schema_version") != RECEIPT_SCHEMA:
        fail("manifest-bound receipt schema changed")
    require_pass(receipt_json.get("result"), "manifest-bound receipt result")
    if receipt_json.get("intended_version") != VERSION:
        fail(f"manifest-bound receipt intended_version must be {VERSION}")
    inventory = require_object(
        receipt_json.get("theorem_inventory"),
        "receipt.theorem_inventory",
    )
    inventory_path = safe_relative_path(
        inventory.get("path"),
        "receipt.theorem_inventory.path",
        required_parent="validation",
    )
    inventory_digest = require_sha256(
        inventory.get("sha256"),
        "receipt.theorem_inventory.sha256",
    )
    inventory_sha_path = safe_relative_path(
        inventory.get("sha256_path"),
        "receipt.theorem_inventory.sha256_path",
        required_parent="validation",
    )
    if inventory_sha_path.as_posix() != INVENTORY_SHA_RELATIVE.as_posix():
        fail("receipt theorem-inventory sidecar path changed")
    expected_inventory_sha = (
        f"{inventory_digest}  {inventory_path.name}\n"
    ).encode("utf-8")
    if read_bytes(
        package / inventory_sha_path.as_posix(),
        "theorem inventory SHA-256 sidecar",
    ) != expected_inventory_sha:
        fail("theorem inventory SHA-256 sidecar is malformed")

    source_assets = require_object(
        manifest.get("source_assets"), "manifest.source_assets"
    )
    receipt_source_assets = require_object(
        receipt_json.get("source_archive"), "receipt.source_archive"
    )
    if receipt_source_assets != source_assets:
        fail("receipt source archive differs from RELEASE_MANIFEST")
    bound = {
        receipt_path,
        RECEIPT_SHA_RELATIVE.as_posix(),
        RELEASE_MANIFEST_RELATIVE.as_posix(),
        CHECKSUMS_RELATIVE.as_posix(),
        INVENTORY_SHA_RELATIVE.as_posix(),
    }
    for key in ("archive", "archive_manifest"):
        asset = require_object(
            source_assets.get(key), f"manifest.source_assets.{key}"
        )
        asset_path = safe_relative_path(
            asset.get("path"), f"manifest.source_assets.{key}.path"
        ).as_posix()
        digest = require_sha256(
            asset.get("sha256"),
            f"manifest.source_assets.{key}.sha256",
        )
        if sha256_bytes(
            read_bytes(package / asset_path, f"manifest asset {key}")
        ) != digest:
            fail(f"manifest asset hash mismatch: {key}")
        bound.add(asset_path)
    evidence = require_array(
        manifest.get("validation_evidence"),
        "manifest.validation_evidence",
    )
    receipt_evidence = require_array(
        receipt_json.get("validation_evidence"),
        "receipt.validation_evidence",
    )
    if receipt_evidence != evidence:
        fail("receipt validation evidence differs from RELEASE_MANIFEST")
    evidence_paths: list[str] = []
    for index, item in enumerate(evidence):
        entry = require_object(
            item, f"manifest.validation_evidence[{index}]"
        )
        evidence_path = safe_relative_path(
            entry.get("path"),
            f"manifest.validation_evidence[{index}].path",
            required_parent="validation",
        ).as_posix()
        digest = require_sha256(
            entry.get("sha256"),
            f"manifest.validation_evidence[{index}].sha256",
        )
        if sha256_bytes(
            read_bytes(
                package / evidence_path,
                f"validation evidence {evidence_path}",
            )
        ) != digest:
            fail(f"validation evidence hash mismatch: {evidence_path}")
        evidence_paths.append(evidence_path)
        bound.add(evidence_path)
    if evidence_paths != sorted(set(evidence_paths)):
        fail("validation evidence paths must be sorted and unique")

    receipt_gate = require_object(
        receipt_json.get("gate_summary"), "receipt.gate_summary"
    )
    expected_gate = [
        entry
        for entry in evidence
        if isinstance(entry, dict)
        and entry.get("path") == GATE_SUMMARY_RELATIVE.as_posix()
    ]
    if expected_gate != [receipt_gate]:
        fail("receipt Git gate summary binding is not exact and unique")
    receipt_source_only_gate = require_object(
        receipt_json.get("source_only_gate_summary"),
        "receipt.source_only_gate_summary",
    )
    require_pass(
        receipt_source_only_gate.get("result"),
        "receipt.source_only_gate_summary.result",
    )
    source_only_binding = {
        "path": receipt_source_only_gate.get("path"),
        "sha256": receipt_source_only_gate.get("sha256"),
    }
    expected_source_only_gate = [
        entry
        for entry in evidence
        if isinstance(entry, dict)
        and entry.get("path")
        == SOURCE_ONLY_GATE_SUMMARY_RELATIVE.as_posix()
    ]
    if expected_source_only_gate != [source_only_binding]:
        fail("receipt source-only gate binding is not exact and unique")
    observed = set(package_file_map(package))
    if observed != bound:
        fail(
            "package file set differs from RELEASE_MANIFEST bindings: "
            f"expected {sorted(bound)}, found {sorted(observed)}"
        )
    return bound


def finalize(arguments: argparse.Namespace) -> int:
    repository = absolute_without_symlink(arguments.repository, "repository")
    package = absolute_without_symlink(arguments.package_dir, "package")
    assert_outside_repository(package, repository, "package")
    if not package.is_dir():
        fail("package is not a directory")

    manifest_path = package / RELEASE_MANIFEST_RELATIVE.as_posix()
    raw_manifest = read_bytes(manifest_path, "RELEASE_MANIFEST")
    manifest = read_json_bytes(raw_manifest, "RELEASE_MANIFEST")
    ensure_public_safe_json(manifest, "RELEASE_MANIFEST")
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        fail("unsupported RELEASE_MANIFEST schema")
    require_pass(manifest.get("result"), "RELEASE_MANIFEST result")
    if manifest.get("intended_version") != VERSION:
        fail(f"RELEASE_MANIFEST intended_version must be {VERSION}")

    verify_manifest_bound_files(package, manifest)
    verify_checksum_file(package)
    receipt_binding = require_object(
        manifest.get("receipt"), "manifest.receipt"
    )
    receipt_path = package / safe_relative_path(
        receipt_binding.get("path"), "manifest.receipt.path"
    ).as_posix()
    receipt_before = read_bytes(receipt_path, "release receipt")
    receipt_digest = require_sha256(
        receipt_binding.get("sha256"), "manifest.receipt.sha256"
    )
    if sha256_bytes(receipt_before) != receipt_digest:
        fail("release receipt hash mismatch before finalize")
    receipt_sha_path = package / RECEIPT_SHA_RELATIVE.as_posix()
    expected_receipt_sha = (
        f"{receipt_digest}  {RECEIPT_RELATIVE.name}\n"
    ).encode("utf-8")
    if read_bytes(receipt_sha_path, "receipt SHA-256 file") != expected_receipt_sha:
        fail("receipt SHA-256 sidecar is malformed")
    receipt = read_json_bytes(receipt_before, "release receipt")
    if receipt.get("schema_version") != RECEIPT_SCHEMA:
        fail("unsupported release receipt schema")

    receipt_repository = require_object(
        receipt.get("repository"), "receipt.repository"
    )
    receipt_fingerprints = require_object(
        receipt.get("worktree_fingerprints"),
        "receipt.worktree_fingerprints",
    )
    fingerprint_before = require_object(
        receipt_fingerprints.get("before"),
        "receipt.worktree_fingerprints.before",
    )
    fingerprint_after = require_object(
        receipt_fingerprints.get("after"),
        "receipt.worktree_fingerprints.after",
    )
    if fingerprint_before != fingerprint_after:
        fail("receipt before and after worktree fingerprints differ")
    if require_bool(
        receipt_fingerprints.get("equal"),
        "receipt.worktree_fingerprints.equal",
    ) is not True:
        fail("receipt worktree fingerprint equality is not true")
    verified_repository, identity, _, _ = verify_repository(
        repository,
        {
            **receipt_repository,
            "clean": True,
            "mode": "git",
            "no_local_alternates": True,
            "before_fingerprint": fingerprint_before,
            "after_fingerprint": fingerprint_after,
        },
    )
    if verified_repository != repository:
        fail("finalize repository identity changed unexpectedly")
    if manifest.get("repository") != identity:
        fail("RELEASE_MANIFEST repository differs from receipt")

    tag_name = require_string(arguments.tag, "tag")
    if tag_name != LOCAL_CANDIDATE_TAG:
        fail(
            "local release-candidate tag must be exactly "
            f"{LOCAL_CANDIDATE_TAG}"
        )
    if tag_name.startswith("-") or any(
        character in tag_name for character in ("\n", "\r", "\x00")
    ):
        fail("tag name is unsafe")
    run_git(
        repository,
        ["check-ref-format", f"refs/tags/{tag_name}"],
    )
    tag_object = str(
        run_git(
            repository,
            ["rev-parse", "--verify", f"refs/tags/{tag_name}"],
        )
    ).strip()
    require_git_object(tag_object, "local tag object")
    tag_type = str(
        run_git(repository, ["cat-file", "-t", tag_object])
    ).strip()
    if tag_type != "tag":
        fail("local release-candidate tag must be annotated")
    peeled_commit = str(
        run_git(
            repository,
            ["rev-parse", f"refs/tags/{tag_name}^{{commit}}"],
        )
    ).strip()
    peeled_tree = str(
        run_git(repository, ["rev-parse", f"{peeled_commit}^{{tree}}"])
    ).strip()
    if peeled_commit != identity["commit"] or peeled_tree != identity["tree"]:
        fail("annotated tag does not peel to the receipt commit and tree")
    raw_tag = run_git(repository, ["cat-file", "tag", tag_object], text=False)
    assert isinstance(raw_tag, bytes)
    try:
        tag_text = raw_tag.decode("utf-8")
    except UnicodeDecodeError as error:
        fail(f"annotated tag is not UTF-8: {error}")
    header, separator, message = tag_text.partition("\n\n")
    if not separator:
        fail("annotated tag has no message")
    if (
        "-----BEGIN PGP SIGNATURE-----" in tag_text
        or "-----BEGIN SSH SIGNATURE-----" in tag_text
    ):
        fail("signed local tag is outside this release authorization")
    header_lines = header.splitlines()
    if (
        f"object {peeled_commit}" not in header_lines
        or "type commit" not in header_lines
        or f"tag {tag_name}" not in header_lines
    ):
        fail("annotated tag headers do not bind the expected tag and commit")
    source_assets = require_object(
        manifest.get("source_assets"), "manifest.source_assets"
    )
    archive = require_object(
        source_assets.get("archive"), "manifest.source_assets.archive"
    )
    archive_manifest = require_object(
        source_assets.get("archive_manifest"),
        "manifest.source_assets.archive_manifest",
    )
    required_message_lines = {
        "commit": f"commit {peeled_commit}",
        "tree": f"tree {peeled_tree}",
        "release receipt sha256": (
            f"release receipt sha256 {receipt_digest}"
        ),
        "source archive sha256": (
            "source archive sha256 "
            f"{require_sha256(archive.get('sha256'), 'archive sha256')}"
        ),
        "archive manifest sha256": (
            "archive manifest sha256 "
            f"{require_sha256(archive_manifest.get('sha256'), 'archive manifest sha256')}"
        ),
    }
    message_lines = message.splitlines()
    if "TrackB v0.2.1 local release candidate" not in message_lines:
        fail("annotated tag subject is not the reviewed local-candidate subject")
    for prefix, expected_line in required_message_lines.items():
        matches = [
            line for line in message_lines if line.startswith(prefix + " ")
        ]
        if matches != [expected_line]:
            fail(
                "annotated tag does not uniquely bind required field: "
                f"{prefix}"
            )
    local_tag = {
        "name": tag_name,
        "tag_object": tag_object,
        "peeled_commit": peeled_commit,
        "tree": peeled_tree,
    }
    existing_tag = manifest.get("local_tag")
    if existing_tag is not None and existing_tag != local_tag:
        fail("RELEASE_MANIFEST already records a different local tag")

    updated_manifest = copy.deepcopy(manifest)
    updated_manifest["local_tag"] = local_tag
    ensure_public_safe_json(updated_manifest, "updated RELEASE_MANIFEST")
    updated_manifest_raw = canonical_json_bytes(updated_manifest)
    updated_checksums = render_sha256s(
        package,
        overrides={
            RELEASE_MANIFEST_RELATIVE.as_posix(): updated_manifest_raw
        },
    )
    old_manifest_raw = raw_manifest
    old_checksums = read_bytes(
        package / CHECKSUMS_RELATIVE.as_posix(), "SHA256SUMS"
    )
    try:
        atomic_write(manifest_path, updated_manifest_raw)
        atomic_write(
            package / CHECKSUMS_RELATIVE.as_posix(), updated_checksums
        )
    except Exception:
        atomic_write(manifest_path, old_manifest_raw)
        atomic_write(
            package / CHECKSUMS_RELATIVE.as_posix(), old_checksums
        )
        raise

    receipt_after = read_bytes(receipt_path, "release receipt")
    if receipt_after != receipt_before:
        fail("finalize changed the release receipt")
    verify_manifest_bound_files(package, updated_manifest)
    verify_checksum_file(package)
    print(
        json.dumps(
            {
                "local_tag": local_tag,
                "manifest": RELEASE_MANIFEST_RELATIVE.as_posix(),
                "receipt_sha256": receipt_digest,
                "result": "FINALIZED",
            },
            sort_keys=True,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare or finalize an external TrackB v0.2.1 local "
            "release package without creating tags or pushing."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser(
        "prepare",
        help="verify gate evidence and atomically create the external package",
    )
    prepare_parser.add_argument(
        "--repository", type=Path, default=ROOT
    )
    prepare_parser.add_argument(
        "--gate-summary", type=Path, required=True
    )
    prepare_parser.add_argument(
        "--source-only-gate-summary", type=Path, required=True
    )
    prepare_parser.add_argument(
        "--source-archive", type=Path, required=True
    )
    prepare_parser.add_argument(
        "--archive-manifest", type=Path, required=True
    )
    prepare_parser.add_argument(
        "--output-dir", type=Path, required=True
    )
    prepare_parser.set_defaults(handler=prepare)

    finalize_parser = subparsers.add_parser(
        "finalize",
        help=(
            "record an existing annotated local tag and regenerate "
            "SHA256SUMS without changing the receipt"
        ),
    )
    finalize_parser.add_argument(
        "--repository", type=Path, default=ROOT
    )
    finalize_parser.add_argument(
        "--package-dir", type=Path, required=True
    )
    finalize_parser.add_argument("--tag", required=True)
    finalize_parser.set_defaults(handler=finalize)
    return parser


def main() -> int:
    parser = build_parser()
    arguments = parser.parse_args()
    try:
        return int(arguments.handler(arguments))
    except ReleasePreparationError as error:
        print(f"release preparation failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

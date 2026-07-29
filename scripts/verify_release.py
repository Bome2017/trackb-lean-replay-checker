#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed, environment-derived release gate for TrackB v0.2.1."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.1"
GATE_SCHEMA = "trackb-release-gate-summary-v1"
ARCHIVE_PREFIX = "trackb-lean-replay-checker-v0.2.1"
EXPECTED_TOOLCHAIN = "leanprover/lean4:v4.32.1"
EXPECTED_LEAN_COMMIT = "f054605aea4b840552cca2e725580bffd1e1b704"
EXPECTED_LAKE_VERSION = "5.0.0-src+f054605"
EXPECTED_LAKEFILE_SHA256 = (
    "2f0c82b46229463808bf8b2c275c80c694aa6813998580340db16b6c0bf1f0fe"
)
EXPECTED_REMOTE = (
    "https://github.com/Bome2017/trackb-lean-replay-checker.git"
)
EXPECTED_LEAN_SOURCES = {
    "AxiomCheck.lean",
    "FixtureMain.lean",
    "GuardedExamples.lean",
    "Main.lean",
    "SafetyMain.lean",
    "SearchMain.lean",
    "TheoremInventory.lean",
    "TrackBReplay.lean",
    "TrackBResults.lean",
    "TrackBSafety.lean",
    "TrackBSearch.lean",
    "TrackBSemantics.lean",
}
OWNED_LEAN_SOURCES = EXPECTED_LEAN_SOURCES - {"TheoremInventory.lean"}
EXPECTED_OWNED_MODULES = {
    "AxiomCheck",
    "FixtureMain",
    "GuardedExamples",
    "Main",
    "SafetyMain",
    "SearchMain",
    "TrackBReplay",
    "TrackBResults",
    "TrackBSafety",
    "TrackBSearch",
    "TrackBSemantics",
}
EXPECTED_IMPORT_ROOTS = {
    "AxiomCheck",
    "FixtureMain",
    "Main",
    "SafetyMain",
    "SearchMain",
}
ALLOWED_AXIOMS = {"Classical.choice", "Quot.sound", "propext"}
JUSTIFIED_INVENTORY_UNSAFE_DEFS = {
    "buildInventory",
    "main",
    "run",
}
REQUIRED_FORMAL_THEOREMS = {
    "bounded_output_binding": (
        "TrackBReplay.checked_bounded_safe_endToEnd"
    ),
    "metadata_consistency": (
        "TrackBReplay.GlobalSafetyResult.metadataCheck_iff"
    ),
    "semantic_soundness": (
        "TrackBReplay.GlobalSafetyResult.semanticCheck_sound"
    ),
    "combined_checker": "TrackBReplay.GlobalSafetyResult.check_sound",
}
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
FIXTURE_THEOREM_BINDINGS = {
    (
        "fixtures/guarded/agent_email_requires_approval/workflow.json"
    ): (
        "TrackBReplay.GuardedExamples.emailFixture_compile",
        "TrackBReplay.GuardedExamples.emailCertificate_check",
        (
            "TrackBReplay.GuardedExamples."
            "email_requires_approval_globally_safe"
        ),
    ),
    (
        "fixtures/guarded/agent_delete_requires_confirmation/workflow.json"
    ): (
        "TrackBReplay.GuardedExamples.deleteFixture_compile",
        "TrackBReplay.GuardedExamples.deleteCertificate_check",
        (
            "TrackBReplay.GuardedExamples."
            "delete_requires_confirmation_globally_safe"
        ),
    ),
    (
        "fixtures/guarded/agent_vendor_payment_guarded/workflow.json"
    ): (
        "TrackBReplay.GuardedExamples.vendorPaymentFixture_compile",
        "TrackBReplay.GuardedExamples.vendorPaymentCertificate_check",
        (
            "TrackBReplay.GuardedExamples."
            "vendor_payment_guarded_globally_safe"
        ),
    ),
}
EXPECTED_TEST_IDS = {
    (
        "test_bounded_result_emission.BoundedResultEmissionTests."
        "test_checked_package_binds_engine_result_and_semantics"
    ),
    (
        "test_bounded_result_emission.BoundedResultEmissionTests."
        "test_deterministic_report_matches_live_validation"
    ),
    (
        "test_bounded_result_emission.BoundedResultEmissionTests."
        "test_emitted_object_is_the_exact_carried_result"
    ),
    (
        "test_bounded_result_emission.BoundedResultEmissionTests."
        "test_every_required_emitted_field_matches_engine_fixture"
    ),
    (
        "test_bounded_result_emission.BoundedResultEmissionTests."
        "test_field_substitutions_are_not_the_carried_object"
    ),
    (
        "test_bounded_result_emission.BoundedResultEmissionTests."
        "test_search_main_serializes_the_carried_result_directly"
    ),
    "test_end_to_end.EndToEndTests.test_receipt_binds_exact_bytes",
    "test_end_to_end.EndToEndTests.test_safe_result_is_out_of_scope",
    "test_end_to_end.EndToEndTests.test_tampered_transition_fails",
    "test_end_to_end.EndToEndTests.test_valid_runtime_pair_passes",
    "test_end_to_end.EndToEndTests.test_workflow_result_binding_fails_closed",
    (
        "test_reachability.ReachabilityTests."
        "test_forbidden_sibling_key_is_rejected"
    ),
    (
        "test_reachability.ReachabilityTests."
        "test_generated_unsafe_result_passes_native_replay_checker"
    ),
    (
        "test_reachability.ReachabilityTests."
        "test_guarded_fixture_correspondence_mismatch_fails"
    ),
    (
        "test_reachability.ReachabilityTests."
        "test_guarded_fixtures_bind_and_have_checked_global_certificates"
    ),
    (
        "test_reachability.ReachabilityTests."
        "test_incomplete_global_closure_is_rejected"
    ),
    (
        "test_reachability.ReachabilityTests."
        "test_safe_within_bound_is_distinct_from_global_safety"
    ),
    (
        "test_theorem_inventory_gate.TheoremInventoryHostileGateTests."
        "test_all_fourteen_required_cases_are_reported"
    ),
    (
        "test_theorem_inventory_gate.TheoremInventoryHostileGateTests."
        "test_comments_strings_and_definitions_are_not_theorems"
    ),
    (
        "test_theorem_inventory_gate.TheoremInventoryHostileGateTests."
        "test_external_is_excluded_and_local_owned_theorem_is_included"
    ),
    (
        "test_theorem_inventory_gate.TheoremInventoryHostileGateTests."
        "test_generated_projection_and_recursor_are_not_authored"
    ),
    (
        "test_theorem_inventory_gate.TheoremInventoryHostileGateTests."
        "test_hostile_modules_and_outputs_remain_outside_repository"
    ),
    (
        "test_theorem_inventory_gate.TheoremInventoryHostileGateTests."
        "test_multiline_attributes_and_unusual_whitespace_are_discovered"
    ),
    (
        "test_theorem_inventory_gate.TheoremInventoryHostileGateTests."
        "test_multiline_unicode_and_quoted_theorems_are_discovered"
    ),
    (
        "test_theorem_inventory_gate.TheoremInventoryHostileGateTests."
        "test_nested_and_duplicate_leaf_full_names_are_preserved"
    ),
    (
        "test_theorem_inventory_gate.TheoremInventoryHostileGateTests."
        "test_safe_hostile_syntax_fixture_passes_axiom_gates"
    ),
    (
        "test_theorem_inventory_gate.TheoremInventoryHostileGateTests."
        "test_sorry_ax_theorem_is_discovered_and_fails_closed"
    ),
    (
        "test_z3_witness_proposer.Z3WitnessProposerTests."
        "test_checker_timeout_is_explicit_and_nonzero"
    ),
    (
        "test_z3_witness_proposer.Z3WitnessProposerTests."
        "test_lean_rejection_is_comparison_mismatch_and_nonzero"
    ),
    (
        "test_z3_witness_proposer.Z3WitnessProposerTests."
        "test_sat_candidate_crosses_the_real_lean_checker_interface"
    ),
    (
        "test_z3_witness_proposer.Z3WitnessProposerTests."
        "test_sat_candidate_requires_and_records_lean_acceptance"
    ),
    (
        "test_z3_witness_proposer.Z3WitnessProposerTests."
        "test_solver_error_is_explicit_and_nonzero"
    ),
    (
        "test_z3_witness_proposer.Z3WitnessProposerTests."
        "test_solver_timeout_is_explicit_and_nonzero"
    ),
    (
        "test_z3_witness_proposer.Z3WitnessProposerTests."
        "test_unknown_is_inconclusive_and_nonzero"
    ),
    (
        "test_z3_witness_proposer.Z3WitnessProposerTests."
        "test_unsat_is_advisory_and_never_safe"
    ),
}
EXCLUDED_ARCHIVE_PARTS = {
    ".git",
    ".lake",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "receipts",
}
EXCLUDED_ARCHIVE_SUFFIXES = {
    ".a",
    ".bc",
    ".c",
    ".ilean",
    ".o",
    ".olean",
    ".pyc",
    ".so",
}
PRIVATE_PATH_PATTERNS = (
    re.compile(
        ("/" + "Users" + r"/[^/\r\n\"'<>]+").encode("ascii")
    ),
    re.compile(
        ("/" + "home" + r"/[^/\r\n\"'<>]+").encode("ascii")
    ),
    re.compile(
        (
            r"[A-Za-z]:\\"
            + "Users"
            + r"\\[^\\\r\n\"'<>]+"
        ).encode("ascii")
    ),
    re.compile(
        (
            "/" + "private" + "/" + "tmp" + r"(?:/|$)"
        ).encode("ascii")
    ),
    re.compile(
        (
            "/" + "private" + "/" + "var" + r"/folders/[^\s\"'<>]+"
        ).encode("ascii")
    ),
    re.compile(
        ("/" + "var" + r"/folders/[^\s\"'<>]+").encode("ascii")
    ),
)
CURRENT_CLAIM_DOCUMENTS = (
    "README.md",
    "CLAIM_BOUNDARIES.md",
    "RELEASE_NOTES_v0.2.1.md",
    "SEMANTICS_AND_INPUT_DOMAIN.md",
    "docs/BOUNDED_RESULT_CHECKER_DECISION.md",
    "docs/HOSTILE_THEOREM_GATE.md",
    "docs/MIGRATION_v0.1.0_TO_v0.2.1.md",
    "docs/PUBLICATION_PLAN_v0.2.1.md",
    "docs/REPLAYGUARD_E2A_CERTIFICATE_BOUNDARY.md",
    "docs/THEOREM_INVENTORY_POLICY.md",
)
SANITIZED_ENVIRONMENT_KEYS = {
    "DYLD_FALLBACK_LIBRARY_PATH",
    "DYLD_LIBRARY_PATH",
    "ELAN_TOOLCHAIN",
    "LAKE_HOME",
    "LD_LIBRARY_PATH",
    "LEAN_PATH",
    "LEAN_SRC_PATH",
    "LEAN_SYSROOT",
    "PYTHONHOME",
    "PYTHONPATH",
}


class GateFailure(RuntimeError):
    """A release-gate condition failed."""


def fail(message: str) -> None:
    raise GateFailure(message)


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


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


def release_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for key in list(environment):
        if (
            key in SANITIZED_ENVIRONMENT_KEYS
            or key.startswith("GIT_")
        ):
            environment.pop(key, None)
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONHASHSEED"] = "0"
    return environment


def verify_invocation_environment() -> dict[str, object]:
    injected = sorted(
        key
        for key in SANITIZED_ENVIRONMENT_KEYS
        if os.environ.get(key)
    )
    if injected:
        fail(
            "release gate was invoked with path/toolchain injection "
            f"variables set: {injected}"
        )
    return {
        "path_or_toolchain_injection_variables": [],
        "result": "PASS",
    }


def private_path_bytes_match(raw: bytes) -> bool:
    for pattern in PRIVATE_PATH_PATTERNS:
        if pattern.search(raw):
            return True
    sensitive_paths = {
        str(ROOT.resolve()),
        str(ROOT.resolve().parent),
        str(Path.home().resolve()),
    }
    temporary_root = os.environ.get("TMPDIR")
    if temporary_root:
        sensitive_paths.add(str(Path(temporary_root).resolve()))
    for sensitive in sorted(sensitive_paths, key=len, reverse=True):
        if len(sensitive) >= 8 and sensitive.encode("utf-8") in raw:
            return True
    return False


def json_strings(value: object) -> list[str]:
    strings: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if isinstance(key, str):
                strings.append(key)
            strings.extend(json_strings(nested))
    elif isinstance(value, list):
        for nested in value:
            strings.extend(json_strings(nested))
    elif isinstance(value, str):
        strings.append(value)
    return strings


def decoded_json_private_path_match(raw: bytes) -> bool:
    pending: list[tuple[str, int]] = []
    try:
        decoded = raw.decode("utf-8")
        parsed = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    pending.extend((value, 0) for value in json_strings(parsed))
    while pending:
        value, depth = pending.pop()
        encoded = value.encode("utf-8")
        if private_path_bytes_match(encoded):
            return True
        if depth >= 4:
            continue
        try:
            nested = json.loads(value)
        except json.JSONDecodeError:
            continue
        pending.extend(
            (nested_value, depth + 1)
            for nested_value in json_strings(nested)
        )
    return False


def verify_no_private_path_bytes(raw: bytes, label: str) -> None:
    if private_path_bytes_match(raw):
        fail(f"host-local absolute path found in {label}")
    if decoded_json_private_path_match(raw):
        fail(f"JSON-decoded host-local absolute path found in {label}")


def verify_private_path_policy() -> dict[str, object]:
    rejected = (
        ("/" + "Users" + "/alice/project").encode("utf-8"),
        ("/" + "Users" + "/Alice Smith/project").encode("utf-8"),
        ("/" + "home" + "/alice/project").encode("utf-8"),
        ("C:" + "\\" + "Users" + "\\" + "Alice Smith" + "\\project").encode(
            "utf-8"
        ),
        ("/" + "private" + "/" + "tmp" + "/build/output").encode("utf-8"),
        ("/" + "var" + "/folders/host/cache").encode("utf-8"),
        json.dumps(
            {"path": "C:" + "\\" + "Users" + "\\" + "Alice Smith" + "\\project"}
        ).encode("utf-8"),
        (
            '{"path":"\\/'
            + "Users"
            + '\\/Alice Smith\\/project"}'
        ).encode("utf-8"),
    )
    accepted = (
        b"validation/theorem_inventory.json",
        b"https://github.com/Bome2017/trackb-lean-replay-checker.git",
        b"/tmp/trackb-public-example.json",
    )
    for probe in rejected:
        if not (
            private_path_bytes_match(probe)
            or decoded_json_private_path_match(probe)
        ):
            fail(f"private-path rejection policy missed probe: {probe!r}")
    for probe in accepted:
        if (
            private_path_bytes_match(probe)
            or decoded_json_private_path_match(probe)
        ):
            fail(f"private-path rejection policy rejected safe probe: {probe!r}")
    return {
        "accepted_safe_probes": len(accepted),
        "rejected_private_probes": len(rejected),
        "result": "PASS",
    }


def run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    accepted: set[int] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=release_environment() if env is None else env,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        fail(f"cannot execute {' '.join(command)}: {error}")
    accepted_codes = {0} if accepted is None else accepted
    if completed.returncode not in accepted_codes:
        output = completed.stdout + completed.stderr
        if output:
            sys.stderr.write(output)
        fail(
            "command failed with exit "
            f"{completed.returncode}: {' '.join(command)}"
        )
    return completed


def git_text(*arguments: str) -> str:
    return run(["git", *arguments]).stdout.strip()


def ensure_outside_root(path: Path, label: str) -> Path:
    if path.is_symlink():
        fail(f"{label} must not be a symlink")
    resolved = path.resolve()
    root = ROOT.resolve()
    if resolved == root or root in resolved.parents:
        fail(f"{label} must be outside the source tree")
    return resolved


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--expected-branch")
    parser.add_argument("--expected-remote", default=EXPECTED_REMOTE)
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="validate an archive extraction with no Git metadata",
    )
    parser.add_argument(
        "--expected-source-manifest",
        type=Path,
        help="manifest that defines exact files in source-only mode",
    )
    parser.add_argument("--expected-source-manifest-sha256")
    parser.add_argument("--expected-source-archive-sha256")
    parser.add_argument(
        "--require-no-lake-at-start",
        action="store_true",
        help="fail unless the validation tree begins without .lake",
    )
    parser.add_argument("--archive-output", type=Path)
    parser.add_argument("--archive-manifest-output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    arguments = parser.parse_args()

    object_id_pattern = re.compile(r"[0-9a-f]{40}")
    digest_pattern = re.compile(r"[0-9a-f]{64}")
    if not object_id_pattern.fullmatch(arguments.expected_commit):
        parser.error("--expected-commit must be a lowercase 40-hex object ID")
    if not object_id_pattern.fullmatch(arguments.expected_tree):
        parser.error("--expected-tree must be a lowercase 40-hex object ID")
    if bool(arguments.archive_output) != bool(
        arguments.archive_manifest_output
    ):
        parser.error(
            "--archive-output and --archive-manifest-output are required "
            "together"
        )
    if arguments.source_only:
        if (
            arguments.expected_source_manifest is None
            or arguments.expected_source_manifest_sha256 is None
            or arguments.expected_source_archive_sha256 is None
        ):
            parser.error(
                "--source-only requires --expected-source-manifest, "
                "--expected-source-manifest-sha256, and "
                "--expected-source-archive-sha256"
            )
        if not digest_pattern.fullmatch(
            arguments.expected_source_manifest_sha256
        ):
            parser.error(
                "--expected-source-manifest-sha256 must be lowercase "
                "64-hex"
            )
        if not digest_pattern.fullmatch(
            arguments.expected_source_archive_sha256
        ):
            parser.error(
                "--expected-source-archive-sha256 must be lowercase "
                "64-hex"
            )
        if arguments.expected_branch is not None:
            parser.error(
                "--expected-branch is not meaningful in source-only mode"
            )
    elif any(
        value is not None
        for value in (
            arguments.expected_source_manifest,
            arguments.expected_source_manifest_sha256,
            arguments.expected_source_archive_sha256,
        )
    ):
        parser.error(
            "expected source artifact options are only valid with "
            "--source-only"
        )
    else:
        if arguments.expected_branch is None:
            parser.error("Git release mode requires --expected-branch")
        if not arguments.require_no_lake_at_start:
            parser.error(
                "Git release mode requires --require-no-lake-at-start"
            )
    artifact_paths = [
        path.resolve()
        for path in (
            arguments.expected_source_manifest,
            arguments.archive_output,
            arguments.archive_manifest_output,
            arguments.summary_output,
        )
        if path is not None
    ]
    if len(artifact_paths) != len(set(artifact_paths)):
        parser.error("release input and output artifact paths must be distinct")
    if (
        arguments.archive_output is not None
        and arguments.archive_manifest_output is not None
        and arguments.archive_output.name
        == arguments.archive_manifest_output.name
    ):
        parser.error(
            "source archive and archive manifest basenames must be distinct"
        )
    return arguments


def excluded_release_path(relative: PurePosixPath) -> bool:
    if any(part in EXCLUDED_ARCHIVE_PARTS for part in relative.parts):
        return True
    return relative.name == ".DS_Store" or (
        relative.suffix in EXCLUDED_ARCHIVE_SUFFIXES
    )


def verify_prebuild_clean_tree() -> dict[str, object]:
    contaminants: list[str] = []
    for directory, directory_names, file_names in os.walk(
        ROOT, followlinks=False
    ):
        directory_path = Path(directory)
        relative_directory = directory_path.relative_to(ROOT)
        if relative_directory == Path("."):
            directory_names[:] = [
                name for name in directory_names if name != ".git"
            ]
            file_names = [name for name in file_names if name != ".git"]
        retained_directories: list[str] = []
        for name in directory_names:
            path = directory_path / name
            relative = PurePosixPath(path.relative_to(ROOT).as_posix())
            if path.is_symlink():
                fail(f"prebuild tree contains a symlink: {relative}")
            if excluded_release_path(relative):
                contaminants.append(relative.as_posix())
            elif not path.is_dir():
                fail(f"prebuild tree contains a non-regular path: {relative}")
            else:
                retained_directories.append(name)
        directory_names[:] = retained_directories
        for name in file_names:
            path = directory_path / name
            relative = PurePosixPath(path.relative_to(ROOT).as_posix())
            if path.is_symlink():
                fail(f"prebuild tree contains a symlink: {relative}")
            if excluded_release_path(relative):
                contaminants.append(relative.as_posix())
            elif not path.is_file():
                fail(f"prebuild tree contains a non-regular path: {relative}")
    if contaminants:
        fail(
            "prebuild tree contains generated/cache material: "
            f"{sorted(contaminants)}"
        )
    return {
        "generated_or_cache_paths": [],
        "result": "PASS",
        "symlinks": [],
    }


def verify_postbuild_clean_tree() -> dict[str, object]:
    contaminants: list[str] = []
    for directory, directory_names, file_names in os.walk(
        ROOT, followlinks=False
    ):
        directory_path = Path(directory)
        relative_directory = directory_path.relative_to(ROOT)
        if relative_directory == Path("."):
            directory_names[:] = [
                name
                for name in directory_names
                if name not in {".git", ".lake"}
            ]
            file_names = [name for name in file_names if name != ".git"]
        retained_directories: list[str] = []
        for name in directory_names:
            path = directory_path / name
            relative = PurePosixPath(path.relative_to(ROOT).as_posix())
            if path.is_symlink():
                fail(f"postbuild source tree contains a symlink: {relative}")
            if excluded_release_path(relative):
                contaminants.append(relative.as_posix())
            elif not path.is_dir():
                fail(f"postbuild source tree has a non-regular path: {relative}")
            else:
                retained_directories.append(name)
        directory_names[:] = retained_directories
        for name in file_names:
            path = directory_path / name
            relative = PurePosixPath(path.relative_to(ROOT).as_posix())
            if path.is_symlink():
                fail(f"postbuild source tree contains a symlink: {relative}")
            if excluded_release_path(relative):
                contaminants.append(relative.as_posix())
            elif not path.is_file():
                fail(f"postbuild source tree has a non-regular path: {relative}")
    if contaminants:
        fail(
            "postbuild source tree contains unexpected generated/cache "
            f"material: {sorted(contaminants)}"
        )
    return {
        "allowed_lake_build_directory": True,
        "generated_or_cache_paths_outside_lake": [],
        "result": "PASS",
        "symlinks_outside_lake": [],
    }


def release_source_paths() -> list[Path]:
    paths: list[Path] = []
    for path in ROOT.rglob("*"):
        relative = PurePosixPath(path.relative_to(ROOT).as_posix())
        if excluded_release_path(relative):
            continue
        if path.is_symlink():
            fail(f"source-tree symlink is forbidden: {relative}")
        if path.is_file():
            paths.append(path)
    return sorted(paths, key=lambda item: item.relative_to(ROOT).as_posix())


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        fail(f"invalid {label}: {error}")
    if not isinstance(value, dict):
        fail(f"{label} must be a JSON object")
    return value


def source_records(paths: list[Path]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        raw = path.read_bytes()
        mode = "0755" if path.stat().st_mode & stat.S_IXUSR else "0644"
        records.append(
            {
                "mode": mode,
                "path": relative,
                "sha256": sha256_bytes(raw),
                "size": len(raw),
            }
        )
    return records


def source_fingerprint(paths: list[Path]) -> str:
    return sha256_bytes(canonical_json_bytes(source_records(paths)))


def git_fingerprint() -> dict[str, object]:
    status_raw = run(
        [
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ]
    ).stdout
    index_raw = run(["git", "ls-files", "-s", "-z"]).stdout.encode("utf-8")
    return {
        "branch": git_text("branch", "--show-current"),
        "clean": status_raw == "",
        "commit": git_text("rev-parse", "HEAD"),
        "index_sha256": sha256_bytes(index_raw),
        "source_sha256": source_fingerprint(release_source_paths()),
        "status_sha256": sha256_bytes(status_raw.encode("utf-8")),
        "tree": git_text("rev-parse", "HEAD^{tree}"),
    }


def source_only_fingerprint(
    expected_manifest: dict[str, Any],
) -> dict[str, object]:
    records = source_records(release_source_paths())
    expected = expected_manifest.get("files")
    if not isinstance(expected, list):
        fail("expected source manifest has no files array")
    if records != expected:
        fail("source-only tree differs from the expected archive manifest")
    return {
        "clean": True,
        "commit": None,
        "source_sha256": sha256_bytes(canonical_json_bytes(records)),
        "tree": None,
    }


def verify_expected_source_manifest(
    path: Path,
    manifest: dict[str, Any],
) -> None:
    if manifest.get("schema_version") != (
        "trackb-source-archive-manifest-v1"
    ):
        fail("expected source manifest schema is unsupported")
    if manifest.get("archive_prefix") != ARCHIVE_PREFIX:
        fail("expected source manifest archive prefix changed")
    files = manifest.get("files")
    if not isinstance(files, list) or manifest.get("file_count") != len(files):
        fail("expected source manifest file inventory is inconsistent")
    if path.read_bytes() != canonical_json_bytes(manifest):
        fail("expected source manifest is not canonical JSON")
    verify_no_private_path_bytes(
        path.read_bytes(), "expected source manifest"
    )


def verify_git_identity(arguments: argparse.Namespace) -> dict[str, object]:
    git_marker = ROOT / ".git"
    if git_marker.is_symlink():
        fail("Git validation mode forbids a symlinked .git marker")
    if not git_marker.exists():
        fail("Git validation mode requires .git metadata")
    if git_text("rev-parse", "--show-toplevel") != str(ROOT.resolve()):
        fail("release gate is not running at the Git worktree root")

    fingerprint = git_fingerprint()
    if not fingerprint["clean"]:
        fail("release candidate must be exactly clean")
    if fingerprint["commit"] != arguments.expected_commit:
        fail(
            "commit mismatch: expected "
            f"{arguments.expected_commit}, found {fingerprint['commit']}"
        )
    if fingerprint["tree"] != arguments.expected_tree:
        fail(
            "tree mismatch: expected "
            f"{arguments.expected_tree}, found {fingerprint['tree']}"
        )
    if (
        arguments.expected_branch is not None
        and fingerprint["branch"] != arguments.expected_branch
    ):
        fail(
            "branch mismatch: expected "
            f"{arguments.expected_branch}, found {fingerprint['branch']}"
        )
    remote = git_text("remote", "get-url", "origin")
    if remote != arguments.expected_remote:
        fail(
            f"origin mismatch: expected {arguments.expected_remote}, "
            f"found {remote}"
        )

    alternates_path = Path(
        git_text("rev-parse", "--git-path", "objects/info/alternates")
    )
    if not alternates_path.is_absolute():
        alternates_path = ROOT / alternates_path
    if alternates_path.exists() and alternates_path.read_bytes().strip():
        fail("local Git object alternates are forbidden")

    return {
        "before_fingerprint": fingerprint,
        "branch": fingerprint["branch"],
        "clean": True,
        "commit": fingerprint["commit"],
        "mode": "git",
        "no_local_alternates": True,
        "remote": remote,
        "tree": fingerprint["tree"],
    }


def verify_source_only_identity(
    arguments: argparse.Namespace,
    expected_manifest: dict[str, Any],
) -> dict[str, object]:
    git_marker = ROOT / ".git"
    if git_marker.exists() or git_marker.is_symlink():
        fail("source-only validation forbids .git metadata")
    if (ROOT / ".lake").exists():
        fail("source-only validation must begin without .lake")
    fingerprint = source_only_fingerprint(expected_manifest)
    return {
        "before_fingerprint": fingerprint,
        "branch": None,
        "clean": True,
        "commit": arguments.expected_commit,
        "mode": "source-only",
        "no_local_alternates": True,
        "remote": arguments.expected_remote,
        "tree": arguments.expected_tree,
    }


def strip_lean_comments_and_strings(text: str) -> str:
    """Blank Lean comments and strings while preserving token separation."""

    output: list[str] = []
    index = 0
    block_depth = 0
    in_string = False
    while index < len(text):
        if block_depth:
            if text.startswith("/-", index):
                block_depth += 1
                output.extend("  ")
                index += 2
            elif text.startswith("-/", index):
                block_depth -= 1
                output.extend("  ")
                index += 2
            else:
                output.append("\n" if text[index] == "\n" else " ")
                index += 1
            continue
        if in_string:
            character = text[index]
            if character == "\\" and index + 1 < len(text):
                output.extend("  ")
                index += 2
            elif character == '"':
                output.append(" ")
                index += 1
                in_string = False
            else:
                output.append("\n" if character == "\n" else " ")
                index += 1
            continue
        if text.startswith("/-", index):
            block_depth = 1
            output.extend("  ")
            index += 2
        elif text.startswith("--", index):
            while index < len(text) and text[index] != "\n":
                output.append(" ")
                index += 1
        elif text[index] == '"':
            in_string = True
            output.append(" ")
            index += 1
        else:
            output.append(text[index])
            index += 1
    if block_depth or in_string:
        fail("unterminated Lean comment or string during hygiene scan")
    return "".join(output)


def verify_lean_hygiene() -> dict[str, object]:
    token_pattern = re.compile(
        r"(?<![A-Za-z0-9_'])(sorry|admit|axiom|unsafe|native_decide)"
        r"(?![A-Za-z0-9_'])"
    )
    for filename in sorted(OWNED_LEAN_SOURCES):
        cleaned = strip_lean_comments_and_strings(
            (ROOT / filename).read_text(encoding="utf-8")
        )
        match = token_pattern.search(cleaned)
        if match:
            line = cleaned.count("\n", 0, match.start()) + 1
            fail(
                f"prohibited Lean token {match.group(1)!r} "
                f"in owned module {filename}:{line}"
            )

    inventory_cleaned = strip_lean_comments_and_strings(
        (ROOT / "TheoremInventory.lean").read_text(encoding="utf-8")
    )
    inventory_tokens = token_pattern.findall(inventory_cleaned)
    if any(
        token in {"sorry", "admit", "axiom", "native_decide"}
        for token in inventory_tokens
    ):
        fail("inventory tooling contains an unjustified prohibited Lean token")
    unsafe_names = set(
        re.findall(
            r"(?<![A-Za-z0-9_'])unsafe\s+def\s+"
            r"([A-Za-z_][A-Za-z0-9_']*)",
            inventory_cleaned,
        )
    )
    if unsafe_names != JUSTIFIED_INVENTORY_UNSAFE_DEFS:
        fail(
            "inventory-tool unsafe declarations changed: "
            f"expected {sorted(JUSTIFIED_INVENTORY_UNSAFE_DEFS)}, "
            f"found {sorted(unsafe_names)}"
        )
    if inventory_tokens.count("unsafe") != len(
        JUSTIFIED_INVENTORY_UNSAFE_DEFS
    ):
        fail("inventory tooling has an unreviewed unsafe use")
    return {
        "audit_tool_unsafe_declarations": sorted(unsafe_names),
        "audit_tool_unsafe_justified": True,
        "owned_module_prohibited_tokens": [],
        "result": "PASS",
    }


def verify_source_boundary(
    arguments: argparse.Namespace,
) -> dict[str, object]:
    observed_lean = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*.lean")
        if ".git" not in path.relative_to(ROOT).parts
        and ".lake" not in path.relative_to(ROOT).parts
    }
    if observed_lean != EXPECTED_LEAN_SOURCES:
        fail(
            "Lean source boundary changed: expected "
            f"{sorted(EXPECTED_LEAN_SOURCES)}, found {sorted(observed_lean)}"
        )

    paths = release_source_paths()
    if arguments.require_no_lake_at_start and (ROOT / ".lake").exists():
        fail("validation tree must begin without .lake")

    manifest = load_json(ROOT / "lake-manifest.json", "Lake manifest")
    if manifest.get("name") != "trackb_lean_replay_checker":
        fail("Lake manifest project name mismatch")
    if manifest.get("packages") != []:
        fail("unexpected Lake dependency or sibling path dependency")

    lakefile_digest = sha256_file(ROOT / "lakefile.toml")
    if lakefile_digest != EXPECTED_LAKEFILE_SHA256:
        fail(
            "Lake configuration differs from the reviewed exact target graph"
        )

    tracked_or_manifest_paths: set[str]
    if arguments.source_only:
        expected_manifest = load_json(
            arguments.expected_source_manifest.resolve(),
            "expected source manifest",
        )
        entries = expected_manifest.get("files")
        if not isinstance(entries, list):
            fail("expected source manifest files must be an array")
        tracked_or_manifest_paths = {
            entry.get("path")
            for entry in entries
            if isinstance(entry, dict) and isinstance(entry.get("path"), str)
        }
    else:
        tracked_or_manifest_paths = set(
            run(["git", "ls-files", "-z"]).stdout.rstrip("\0").split("\0")
        )
        tracked_or_manifest_paths.discard("")

    forbidden_tracked = sorted(
        relative
        for relative in tracked_or_manifest_paths
        if excluded_release_path(PurePosixPath(relative))
    )
    if forbidden_tracked:
        fail(f"tracked/generated artifacts are forbidden: {forbidden_tracked}")

    for path in paths:
        raw = path.read_bytes()
        verify_no_private_path_bytes(
            raw,
            "release source "
            f"{path.relative_to(ROOT).as_posix()}",
        )

    fixture_hashes: dict[str, str] = {}
    for relative, expected in EXPECTED_FIXTURE_SHA256.items():
        path = ROOT / relative
        if not path.is_file():
            fail(f"required guarded fixture is missing: {relative}")
        observed = sha256_file(path)
        if observed != expected:
            fail(
                f"guarded fixture hash mismatch for {relative}: "
                f"expected {expected}, found {observed}"
            )
        fixture_hashes[relative] = observed

    hygiene = verify_lean_hygiene()
    return {
        "file_count": len(paths),
        "fixture_hashes": fixture_hashes,
        "lean_sources": sorted(EXPECTED_LEAN_SOURCES),
        "no_absolute_private_paths": True,
        "no_generated_tracked_material": True,
        "no_sibling_dependencies": True,
        "no_symlinks": True,
        "lakefile_sha256": lakefile_digest,
        "source_hygiene": hygiene,
    }


def verify_toolchain() -> dict[str, str]:
    toolchain = (ROOT / "lean-toolchain").read_text(
        encoding="utf-8"
    ).strip()
    if toolchain != EXPECTED_TOOLCHAIN:
        fail(
            f"toolchain mismatch: expected {EXPECTED_TOOLCHAIN}, "
            f"found {toolchain}"
        )
    lean_version = run(["lean", "--version"]).stdout.strip()
    if "Lean (version 4.32.1" not in lean_version:
        fail(f"unexpected Lean version: {lean_version}")
    if EXPECTED_LEAN_COMMIT not in lean_version:
        fail(f"unexpected Lean commit: {lean_version}")
    lake_version = run(["lake", "--version"]).stdout.strip()
    if lake_version != EXPECTED_LAKE_VERSION:
        fail(
            f"Lake version mismatch: expected {EXPECTED_LAKE_VERSION}, "
            f"found {lake_version}"
        )
    return {
        "lake": lake_version,
        "lean": lean_version,
        "lean_commit": EXPECTED_LEAN_COMMIT,
        "pin": toolchain,
    }


def build_all_targets() -> dict[str, object]:
    completed = run(["lake", "build"])
    output = completed.stdout + completed.stderr
    warnings = [
        line for line in output.splitlines() if "warning:" in line.lower()
    ]
    if warnings:
        fail(f"unapproved Lean build warnings: {warnings}")
    return {
        "command": "lake build",
        "result": "PASS",
        "warning_count": 0,
    }


def verify_guarded_fixture_correspondence() -> dict[str, object]:
    checker = (
        ROOT
        / ".lake"
        / "build"
        / "bin"
        / "trackb-guarded-fixture-check"
    )
    if not checker.is_file():
        fail("guarded fixture correspondence executable is missing")
    results: list[dict[str, str]] = []
    for relative in EXPECTED_FIXTURE_SHA256:
        completed = run([str(checker), str(ROOT / relative)])
        output = completed.stdout + completed.stderr
        if "model=exact" not in output:
            fail(
                "guarded fixture correspondence marker is missing for "
                f"{relative}"
            )
        results.append({"fixture": relative, "result": "PASS"})
    return {"result": "PASS", "fixtures": results}


def export_and_verify_inventory(
    temporary_root: Path,
) -> tuple[dict[str, Any], dict[str, object]]:
    generated_root = temporary_root / "inventory"
    generated_root.mkdir()
    generated_json = generated_root / "theorem_inventory.json"
    generated_sha = generated_root / "theorem_inventory.sha256"
    completed = run(
        [
            sys.executable,
            "scripts/export_theorem_inventory.py",
            "--project-root",
            str(ROOT),
            "--output",
            str(generated_json),
            "--sha256-output",
            str(generated_sha),
        ]
    )
    if "THEOREM_INVENTORY=PASS" not in (
        completed.stdout + completed.stderr
    ):
        fail("theorem inventory wrapper did not report PASS")

    reviewed_json = ROOT / "validation" / "theorem_inventory.json"
    reviewed_sha = ROOT / "validation" / "theorem_inventory.sha256"
    if generated_json.read_bytes() != reviewed_json.read_bytes():
        fail(
            "environment-derived theorem inventory differs from the "
            "reviewed inventory"
        )
    if generated_sha.read_bytes() != reviewed_sha.read_bytes():
        fail("theorem inventory digest receipt differs from reviewed bytes")

    inventory = load_json(generated_json, "theorem inventory")
    if inventory.get("schemaVersion") != "trackb-theorem-inventory-v1":
        fail("unexpected theorem inventory schema")
    checks = inventory.get("checks")
    if not isinstance(checks, dict) or checks.get("result") != "PASS":
        fail("environment theorem inventory gate did not pass")
    required_check_values = {
        "allOwnedConstantAxiomGatePassed": True,
        "authoredAxiomGatePassed": True,
        "axiomGatePassed": True,
        "fullNamesDistinct": True,
        "manifestPassed": True,
        "ownedModulesLoaded": True,
        "theoremAxiomGatePassed": True,
        "unsafeDeclarationGatePassed": True,
    }
    for key, expected in required_check_values.items():
        if checks.get(key) is not expected:
            fail(f"theorem inventory check failed: {key}")
    if set(inventory.get("allowedAxioms", [])) != ALLOWED_AXIOMS:
        fail("theorem inventory axiom allowlist changed")
    if set(inventory.get("ownedModules", [])) != EXPECTED_OWNED_MODULES:
        fail("theorem inventory owned-module surface changed")
    if set(inventory.get("importedModules", [])) != EXPECTED_IMPORT_ROOTS:
        fail("theorem inventory import-root surface changed")
    if inventory.get("ownedAxioms") != []:
        fail("owned axiom declaration discovered")
    if inventory.get("unsafeDeclarations") != []:
        fail("unsafe declaration discovered in an owned module")
    if inventory.get("unloadedOwnedModules") != []:
        fail("an owned module was not loaded")
    if inventory.get("axiomOffendingConstants") != []:
        fail("a forbidden axiom occurs in an owned constant")

    theorems = inventory.get("theorems")
    if not isinstance(theorems, list):
        fail("theorem inventory has no theorem array")
    theorem_count = inventory.get("theoremCount")
    authored_count = inventory.get("authoredTheoremCount")
    generated_count = inventory.get("generatedTheoremCount")
    if theorem_count != len(theorems):
        fail("environment theorem count does not match inventory records")
    if not isinstance(authored_count, int) or not isinstance(
        generated_count, int
    ):
        fail("theorem inventory count fields are invalid")
    if authored_count + generated_count != theorem_count:
        fail("authored/generated theorem counts do not partition inventory")

    identities: set[tuple[str, str]] = set()
    theorem_by_name: dict[str, dict[str, Any]] = {}
    axiom_results: list[dict[str, object]] = []
    for entry in theorems:
        if not isinstance(entry, dict):
            fail("theorem inventory entry is not an object")
        name = entry.get("name")
        origin = entry.get("originModule")
        if not isinstance(name, str) or not isinstance(origin, str):
            fail("theorem inventory identity is incomplete")
        if origin not in EXPECTED_OWNED_MODULES:
            fail(f"theorem has a foreign owned-module origin: {name}")
        identity = (origin, name)
        if identity in identities:
            fail(f"duplicate theorem identity: {identity}")
        identities.add(identity)
        if name in theorem_by_name:
            fail(f"duplicate full theorem name: {name}")
        theorem_by_name[name] = entry
        type_representation = entry.get("typeRepresentation")
        if not isinstance(type_representation, str) or not type_representation:
            fail(f"theorem has no canonical type representation: {name}")
        if entry.get("typeRepresentationFormat") != "Lean.Expr.repr-v1":
            fail(f"theorem type representation format changed: {name}")
        authored = entry.get("authoredDeclaration")
        if not isinstance(authored, bool) or entry.get("authored") is not authored:
            fail(f"theorem authorship fields are inconsistent: {name}")
        provenance = entry.get("environmentProvenance")
        if not isinstance(provenance, dict):
            fail(f"theorem has no environment provenance: {name}")
        if set(provenance) != {
            "exactDeclarationRange",
            "generatedProjection",
            "kind",
        }:
            fail(f"theorem environment provenance shape changed: {name}")
        if not isinstance(provenance.get("exactDeclarationRange"), bool):
            fail(f"invalid declaration-range evidence: {name}")
        if not isinstance(provenance.get("generatedProjection"), bool):
            fail(f"invalid generated-projection evidence: {name}")
        expected_kind = "authored" if authored else "generated"
        if provenance.get("kind") != expected_kind:
            fail(f"theorem environment provenance kind is inconsistent: {name}")
        if authored and (
            provenance.get("exactDeclarationRange") is not True
            or provenance.get("generatedProjection") is not False
        ):
            fail(f"authored theorem lacks exact environment evidence: {name}")
        classification = entry.get("classification")
        if not isinstance(classification, dict) or set(classification) != {
            "category",
            "exampleTheorem",
            "externallyCited",
            "internalHelper",
            "publicApi",
        }:
            fail(f"theorem classification shape changed: {name}")
        classification_flags = {
            key: classification.get(key)
            for key in (
                "exampleTheorem",
                "externallyCited",
                "internalHelper",
                "publicApi",
            )
        }
        if any(not isinstance(value, bool) for value in classification_flags.values()):
            fail(f"theorem classification flag is not Boolean: {name}")
        primary_flags = (
            classification_flags["publicApi"],
            classification_flags["internalHelper"],
            classification_flags["exampleTheorem"],
        )
        if authored:
            if sum(primary_flags) != 1:
                fail(f"authored theorem classification is not a partition: {name}")
            expected_category = (
                "internal_helper"
                if classification_flags["internalHelper"]
                else (
                    "example_theorem"
                    if classification_flags["exampleTheorem"]
                    else "public_api"
                )
            )
        else:
            if any(classification_flags.values()):
                fail(f"generated theorem has an authored classification: {name}")
            expected_category = "generated"
        if classification.get("category") != expected_category:
            fail(f"theorem classification category is inconsistent: {name}")
        axioms = entry.get("transitiveAxioms")
        if not isinstance(axioms, list) or any(
            not isinstance(axiom, str) for axiom in axioms
        ):
            fail(f"invalid axiom evidence for theorem: {name}")
        if axioms != sorted(set(axioms)):
            fail(f"theorem axiom evidence is not sorted and unique: {name}")
        forbidden = set(axioms) - ALLOWED_AXIOMS
        if forbidden:
            fail(
                f"forbidden transitive axioms for {name}: "
                f"{sorted(forbidden)}"
            )
        axiom_results.append(
            {
                "name": name,
                "origin_module": origin,
                "authored": authored,
                "classification": classification,
                "result": "PASS",
                "transitive_axioms": axioms,
                "type_digest": sha256_bytes(
                    type_representation.encode("utf-8")
                ),
            }
        )

    formal_results: dict[str, str] = {}
    for role, theorem_name in REQUIRED_FORMAL_THEOREMS.items():
        entry = theorem_by_name.get(theorem_name)
        if entry is None:
            fail(f"required formal theorem is absent: {theorem_name}")
        if entry.get("authoredDeclaration") is not True:
            fail(f"required theorem is not authored: {theorem_name}")
        classification = entry.get("classification")
        if not isinstance(classification, dict) or (
            classification.get("externallyCited") is not True
        ):
            fail(
                "required theorem is not on the reviewed externally cited "
                f"surface: {theorem_name}"
            )
        formal_results[role] = "PASS"

    fixture_theorem_results: dict[str, list[str]] = {}
    for fixture, theorem_names in FIXTURE_THEOREM_BINDINGS.items():
        for theorem_name in theorem_names:
            entry = theorem_by_name.get(theorem_name)
            if entry is None or entry.get("authoredDeclaration") is not True:
                fail(
                    "guarded fixture is not bound to its authored theorem: "
                    f"{fixture}: {theorem_name}"
                )
        fixture_theorem_results[fixture] = list(theorem_names)

    digest = sha256_file(reviewed_json)
    expected_sha_line = f"{digest}  theorem_inventory.json\n"
    if reviewed_sha.read_text(encoding="utf-8") != expected_sha_line:
        fail("reviewed theorem inventory SHA-256 file is malformed")
    return inventory, {
        "allowed_axioms": sorted(ALLOWED_AXIOMS),
        "authored_theorem_count": authored_count,
        "axiom_results": axiom_results,
        "formal_results": formal_results,
        "fixture_theorem_bindings": fixture_theorem_results,
        "generated_theorem_count": generated_count,
        "path": "validation/theorem_inventory.json",
        "result": "PASS",
        "sha256": digest,
        "sha256_path": "validation/theorem_inventory.sha256",
        "theorem_count": theorem_count,
    }


def run_python_tests() -> dict[str, object]:
    environment = release_environment()
    completed = run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-v",
        ],
        env=environment,
    )
    output = completed.stdout + completed.stderr
    counts = re.findall(
        r"^Ran ([0-9]+) tests? in ", output, re.MULTILINE
    )
    if len(counts) != 1:
        fail("Python test count is missing or ambiguous")
    if len(re.findall(r"^OK$", output, re.MULTILINE)) != 1:
        fail("Python tests did not finish with one unqualified OK")
    disallowed_status = re.search(
        r"(FAILED|skipped=|expected failures=|unexpected successes=)",
        output,
        re.IGNORECASE,
    )
    if disallowed_status:
        fail(
            "Python release tests contain a qualified or failing status: "
            f"{disallowed_status.group(1)}"
        )
    observed_test_ids = {
        f"{qualified}.{method}"
        for method, qualified in re.findall(
            r"^([A-Za-z0-9_]+) \(([^)]+)\) \.\.\. ok$",
            output,
            re.MULTILINE,
        )
    }
    if observed_test_ids != EXPECTED_TEST_IDS:
        fail(
            "reviewed Python test inventory changed: "
            f"missing={sorted(EXPECTED_TEST_IDS - observed_test_ids)}, "
            f"extra={sorted(observed_test_ids - EXPECTED_TEST_IDS)}"
        )
    if int(counts[0]) != len(observed_test_ids):
        fail("reported Python test count differs from observed test IDs")
    module_counts = Counter(
        test_id.split(".", 1)[0] for test_id in observed_test_ids
    )
    required_suite_results = {
        "bounded_result_emission": (
            "PASS"
            if module_counts["test_bounded_result_emission"] == 6
            else "FAIL"
        ),
        "hostile_theorem_inventory": (
            "PASS"
            if module_counts["test_theorem_inventory_gate"] == 10
            else "FAIL"
        ),
        "z3_witness_proposer": (
            "PASS"
            if module_counts["test_z3_witness_proposer"] == 8
            else "FAIL"
        ),
    }
    if set(required_suite_results.values()) != {"PASS"}:
        fail(f"a required Python test suite did not execute: {module_counts}")
    return {
        "command": "python -m unittest discover -s tests -v",
        "count": int(counts[0]),
        "module_counts": dict(sorted(module_counts.items())),
        "result": "PASS",
        "reviewed_test_ids_sha256": sha256_bytes(
            canonical_json_bytes(sorted(observed_test_ids))
        ),
        "required_suites": required_suite_results,
        "skips": 0,
    }


def verify_validation_reports() -> dict[str, dict[str, object]]:
    specifications = {
        "bounded_output": (
            "validation/bounded_result_emission_report.json",
            "trackb.bounded-result-emission-report.v1",
        ),
        "hostile_inventory": (
            "validation/hostile_theorem_inventory_report.json",
            "trackb.hostile-theorem-inventory-report.v1",
        ),
    }
    reports: dict[str, dict[str, object]] = {}
    for key, (relative, schema) in specifications.items():
        path = ROOT / relative
        payload = load_json(path, f"{key} validation report")
        if payload.get("schema_version") != schema:
            fail(f"unexpected schema for {relative}")
        if payload.get("result") != "PASS":
            fail(f"validation report did not pass: {relative}")
        if payload.get("release_version") != VERSION:
            fail(f"validation report version mismatch: {relative}")
        reports[key] = {
            "path": relative,
            "result": "PASS",
            "sha256": sha256_file(path),
        }
    return reports


def verify_documentation_claims() -> dict[str, object]:
    documents: dict[str, str] = {}
    for relative in CURRENT_CLAIM_DOCUMENTS:
        path = ROOT / relative
        if not path.is_file():
            fail(f"required current-claim document is missing: {relative}")
        documents[relative] = path.read_text(encoding="utf-8")

    combined = "\n".join(documents.values())
    required_phrases = (
        "initial-containing, non-forbidden, successor-closed",
        "semanticCheck_sound",
        "metadataCheck_iff",
        "environment",
    )
    for phrase in required_phrases:
        if phrase not in combined:
            fail(f"required documentation claim is absent: {phrase}")
    decision = documents["docs/BOUNDED_RESULT_CHECKER_DECISION.md"]
    if "DEFERRED" not in decision:
        fail("bounded checker disposition is not explicitly deferred")

    current_release_text = combined
    stale_claims = (
        "all 44 explicit theorem",
        "44 remaining explicit theorem",
        "source theorem inventory with that gate",
    )
    for stale in stale_claims:
        if stale in current_release_text:
            fail(f"stale theorem-gate claim remains: {stale}")
    forbidden_claim_patterns = (
        (
            r"SAFE_WITHIN_BOUND.{0,120}"
            r"(?:proves|means|establishes).{0,30}"
            r"(?:global|unbounded|all-depth) safety",
            "bounded safety as global safety",
        ),
        (
            r"bounded safety\s+is\s+global safety",
            "bounded safety as global safety",
        ),
        (
            r"TrackB.{0,40}(?:proves|formalizes).{0,30}"
            r"(?:ReplayGuard|Evidence-to-Action|E2A)",
            "an external project as a TrackB theorem",
        ),
        (
            r"every (?:supplied )?certificate member is reachable",
            "all supplied certificate members as reachable",
        ),
        (
            r"reachable-state certificate",
            "the imprecise reachable-state certificate label",
        ),
    )
    for pattern, description in forbidden_claim_patterns:
        if re.search(
            pattern,
            current_release_text,
            re.IGNORECASE | re.DOTALL,
        ):
            fail(f"documentation overstates {description}")
    return {
        "bounded_checker_disposition": "DEFERRED",
        "documents": list(CURRENT_CLAIM_DOCUMENTS),
        "result": "PASS",
    }


def parse_archive_builder_output(
    completed: subprocess.CompletedProcess[str],
) -> dict[str, Any]:
    lines = [
        line
        for line in (completed.stdout + completed.stderr).splitlines()
        if line.strip()
    ]
    if not lines:
        fail("source archive builder produced no result")
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError as error:
        fail(f"invalid source archive builder output: {error}")
    if not isinstance(payload, dict) or payload.get("result") != "PASS":
        fail("source archive builder did not report PASS")
    return payload


def build_source_archive(output: Path, manifest_output: Path) -> dict[str, Any]:
    completed = run(
        [
            sys.executable,
            "scripts/build_source_archive.py",
            "--output",
            str(output),
            "--manifest-output",
            str(manifest_output),
            "--prefix",
            ARCHIVE_PREFIX,
        ]
    )
    return parse_archive_builder_output(completed)


def verify_archive_bytes(
    archive_path: Path,
    manifest_path: Path,
    expected_records: list[dict[str, object]],
) -> dict[str, object]:
    manifest = load_json(manifest_path, "source archive manifest")
    if manifest.get("schema_version") != (
        "trackb-source-archive-manifest-v1"
    ):
        fail("unexpected source archive manifest schema")
    if manifest.get("archive_prefix") != ARCHIVE_PREFIX:
        fail("unexpected source archive prefix")
    records = manifest.get("files")
    if records != expected_records:
        fail("source archive manifest differs from the exact source set")
    if manifest.get("file_count") != len(expected_records):
        fail("source archive manifest file count is inconsistent")
    if manifest_path.read_bytes() != canonical_json_bytes(manifest):
        fail("source archive manifest is not canonical JSON")

    expected_by_path = {
        record["path"]: record for record in expected_records
    }
    observed_paths: set[str] = set()
    with tarfile.open(archive_path, mode="r:gz") as archive:
        members = archive.getmembers()
        if len(members) != len(expected_records):
            fail("source archive member count is inconsistent")
        for member in members:
            if not member.isreg():
                fail(f"source archive contains a non-regular file: {member.name}")
            member_path = PurePosixPath(member.name)
            if (
                member_path.is_absolute()
                or ".." in member_path.parts
                or len(member_path.parts) < 2
                or member_path.parts[0] != ARCHIVE_PREFIX
            ):
                fail(f"unsafe source archive path: {member.name}")
            relative = PurePosixPath(*member_path.parts[1:]).as_posix()
            if excluded_release_path(PurePosixPath(relative)):
                fail(f"generated or metadata path entered archive: {relative}")
            if relative in observed_paths:
                fail(f"duplicate source archive path: {relative}")
            observed_paths.add(relative)
            expected = expected_by_path.get(relative)
            if expected is None:
                fail(f"unexpected source archive member: {relative}")
            handle = archive.extractfile(member)
            if handle is None:
                fail(f"cannot read source archive member: {relative}")
            raw = handle.read()
            verify_no_private_path_bytes(
                raw, f"source archive member {relative}"
            )
            if len(raw) != expected["size"]:
                fail(f"source archive size mismatch: {relative}")
            if sha256_bytes(raw) != expected["sha256"]:
                fail(f"source archive digest mismatch: {relative}")
            if f"{member.mode & 0o777:04o}" != expected["mode"]:
                fail(f"source archive mode mismatch: {relative}")
            if (
                member.uid != 0
                or member.gid != 0
                or member.mtime != 0
                or member.uname != ""
                or member.gname != ""
            ):
                fail(f"nondeterministic archive metadata: {relative}")
    if observed_paths != set(expected_by_path):
        fail("source archive member set differs from source manifest")
    return {
        "filename": archive_path.name,
        "file_count": len(expected_records),
        "manifest_filename": manifest_path.name,
        "manifest_sha256": sha256_file(manifest_path),
        "result": "PASS",
        "sha256": sha256_file(archive_path),
    }


def verify_archive_source_equivalence(
    arguments: argparse.Namespace,
    expected_manifest: dict[str, Any] | None,
) -> list[dict[str, object]]:
    records = source_records(release_source_paths())
    paths = {record["path"] for record in records}
    if arguments.source_only:
        if expected_manifest is None:
            fail("source-only mode has no expected source manifest")
        expected_records = expected_manifest.get("files")
        if records != expected_records:
            fail("source-only archive source set changed during validation")
    else:
        tracked = set(
            run(["git", "ls-files", "-z"]).stdout.rstrip("\0").split("\0")
        )
        tracked.discard("")
        if paths != tracked:
            fail(
                "source archive set differs from exact Git tracked set: "
                f"missing={sorted(tracked - paths)}, "
                f"extra={sorted(paths - tracked)}"
            )
    return records


def construct_and_verify_archive(
    arguments: argparse.Namespace,
    temporary_root: Path,
    expected_manifest: dict[str, Any] | None,
) -> dict[str, object]:
    if arguments.archive_output is None:
        archive_path = temporary_root / (
            "trackb-lean-replay-checker-v0.2.1-source.tar.gz"
        )
        manifest_path = temporary_root / (
            "trackb-lean-replay-checker-v0.2.1-source-manifest.json"
        )
    else:
        archive_path = ensure_outside_root(
            arguments.archive_output, "archive output"
        )
        manifest_path = ensure_outside_root(
            arguments.archive_manifest_output, "archive manifest output"
        )

    second_archive = temporary_root / "determinism-check.tar.gz"
    second_manifest = temporary_root / "determinism-check-manifest.json"
    build_source_archive(archive_path, manifest_path)
    build_source_archive(second_archive, second_manifest)
    if archive_path.read_bytes() != second_archive.read_bytes():
        fail("two source archive builds are not byte-identical")
    if manifest_path.read_bytes() != second_manifest.read_bytes():
        fail("two source archive manifests are not byte-identical")

    expected_records = verify_archive_source_equivalence(
        arguments, expected_manifest
    )
    result = verify_archive_bytes(
        archive_path, manifest_path, expected_records
    )
    result["deterministic_rebuild"] = "PASS"
    result["exact_source_equivalence"] = "PASS"
    result["no_cache_files"] = True
    result["no_git"] = True
    result["no_lake"] = True
    result["path_and_symlink_safety"] = "PASS"
    if arguments.source_only:
        if (
            result["sha256"]
            != arguments.expected_source_archive_sha256
        ):
            fail(
                "source-only regenerated archive differs from the "
                "expected deterministic archive"
            )
        if (
            result["manifest_sha256"]
            != arguments.expected_source_manifest_sha256
        ):
            fail(
                "source-only regenerated manifest differs from the "
                "expected archive-content manifest"
            )
        result["matches_expected_archive"] = "PASS"
        result["matches_expected_manifest"] = "PASS"
    return result


def verify_final_fingerprint(
    arguments: argparse.Namespace,
    repository: dict[str, object],
    expected_manifest: dict[str, Any] | None,
) -> dict[str, object]:
    if arguments.source_only:
        if expected_manifest is None:
            fail("source-only mode has no expected source manifest")
        after = source_only_fingerprint(expected_manifest)
    else:
        after = git_fingerprint()
    before = repository["before_fingerprint"]
    if after != before:
        fail(
            "worktree/source fingerprint changed during release validation"
        )
    return after


def module_hashes() -> list[dict[str, str]]:
    return [
        {
            "path": filename,
            "sha256": sha256_file(ROOT / filename),
        }
        for filename in sorted(EXPECTED_LEAN_SOURCES)
    ]


def main() -> int:
    arguments = parse_arguments()
    started_at = utc_now()
    try:
        invocation_environment = verify_invocation_environment()
        expected_manifest: dict[str, Any] | None = None
        if arguments.source_only:
            if arguments.expected_source_manifest.is_symlink():
                fail("expected source manifest must not be a symlink")
            expected_manifest_path = arguments.expected_source_manifest.resolve()
            if not expected_manifest_path.is_file():
                fail("expected source manifest does not exist")
            if sha256_file(expected_manifest_path) != (
                arguments.expected_source_manifest_sha256
            ):
                fail("expected source manifest SHA-256 mismatch")
            expected_manifest = load_json(
                expected_manifest_path,
                "expected source manifest",
            )
            verify_expected_source_manifest(
                expected_manifest_path, expected_manifest
            )

        repository = (
            verify_source_only_identity(arguments, expected_manifest)
            if arguments.source_only
            else verify_git_identity(arguments)
        )
        prebuild_tree = verify_prebuild_clean_tree()
        source_boundary = verify_source_boundary(arguments)
        source_boundary["prebuild_tree"] = prebuild_tree
        source_boundary["sanitized_environment_keys"] = sorted(
            SANITIZED_ENVIRONMENT_KEYS
        )
        source_boundary["invocation_environment"] = invocation_environment
        source_boundary["private_path_policy"] = verify_private_path_policy()
        toolchain = verify_toolchain()
        build = build_all_targets()
        fixture_correspondence = verify_guarded_fixture_correspondence()

        with tempfile.TemporaryDirectory(
            prefix="trackb-release-gate-"
        ) as temporary:
            temporary_root = Path(temporary)
            inventory, inventory_summary = export_and_verify_inventory(
                temporary_root
            )
            fixture_correspondence["theorem_bindings"] = (
                inventory_summary["fixture_theorem_bindings"]
            )
            tests = run_python_tests()
            validation_reports = verify_validation_reports()
            documentation = verify_documentation_claims()
            archive = construct_and_verify_archive(
                arguments, temporary_root, expected_manifest
            )

        postbuild_tree = verify_postbuild_clean_tree()
        source_boundary["postbuild_tree"] = postbuild_tree
        after_fingerprint = verify_final_fingerprint(
            arguments, repository, expected_manifest
        )
        repository["after_fingerprint"] = after_fingerprint
        formal_results = inventory_summary["formal_results"]
        source_boundary["result"] = "PASS"
        validation_evidence = sorted(
            [
                {
                    "path": inventory_summary["path"],
                    "sha256": inventory_summary["sha256"],
                },
                {
                    "path": validation_reports["bounded_output"]["path"],
                    "sha256": validation_reports["bounded_output"]["sha256"],
                },
                {
                    "path": validation_reports["hostile_inventory"]["path"],
                    "sha256": validation_reports[
                        "hostile_inventory"
                    ]["sha256"],
                },
            ],
            key=lambda entry: entry["path"],
        )
        summary: dict[str, object] = {
            "schema_version": GATE_SCHEMA,
            "result": "PASS",
            "started_at": started_at,
            "completed_at": utc_now(),
            "intended_version": "v0.2.1",
            "repository": repository,
            "toolchain": toolchain,
            "modules": module_hashes(),
            "theorem_inventory": inventory_summary,
            "checks": {
                "axioms": {
                    "result": "PASS",
                    "theorem_count": inventory_summary["theorem_count"],
                },
                "bounded_output_regression": {
                    "executed_test_count": tests["module_counts"][
                        "test_bounded_result_emission"
                    ],
                    "report_path": validation_reports[
                        "bounded_output"
                    ]["path"],
                    "result": validation_reports[
                        "bounded_output"
                    ]["result"],
                },
                "build": build,
                "documentation_claim_consistency": documentation,
                "fixture_correspondence": fixture_correspondence,
                "hostile_theorem_inventory": {
                    "executed_test_count": tests["module_counts"][
                        "test_theorem_inventory_gate"
                    ],
                    "report_path": validation_reports[
                        "hostile_inventory"
                    ]["path"],
                    "result": validation_reports[
                        "hostile_inventory"
                    ]["result"],
                },
                "metadata_theorem": {
                    "combined_checker_result": formal_results[
                        "combined_checker"
                    ],
                    "name": REQUIRED_FORMAL_THEOREMS[
                        "metadata_consistency"
                    ],
                    "result": formal_results["metadata_consistency"],
                },
                "semantic_theorem": {
                    "name": REQUIRED_FORMAL_THEOREMS[
                        "semantic_soundness"
                    ],
                    "result": formal_results["semantic_soundness"],
                },
                "source_boundary": source_boundary,
                "tests": tests,
            },
            "source_archive": archive,
            "claim_boundaries": {
                "UNSAFE": (
                    "UNSAFE is an exact native first-bad trace at or below "
                    "the configured bound that passed the replay checker."
                ),
                "SAFE_WITHIN_BOUND": (
                    "SAFE_WITHIN_BOUND excludes a semantic counterexample only "
                    "at or below the configured bound in the exact model."
                ),
                "GLOBALLY_SAFE": (
                    "GLOBALLY_SAFE is supported by an initial-containing, "
                    "non-forbidden, successor-closed finite certificate in "
                    "the exact model."
                ),
            },
            "bounded_checker_disposition": (
                "DEFERRED_TO_v0.2.2_OR_v0.3.0; "
                "REQUIRED_v0.2.1_IN_PROCESS_BINDING_PASS"
            ),
            "validation_reports": validation_evidence,
        }
        if inventory.get("checks", {}).get("result") != "PASS":
            fail("inventory result changed before summary emission")

        raw_summary = canonical_json_bytes(summary)
        if arguments.summary_output is not None:
            summary_path = ensure_outside_root(
                arguments.summary_output, "gate summary output"
            )
            atomic_write(summary_path, raw_summary)
            if summary_path.read_bytes() != raw_summary:
                fail("persisted gate summary changed after atomic write")
        if arguments.archive_output is not None:
            if sha256_file(arguments.archive_output.resolve()) != archive["sha256"]:
                fail("persisted source archive changed before PASS")
            if (
                sha256_file(arguments.archive_manifest_output.resolve())
                != archive["manifest_sha256"]
            ):
                fail("persisted source manifest changed before PASS")
        sys.stdout.write(
            "RELEASE_GATE=PASS "
            f"mode={repository['mode']} "
            f"theorems={inventory_summary['theorem_count']} "
            f"authored={inventory_summary['authored_theorem_count']} "
            f"tests={tests['count']} "
            f"archive_sha256={archive['sha256']} "
            f"inventory_sha256={inventory_summary['sha256']}\n"
        )
        return 0
    except (
        GateFailure,
        KeyError,
        OSError,
        tarfile.TarError,
        TypeError,
        ValueError,
    ) as error:
        sys.stderr.write(f"RELEASE_GATE=FAIL: {error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

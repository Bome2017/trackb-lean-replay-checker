#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
# SPDX-License-Identifier: Apache-2.0
"""Optional Z3 witness proposer with a mandatory Lean replay-check boundary.

This module is intentionally not a safety decision procedure.  Z3 may propose
an UNSAFE-shaped native result, but the public TrackB Lean replay checker must
accept the exact workflow/result bytes before this tool reports
``candidate_unsafe``.  UNSAT is advisory and is never translated to SAFE.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Sequence


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKER = PACKAGE_ROOT / ".lake" / "build" / "bin" / "trackb-replay-check"

PROPOSAL_SCHEMA = "trackb-z3-witness-proposal/0.2"
ENCODING_ID = "trackb-v0.1-boolean-z3-witness-proposal/1"
QUERY_DIGEST_KIND = "sha256-query-transcript-v1"

CANDIDATE_UNSAFE = "candidate_unsafe"
NO_CANDIDATE_ADVISORY = "no_candidate_advisory"
INCONCLUSIVE_UNKNOWN = "inconclusive_unknown"
ERROR = "error"
TIMEOUT = "timeout"

EXIT_OK = 0
EXIT_UNKNOWN = 20
EXIT_TIMEOUT = 21
EXIT_ERROR = 22
EXIT_COMPARISON_MISMATCH = 23

UNSAFE_CLAIM_BOUNDARY = (
    "UNSAFE means a bad replay exists within the configured bound and model "
    "assumptions. SAFE_WITHIN_BOUND does not prove global safety."
)

AUTHORITY_BOUNDARY = (
    "This status is produced by an optional witness proposer. It never proves "
    "SAFE. A candidate trace has authority only through the TrackB Lean replay "
    "checker applied to the exact workflow/result bytes."
)


@dataclass(frozen=True)
class EngineOutcome:
    """Result of the optional solver layer before the Lean authority boundary."""

    kind: str
    solver_version: str
    query_digest: str
    queried_depths: Sequence[int] = ()
    reason_unknown: Optional[str] = None
    candidate_result: Optional[dict[str, Any]] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class CheckerOutcome:
    """Captured invocation of the authoritative native replay checker."""

    exit_code: Optional[int]
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None
    timed_out: bool = False


@dataclass(frozen=True)
class PipelineOutcome:
    """Serializable proposal record, optional accepted candidate, and CLI code."""

    record: dict[str, Any]
    candidate_bytes: Optional[bytes]
    exit_code: int


class QueryTranscript:
    """Length-framed digest of query context and every SMT-LIB query attempted."""

    def __init__(self, workflow_digest: str, timeout_ms: int) -> None:
        self._digest = hashlib.sha256()
        context = json.dumps(
            {
                "encoding_id": ENCODING_ID,
                "timeout_ms_per_query": timeout_ms,
                "workflow_sha256": workflow_digest,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self._add_frame(b"context", context)

    def add_query(self, depth: int, smt2: str) -> None:
        self._add_frame(f"depth:{depth}".encode("ascii"), smt2.encode("utf-8"))

    def hexdigest(self) -> str:
        return self._digest.hexdigest()

    def _add_frame(self, label: bytes, payload: bytes) -> None:
        self._digest.update(len(label).to_bytes(8, "big"))
        self._digest.update(label)
        self._digest.update(len(payload).to_bytes(8, "big"))
        self._digest.update(payload)


class Z3WitnessEngine:
    """Proposal-only bounded encoder; it has no safety authority."""

    def propose(
        self,
        workflow: dict[str, Any],
        *,
        workflow_digest: str,
        timeout_ms: int,
    ) -> EngineOutcome:
        transcript = QueryTranscript(workflow_digest, timeout_ms)
        queried_depths: list[int] = []

        try:
            z3 = _load_z3()
        except Exception as exc:  # defensive boundary around an optional package
            return EngineOutcome(
                kind=ERROR,
                solver_version="unavailable",
                query_digest=transcript.hexdigest(),
                error=f"could not import optional z3-solver package: {exc}",
            )

        if z3 is None:
            return EngineOutcome(
                kind=ERROR,
                solver_version="unavailable",
                query_digest=transcript.hexdigest(),
                error=(
                    "z3-solver is not installed; the optional witness proposer "
                    "is unavailable"
                ),
            )

        solver_version = _solver_version(z3)

        try:
            projection = _proposal_projection(workflow)
            for depth in range(projection["bound"] + 1):
                built = _build_query(z3, projection, depth, timeout_ms)
                transcript.add_query(depth, built["solver"].sexpr())
                queried_depths.append(depth)
                result = built["solver"].check()

                if result == z3.sat:
                    candidate = _decode_candidate(
                        z3,
                        projection,
                        built,
                        built["solver"].model(),
                        depth,
                    )
                    return EngineOutcome(
                        kind="sat",
                        solver_version=solver_version,
                        query_digest=transcript.hexdigest(),
                        queried_depths=tuple(queried_depths),
                        candidate_result=candidate,
                    )

                if result == z3.unsat:
                    continue

                reason = _reason_unknown(built["solver"])
                kind = TIMEOUT if "timeout" in reason.lower() else INCONCLUSIVE_UNKNOWN
                return EngineOutcome(
                    kind=kind,
                    solver_version=solver_version,
                    query_digest=transcript.hexdigest(),
                    queried_depths=tuple(queried_depths),
                    reason_unknown=reason,
                )

            return EngineOutcome(
                kind="unsat",
                solver_version=solver_version,
                query_digest=transcript.hexdigest(),
                queried_depths=tuple(queried_depths),
            )
        except Exception as exc:
            return EngineOutcome(
                kind=ERROR,
                solver_version=solver_version,
                query_digest=transcript.hexdigest(),
                queried_depths=tuple(queried_depths),
                error=f"{type(exc).__name__}: {exc}",
            )


def run_pipeline(
    *,
    workflow_path: Path,
    checker_path: Path,
    timeout_ms: int,
    checker_timeout_ms: int,
    engine: Any,
    checker_runner: Callable[[Path, Path, Path, int], CheckerOutcome],
) -> PipelineOutcome:
    """Run the advisory proposal pipeline without writing caller-owned paths."""

    if timeout_ms <= 0:
        return _preflight_error(
            workflow_path,
            timeout_ms,
            "timeout_ms must be greater than zero",
        )
    if checker_timeout_ms <= 0:
        return _preflight_error(
            workflow_path,
            timeout_ms,
            "checker_timeout_ms must be greater than zero",
        )

    try:
        workflow_bytes = workflow_path.read_bytes()
    except OSError as exc:
        return _preflight_error(
            workflow_path,
            timeout_ms,
            f"could not read workflow: {exc}",
        )

    workflow_digest = sha256(workflow_bytes)
    try:
        workflow = json.loads(workflow_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _error_outcome(
            workflow_path=workflow_path,
            workflow_bytes=workflow_bytes,
            timeout_ms=timeout_ms,
            solver_version="not_loaded",
            query_digest=QueryTranscript(
                workflow_digest,
                timeout_ms,
            ).hexdigest(),
            error=f"workflow is not valid UTF-8 JSON: {exc}",
        )

    if not isinstance(workflow, dict):
        return _error_outcome(
            workflow_path=workflow_path,
            workflow_bytes=workflow_bytes,
            timeout_ms=timeout_ms,
            solver_version="not_loaded",
            query_digest=QueryTranscript(
                workflow_digest,
                timeout_ms,
            ).hexdigest(),
            error="workflow JSON must be an object",
        )

    try:
        engine_outcome = engine.propose(
            workflow,
            workflow_digest=workflow_digest,
            timeout_ms=timeout_ms,
        )
    except Exception as exc:
        return _error_outcome(
            workflow_path=workflow_path,
            workflow_bytes=workflow_bytes,
            timeout_ms=timeout_ms,
            solver_version="engine_exception",
            query_digest=QueryTranscript(
                workflow_digest,
                timeout_ms,
            ).hexdigest(),
            error=f"proposal engine raised {type(exc).__name__}: {exc}",
        )

    record = _base_record(
        workflow_path=workflow_path,
        workflow_bytes=workflow_bytes,
        timeout_ms=timeout_ms,
        engine_outcome=engine_outcome,
    )

    if engine_outcome.kind == "unsat":
        record["status"] = NO_CANDIDATE_ADVISORY
        record["solver"]["outcome"] = "unsat"
        record["comparison"] = {
            "status": "not_applicable",
            "reason": "UNSAT is advisory and is not compared to a SAFE authority.",
        }
        return PipelineOutcome(record, None, EXIT_OK)

    if engine_outcome.kind == INCONCLUSIVE_UNKNOWN:
        record["status"] = INCONCLUSIVE_UNKNOWN
        record["solver"]["outcome"] = "unknown"
        record["comparison"] = {
            "status": "not_run",
            "reason": "No candidate trace was available for Lean replay.",
        }
        return PipelineOutcome(record, None, EXIT_UNKNOWN)

    if engine_outcome.kind == TIMEOUT:
        record["status"] = TIMEOUT
        record["solver"]["outcome"] = "timeout"
        record["comparison"] = {
            "status": "not_run",
            "reason": "No candidate trace was available for Lean replay.",
        }
        return PipelineOutcome(record, None, EXIT_TIMEOUT)

    if engine_outcome.kind == ERROR:
        record["status"] = ERROR
        record["solver"]["outcome"] = "error"
        record["error"] = engine_outcome.error or "unspecified proposal-engine error"
        record["comparison"] = {
            "status": "not_run",
            "reason": "No candidate trace was available for Lean replay.",
        }
        return PipelineOutcome(record, None, EXIT_ERROR)

    if engine_outcome.kind != "sat" or engine_outcome.candidate_result is None:
        record["status"] = ERROR
        record["solver"]["outcome"] = engine_outcome.kind
        record["error"] = "proposal engine returned an invalid outcome shape"
        record["comparison"] = {
            "status": "not_run",
            "reason": "No well-formed candidate payload was supplied.",
        }
        return PipelineOutcome(record, None, EXIT_ERROR)

    candidate_bytes = (
        json.dumps(
            engine_outcome.candidate_result,
            indent=2,
            sort_keys=False,
        )
        + "\n"
    ).encode("utf-8")

    with tempfile.TemporaryDirectory(prefix="trackb-z3-candidate-") as temp_name:
        temp_root = Path(temp_name)
        workflow_copy = temp_root / "workflow.json"
        candidate_copy = temp_root / "candidate_result.json"
        workflow_copy.write_bytes(workflow_bytes)
        candidate_copy.write_bytes(candidate_bytes)

        if workflow_copy.read_bytes() != workflow_bytes:
            return _comparison_error(
                record,
                "immutable workflow-copy comparison failed",
                checker_path,
            )
        if candidate_copy.read_bytes() != candidate_bytes:
            return _comparison_error(
                record,
                "immutable candidate-copy comparison failed",
                checker_path,
            )

        checker = checker_runner(
            checker_path,
            workflow_copy,
            candidate_copy,
            checker_timeout_ms,
        )

    record["checker"] = {
        "path": str(checker_path),
        "exit_code": checker.exit_code,
        "stdout": checker.stdout.strip(),
        "stderr": checker.stderr.strip(),
        "error": checker.error,
        "timed_out": checker.timed_out,
        "role": (
            "Authoritative replay validation for the exact proposed native "
            "workflow/result pair."
        ),
    }
    record["candidate"] = {
        "sha256": sha256(candidate_bytes),
        "bytes": len(candidate_bytes),
        "native_status": "UNSAFE",
    }

    if checker.timed_out:
        record["status"] = TIMEOUT
        record["error"] = checker.error or "Lean checker timed out"
        record["comparison"] = {
            "status": "not_completed",
            "reason": "Lean replay validation timed out.",
        }
        return PipelineOutcome(record, None, EXIT_TIMEOUT)

    if checker.error is not None:
        record["status"] = ERROR
        record["error"] = checker.error
        record["comparison"] = {
            "status": "not_completed",
            "reason": "Lean replay validation could not run.",
        }
        return PipelineOutcome(record, None, EXIT_ERROR)

    if checker.exit_code != 0:
        record["status"] = ERROR
        record["error"] = (
            "Z3 proposed a candidate that the TrackB Lean replay checker rejected"
        )
        record["comparison"] = {
            "status": "mismatch",
            "proposer": "sat_candidate",
            "lean_checker": "rejected",
        }
        return PipelineOutcome(record, None, EXIT_COMPARISON_MISMATCH)

    record["status"] = CANDIDATE_UNSAFE
    record["comparison"] = {
        "status": "match",
        "proposer": "sat_candidate",
        "lean_checker": "accepted",
    }
    return PipelineOutcome(record, candidate_bytes, EXIT_OK)


def invoke_lean_checker(
    checker_path: Path,
    workflow_path: Path,
    candidate_path: Path,
    timeout_ms: int,
) -> CheckerOutcome:
    """Invoke the existing native checker; do not interpret its semantics here."""

    try:
        completed = subprocess.run(
            [str(checker_path), str(workflow_path), str(candidate_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_ms / 1000,
        )
    except subprocess.TimeoutExpired as exc:
        return CheckerOutcome(
            exit_code=None,
            stdout=_stream_text(exc.stdout),
            stderr=_stream_text(exc.stderr),
            error=f"Lean checker timed out after {timeout_ms} ms",
            timed_out=True,
        )
    except OSError as exc:
        return CheckerOutcome(
            exit_code=None,
            error=f"could not execute Lean checker: {exc}",
        )

    return CheckerOutcome(
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ask optional Z3 for a bounded UNSAFE witness, then require the "
            "TrackB Lean checker to replay the exact proposed pair. Never emits SAFE."
        )
    )
    parser.add_argument("workflow", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--candidate-result", type=Path)
    parser.add_argument("--checker", type=Path, default=DEFAULT_CHECKER)
    parser.add_argument("--timeout-ms", type=int, default=5_000)
    parser.add_argument("--checker-timeout-ms", type=int, default=30_000)
    return parser.parse_args(argv)


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    engine: Optional[Any] = None,
    checker_runner: Callable[
        [Path, Path, Path, int],
        CheckerOutcome,
    ] = invoke_lean_checker,
) -> int:
    args = parse_args(argv)
    outcome = run_pipeline(
        workflow_path=args.workflow,
        checker_path=args.checker,
        timeout_ms=args.timeout_ms,
        checker_timeout_ms=args.checker_timeout_ms,
        engine=engine if engine is not None else Z3WitnessEngine(),
        checker_runner=checker_runner,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(outcome.record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if outcome.candidate_bytes is not None:
        candidate_path = args.candidate_result
        if candidate_path is None:
            candidate_path = args.output.with_name(
                args.output.stem + ".candidate.json"
            )
        candidate_path.parent.mkdir(parents=True, exist_ok=True)
        candidate_path.write_bytes(outcome.candidate_bytes)

    print(f"status: {outcome.record['status']}")
    print(f"workflow_sha256: {outcome.record['workflow']['sha256']}")
    print(f"query_sha256: {outcome.record['query']['sha256']}")
    print(f"record: {args.output}")
    if outcome.candidate_bytes is not None:
        print(f"candidate_result: {candidate_path}")
    return outcome.exit_code


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _base_record(
    *,
    workflow_path: Path,
    workflow_bytes: bytes,
    timeout_ms: int,
    engine_outcome: EngineOutcome,
) -> dict[str, Any]:
    return {
        "proposal_schema": PROPOSAL_SCHEMA,
        "status": ERROR,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "nonclaims": [
            "No SAFE or SAFE_WITHIN_BOUND conclusion.",
            "No global-safety conclusion.",
            "No completeness claim for the Z3 encoding or solver.",
            "No authority for SAT until the exact native pair passes Lean replay.",
        ],
        "workflow": {
            "name": workflow_path.name,
            "sha256": sha256(workflow_bytes),
            "bytes": len(workflow_bytes),
        },
        "query": {
            "encoding_id": ENCODING_ID,
            "digest_kind": QUERY_DIGEST_KIND,
            "sha256": engine_outcome.query_digest,
            "timeout_ms_per_query": timeout_ms,
            "queried_depths": list(engine_outcome.queried_depths),
        },
        "solver": {
            "version": engine_outcome.solver_version,
            "outcome": engine_outcome.kind,
            "reason_unknown": engine_outcome.reason_unknown,
        },
        "candidate": None,
        "checker": None,
        "comparison": None,
    }


def _preflight_error(
    workflow_path: Path,
    timeout_ms: int,
    error: str,
) -> PipelineOutcome:
    workflow_bytes = b""
    try:
        workflow_bytes = workflow_path.read_bytes()
    except OSError:
        pass
    return _error_outcome(
        workflow_path=workflow_path,
        workflow_bytes=workflow_bytes,
        timeout_ms=timeout_ms,
        solver_version="not_loaded",
        query_digest=QueryTranscript(
            sha256(workflow_bytes),
            timeout_ms,
        ).hexdigest(),
        error=error,
    )


def _error_outcome(
    *,
    workflow_path: Path,
    workflow_bytes: bytes,
    timeout_ms: int,
    solver_version: str,
    query_digest: str,
    error: str,
) -> PipelineOutcome:
    engine_outcome = EngineOutcome(
        kind=ERROR,
        solver_version=solver_version,
        query_digest=query_digest,
        error=error,
    )
    record = _base_record(
        workflow_path=workflow_path,
        workflow_bytes=workflow_bytes,
        timeout_ms=timeout_ms,
        engine_outcome=engine_outcome,
    )
    record["status"] = ERROR
    record["error"] = error
    record["comparison"] = {
        "status": "not_run",
        "reason": "Proposal preflight did not complete.",
    }
    return PipelineOutcome(record, None, EXIT_ERROR)


def _comparison_error(
    record: dict[str, Any],
    error: str,
    checker_path: Path,
) -> PipelineOutcome:
    record["status"] = ERROR
    record["error"] = error
    record["checker"] = {
        "path": str(checker_path),
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "error": "checker was not run",
        "timed_out": False,
    }
    record["comparison"] = {
        "status": "mismatch",
        "reason": error,
    }
    return PipelineOutcome(record, None, EXIT_COMPARISON_MISMATCH)


def _proposal_projection(workflow: dict[str, Any]) -> dict[str, Any]:
    """Extract only fields needed to propose a trace.

    This is not the authoritative native parser or well-formedness checker.  A
    candidate built from this projection still has to pass the Lean executable
    against the exact original workflow bytes.
    """

    required = (
        "schema_version",
        "name",
        "bound",
        "state_variables",
        "initial_state",
        "actions",
        "forbidden",
    )
    missing = [field for field in required if field not in workflow]
    if missing:
        raise ValueError("missing proposal fields: " + ", ".join(missing))

    if workflow["schema_version"] != "0.1":
        raise ValueError("optional proposer currently supports schema_version 0.1")
    if not isinstance(workflow["name"], str) or not workflow["name"]:
        raise ValueError("workflow name must be a non-empty string")
    if (
        isinstance(workflow["bound"], bool)
        or not isinstance(workflow["bound"], int)
        or workflow["bound"] < 0
    ):
        raise ValueError("workflow bound must be a non-negative integer")
    if not isinstance(workflow["state_variables"], dict):
        raise ValueError("state_variables must be an object")
    if not isinstance(workflow["initial_state"], dict):
        raise ValueError("initial_state must be an object")
    if not isinstance(workflow["actions"], list):
        raise ValueError("actions must be an array")
    if not isinstance(workflow["forbidden"], dict):
        raise ValueError("forbidden must be an object")
    if not isinstance(workflow["forbidden"].get("all"), dict):
        raise ValueError("forbidden.all must be an object")

    variables = list(workflow["state_variables"])
    for variable, variable_type in workflow["state_variables"].items():
        if not isinstance(variable, str) or not variable:
            raise ValueError("state variable names must be non-empty strings")
        if variable_type != "bool":
            raise ValueError(f"state variable {variable!r} must have type 'bool'")
    if list(workflow["initial_state"]) != variables:
        raise ValueError(
            "initial_state keys and order must exactly match state_variables"
        )
    for variable in variables:
        _require_bool(
            workflow["initial_state"][variable],
            f"initial_state.{variable}",
        )

    actions: list[dict[str, Any]] = []
    action_names: set[str] = set()
    for index, raw_action in enumerate(workflow["actions"]):
        if not isinstance(raw_action, dict):
            raise ValueError(f"action {index} must be an object")
        name = raw_action.get("name")
        pre = raw_action.get("pre")
        effects = raw_action.get("effects")
        if not isinstance(name, str) or not name:
            raise ValueError(f"action {index} name must be a non-empty string")
        if name in action_names:
            raise ValueError(f"action names must be unique; duplicate {name!r}")
        action_names.add(name)
        if not isinstance(pre, dict) or not isinstance(effects, dict):
            raise ValueError(f"action {index} pre/effects must be objects")
        for field_name, mapping in (("pre", pre), ("effects", effects)):
            for variable, value in mapping.items():
                if variable not in variables:
                    raise ValueError(
                        f"action {name!r} {field_name} references {variable!r}"
                    )
                _require_bool(value, f"action {name!r}.{field_name}.{variable}")
        actions.append({"name": name, "pre": pre, "effects": effects})

    forbidden = workflow["forbidden"]["all"]
    for variable, value in forbidden.items():
        if variable not in variables:
            raise ValueError(f"forbidden.all references {variable!r}")
        _require_bool(value, f"forbidden.all.{variable}")

    return {
        "schema_version": workflow["schema_version"],
        "name": workflow["name"],
        "bound": workflow["bound"],
        "variables": variables,
        "initial_state": workflow["initial_state"],
        "actions": actions,
        "forbidden": forbidden,
    }


def _build_query(
    z3: Any,
    workflow: dict[str, Any],
    depth: int,
    timeout_ms: int,
) -> dict[str, Any]:
    variables = workflow["variables"]
    actions = workflow["actions"]
    solver = z3.Solver()
    solver.set(timeout=timeout_ms)

    states = {
        (time, index): z3.Bool(f"state_{time}_{index}")
        for time in range(depth + 1)
        for index in range(len(variables))
    }
    selectors = {
        (time, index): z3.Bool(f"action_{time}_{index}")
        for time in range(depth)
        for index in range(len(actions))
    }

    for index, variable in enumerate(variables):
        solver.add(
            states[(0, index)]
            == z3.BoolVal(workflow["initial_state"][variable])
        )

    variable_indexes = {variable: index for index, variable in enumerate(variables)}
    for time in range(depth):
        step_selectors = [
            selectors[(time, index)] for index in range(len(actions))
        ]
        solver.add(_exactly_one(z3, step_selectors))

        for action_index, action in enumerate(actions):
            selected = selectors[(time, action_index)]
            preconditions = [
                states[(time, variable_indexes[variable])] == z3.BoolVal(expected)
                for variable, expected in action["pre"].items()
            ]
            if preconditions:
                solver.add(z3.Implies(selected, z3.And(preconditions)))

            for variable_index, variable in enumerate(variables):
                successor = states[(time + 1, variable_index)]
                if variable in action["effects"]:
                    expected_successor = z3.BoolVal(action["effects"][variable])
                else:
                    expected_successor = states[(time, variable_index)]
                solver.add(
                    z3.Implies(selected, successor == expected_successor)
                )

    forbidden_terms = [
        states[(depth, variable_indexes[variable])] == z3.BoolVal(expected)
        for variable, expected in workflow["forbidden"].items()
    ]
    solver.add(z3.And(forbidden_terms) if forbidden_terms else z3.BoolVal(True))
    return {
        "solver": solver,
        "states": states,
        "selectors": selectors,
    }


def _decode_candidate(
    z3: Any,
    workflow: dict[str, Any],
    built: dict[str, Any],
    model: Any,
    depth: int,
) -> dict[str, Any]:
    variables = workflow["variables"]
    actions = workflow["actions"]
    states = [
        {
            variable: _model_bool(
                z3,
                model,
                built["states"][(time, index)],
            )
            for index, variable in enumerate(variables)
        }
        for time in range(depth + 1)
    ]

    trace: list[dict[str, Any]] = [
        {
            "step": 0,
            "action": None,
            "state_before": None,
            "state_delta": {},
            "state_after": states[0],
        }
    ]
    for time in range(depth):
        selected_action: Optional[dict[str, Any]] = None
        for action_index, action in enumerate(actions):
            if _model_bool(
                z3,
                model,
                built["selectors"][(time, action_index)],
            ):
                selected_action = action
                break
        if selected_action is None:
            raise ValueError(f"model selected no action at step {time + 1}")

        before = states[time]
        after = states[time + 1]
        trace.append(
            {
                "step": time + 1,
                "action": selected_action["name"],
                "state_before": before,
                "state_delta": {
                    variable: after[variable]
                    for variable in variables
                    if before[variable] is not after[variable]
                },
                "state_after": after,
            }
        )

    return {
        "workflow": workflow["name"],
        "schema_version": workflow["schema_version"],
        "bound": workflow["bound"],
        "status": "UNSAFE",
        "violation": {
            "condition": workflow["forbidden"],
            "first_bad_step": depth,
        },
        "trace": trace,
        "claim_boundary": UNSAFE_CLAIM_BOUNDARY,
    }


def _exactly_one(z3: Any, expressions: Sequence[Any]) -> Any:
    if not expressions:
        return z3.BoolVal(False)
    pairs = [
        z3.Not(z3.And(left, right))
        for index, left in enumerate(expressions)
        for right in expressions[index + 1 :]
    ]
    return z3.And([z3.Or(expressions)] + pairs)


def _model_bool(z3: Any, model: Any, expression: Any) -> bool:
    return bool(z3.is_true(model.eval(expression, model_completion=True)))


def _reason_unknown(solver: Any) -> str:
    try:
        reason = solver.reason_unknown()
    except Exception as exc:
        return f"reason_unknown unavailable: {type(exc).__name__}: {exc}"
    return reason or "unspecified"


def _require_bool(value: Any, label: str) -> None:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be Boolean")


def _solver_version(z3: Any) -> str:
    try:
        return str(z3.get_version_string())
    except Exception:
        return "unknown"


def _load_z3() -> Any:
    try:
        import z3  # type: ignore
    except ImportError:
        return None
    return z3


def _stream_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())

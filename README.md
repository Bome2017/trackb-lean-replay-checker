# TrackB Lean Replay Checker and Reachability Kernel

TrackB v0.2 is a narrow Lean 4 implementation of a finite Boolean workflow
semantics. One typed kernel is shared by:

- the native `UNSAFE` replay checker;
- exhaustive bounded reachability;
- first-bad trace reconstruction; and
- closed-state global-safety certificates.

The external workflow schema remains `schema_version: "0.1"`. The package
version is `0.2.0`.

## Formal results

The main proved results are:

- replay-checker soundness and completeness for its declared native
  counterexample proposition;
- soundness of every `UNSAFE` trace returned by the reachability engine;
- bounded search completeness: if a semantic first-bad trace exists with at
  most the configured number of actions, the engine returns an `UNSAFE` trace;
- `SAFE_WITHIN_BOUND` soundness: that outcome excludes a semantic
  counterexample at or below the configured bound;
- global-safety soundness: `GLOBALLY_SAFE` is emitted only from a checked finite
  set containing the initial state, containing no forbidden state, and closed
  under every enabled transition;
- proof-carrying executable packaging: a successful emitted counterexample is
  bound to both its semantic proof and ordinary native replay acceptance, while
  a successful global result is bound to its closure and native certificate
  acceptance; and
- concrete global-safety theorems for the checked-in email-approval,
  delete-confirmation, and vendor-payment workflows.

The concrete fixture certificates are reduced by the Lean kernel. They do not
use a fixture-specific proof assumption or a native evaluation shortcut. The
axiom gate permits only Lean's standard `propext`, `Classical.choice`, and
`Quot.sound`.

The packaging theorems are `checked_unsafe_endToEnd`,
`checked_bounded_safe_endToEnd`, and `checked_global_endToEnd`. The executable
calls the corresponding pure checked result constructor and fails instead of
emitting an artifact if packaging does not pass.

## Result lattice

`trackb-reachability` emits exactly one machine-readable result:

| Status | Meaning |
|---|---|
| `UNSAFE` | A first-bad trace exists at or below the workflow bound, and the emitted native result passed the ordinary replay checker before output |
| `SAFE_WITHIN_BOUND` | No semantic counterexample exists at or below the workflow bound; no all-depth claim is made |
| `GLOBALLY_SAFE` | A finite closed reachable-state certificate passed the independent checker, proving all-depth safety in the exact declared model |
| process error | Parsing, compilation, reconstruction, packaging, or I/O failed; no safety result is emitted |

All three semantic statuses use process exit code 0 and are distinguished by
the JSON `status` field. Errors use exit code 2. A certificate-check failure
uses exit code 1.

## Build

Requirements: `elan` and the pinned Lean toolchain.

```sh
lake build
```

No Mathlib or other Lake dependency is required.

## Check an existing `UNSAFE` pair

```sh
lake exe trackb-replay-check \
  fixtures/unsafe_workflow.json \
  fixtures/unsafe_result.json
```

Expected output:

```text
PASS workflow=unauthorized_send actions=1 bound=2
```

## Run authoritative reachability

```sh
lake exe trackb-reachability fixtures/unsafe_workflow.json
```

For a guarded workflow:

```sh
lake exe trackb-reachability \
  fixtures/guarded/agent_email_requires_approval/workflow.json \
  > /tmp/trackb-global-result.json

lake exe trackb-global-safety-check \
  fixtures/guarded/agent_email_requires_approval/workflow.json \
  /tmp/trackb-global-result.json
```

The second command independently checks the finite closure carried by the
result.

## Check exact fixture-to-theorem correspondence

```sh
lake exe trackb-guarded-fixture-check \
  fixtures/guarded/agent_email_requires_approval/workflow.json
```

This executable uses the Lean JSON parser and compares the parsed value with
the exact typed workflow used by the concrete theorem. The release gate also
checks the fixture SHA-256.

## Create an exact-input replay receipt

```sh
python3 scripts/check_pair.py \
  fixtures/unsafe_workflow.json \
  fixtures/unsafe_result.json \
  --receipt /tmp/trackb-receipt.json
```

The wrapper copies the exact input bytes to a temporary directory, invokes the
compiled Lean replay checker on those copies, and records SHA-256 digests for
the inputs and executable. It performs no semantic translation.

## Optional Z3 proposal layer

[`scripts/z3_witness_proposer.py`](scripts/z3_witness_proposer.py) is an
optional untrusted accelerator. It never emits `SAFE` or
`SAFE_WITHIN_BOUND`. `UNSAT` is only `no_candidate_advisory`; unknown, timeout,
and errors are explicit nonzero outcomes. A SAT-derived candidate is surfaced
only after the exact native workflow/result pair passes the Lean replay
checker.

See [`docs/Z3_WITNESS_PROPOSER.md`](docs/Z3_WITNESS_PROPOSER.md).

## Validate the release candidate

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify_release.py
```

The fail-closed gate:

- builds every registered target;
- runs all positive and negative tests;
- checks all exported theorem dependencies against the axiom allowlist;
- rejects incomplete-proof tokens and native-evaluation proof shortcuts;
- rejects source-tree symlinks and unexpected Lake dependencies;
- checks exact guarded-fixture SHA-256 values; and
- runs the Lean fixture-to-theorem correspondence executable.

Read [CLAIM_BOUNDARIES.md](CLAIM_BOUNDARIES.md) and
[SEMANTICS_AND_INPUT_DOMAIN.md](SEMANTICS_AND_INPUT_DOMAIN.md) before citing
the result.

## Rights

Copyright 2026 Sanjit Singh Mehat. Apache-2.0. The work was developed under his
direction with LLM assistance; see
[RIGHTS_AND_PROVENANCE.md](RIGHTS_AND_PROVENANCE.md).

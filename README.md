# TrackB Lean Replay Checker

A narrow, executable Lean 4 checker for concrete `UNSAFE` traces emitted under
the TrackB v0.1 bounded Boolean workflow schema.

The core result is deliberately modest and useful:

> If the executable returns `PASS`, the supplied result contains a valid
> counterexample trace for the supplied workflow under the parsed TrackB v0.1
> transition semantics, using no more actions than the workflow bound.

The Lean theorem `TrackBReplay.check_sound` connects the executable Boolean
check to the proposition `TrackBReplay.ValidCounterexample`. The executable
parses the native workflow and result JSON files directly, so there is no
separate workflow-to-Lean semantic translator.

## Build

Requirements: `elan` and the pinned Lean toolchain.

```sh
lake build
```

No Mathlib or other Lake dependency is required.

## Check a pair

```sh
lake exe trackb-replay-check \
  fixtures/unsafe_workflow.json \
  fixtures/unsafe_result.json
```

Expected output:

```text
PASS workflow=unauthorized_send actions=1 bound=2
```

## Create an exact-input receipt

First build, then run:

```sh
python3 scripts/check_pair.py \
  fixtures/unsafe_workflow.json \
  fixtures/unsafe_result.json \
  --receipt /tmp/trackb-receipt.json
```

The wrapper copies the exact input bytes to a temporary directory, invokes the
compiled Lean checker on those copies, and records SHA-256 digests for the
inputs and executable. It performs no semantic translation.

## Test

```sh
python3 scripts/verify_release.py
```

The fail-closed release gate rebuilds every target, runs the tests, checks the
axiom report against an allowlist, rejects incomplete-proof tokens, rejects
source-tree symlinks, and confirms that the manifest has no hidden Lake
dependencies. The tests include a valid witness, transition tampering,
workflow/result bound mismatch, fail-closed handling of `SAFE_WITHIN_BOUND`,
and receipt digest binding.

Read [CLAIM_BOUNDARIES.md](CLAIM_BOUNDARIES.md) before citing the result. In
particular, this package certifies concrete counterexamples; it does not prove
`SAFE_WITHIN_BOUND` or the completeness of a search backend.

## Rights

Copyright 2026 Sanjit Singh Mehat. Apache-2.0. The work was developed under his
direction with LLM assistance; see [RIGHTS_AND_PROVENANCE.md](RIGHTS_AND_PROVENANCE.md).

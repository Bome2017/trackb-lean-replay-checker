# TrackB Lean Replay Checker and Reachability Kernel

TrackB v0.2 is a narrow Lean 4 implementation of a finite Boolean workflow
semantics. One typed kernel is shared by:

- the native `UNSAFE` replay checker;
- exhaustive bounded reachability;
- first-bad trace reconstruction; and
- closed-state global-safety certificates.

The external workflow schema remains `schema_version: "0.1"`. The package
version is `0.2.1`.

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
  bound to both its semantic proof and ordinary native replay acceptance; a
  bounded-safe result is bound to the exact engine outcome, generated state
  lists, and semantic no-counterexample theorem; and a successful global result
  is bound to its closure and native certificate acceptance; and
- concrete global-safety theorems for the checked-in email-approval,
  delete-confirmation, and vendor-payment workflows.

The concrete fixture certificates are reduced by the Lean kernel. They do not
use a fixture-specific proof assumption or a native evaluation shortcut. The
axiom gate permits only Lean's standard `propext`, `Classical.choice`, and
`Quot.sound`.

Global-result semantics and metadata are proved separately.
`GlobalSafetyResult.semanticCheck_sound` derives `workflow.GloballySafe` from
successful compilation and the checked finite safety certificate.
`GlobalSafetyResult.metadataCheck_iff` characterizes the workflow, schema,
bound, status, and claim-boundary fields, while
`GlobalSafetyResult.check_sound` derives both semantic safety and metadata
consistency from the full native checker.

The packaging theorems are `checked_unsafe_endToEnd`,
`checked_bounded_safe_endToEnd`, and `checked_global_endToEnd`. The executable
calls the corresponding pure checked result constructor. Unsafe and global
packaging fail instead of emitting an artifact if their native checker rejects;
bounded-safe output is emitted only from its exact proof-bearing wrapper.

## Result lattice

`trackb-reachability` emits exactly one machine-readable result:

| Status | Meaning |
|---|---|
| `UNSAFE` | A first-bad trace exists at or below the workflow bound, and the emitted native result passed the ordinary replay checker before output |
| `SAFE_WITHIN_BOUND` | No semantic counterexample exists at or below the workflow bound; no all-depth claim is made |
| `GLOBALLY_SAFE` | A finite initial-containing, non-forbidden, successor-closed state-set certificate passed the checker, proving all-depth safety in the exact declared model |
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
candidate_commit="$(git rev-parse HEAD)"
candidate_tree="$(git rev-parse 'HEAD^{tree}')"
candidate_branch="$(git branch --show-current)"
candidate_remote="$(git remote get-url origin)"

PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify_release.py \
  --expected-commit "$candidate_commit" \
  --expected-tree "$candidate_tree" \
  --expected-branch "$candidate_branch" \
  --expected-remote "$candidate_remote" \
  --require-no-lake-at-start
```

The fail-closed gate:

- checks exact Git, tree, remote, pinned-toolchain, and source identities;
- builds every registered target with no unapproved warnings;
- regenerates the authoritative theorem inventory from Lean's elaborated
  environments and byte-compares it with the reviewed inventory;
- audits every owned theorem constant and every owned constant for forbidden
  transitive axioms, without using source regexes or a manual theorem count as
  discovery authority;
- runs the hostile theorem-discovery gate, bounded-output regression, Z3
  proposer tests, and all other positive and negative tests;
- checks the semantic/metadata theorem split, guarded-fixture hashes, and
  parser-to-theorem correspondence;
- rejects incomplete-proof tokens, unreviewed unsafe declarations,
  native-evaluation proof shortcuts, symlinks, sibling dependencies, caches,
  generated objects, and absolute private paths; and
- creates two byte-identical deterministic source archives, verifies exact
  source equivalence and safe archive metadata, then proves the before/after
  source fingerprint is unchanged.

The release gate intentionally rejects a preexisting `.lake`, object file,
cache, symlink, or untracked source. Run it from a fresh clone. Source-only
reproduction additionally requires an extraction with no `.git` and supplies
the expected archive and archive-manifest hashes; the gate regenerates both
and requires byte-identical digests.

`TheoremInventory.lean` is audit tooling. Its three `unsafe` runtime
declarations are narrowly required to invoke Lean's module-loading API and are
excluded from the owned theorem surface; the verifier allows exactly those
reviewed declarations and no others. See
[docs/THEOREM_INVENTORY_POLICY.md](docs/THEOREM_INVENTORY_POLICY.md).

The independently recheckable bounded-result JSON checker is deliberately
deferred; v0.2.1's required in-process exact-object binding is complete. See
[docs/BOUNDED_RESULT_CHECKER_DECISION.md](docs/BOUNDED_RESULT_CHECKER_DECISION.md).

Read [CLAIM_BOUNDARIES.md](CLAIM_BOUNDARIES.md) and
[SEMANTICS_AND_INPUT_DOMAIN.md](SEMANTICS_AND_INPUT_DOMAIN.md) before citing
the result. The current repair record is
[RELEASE_NOTES_v0.2.1.md](RELEASE_NOTES_v0.2.1.md); the historical v0.2.0
notes and validation report remain scoped to commit `5a637f8c`.

## Rights

Copyright 2026 Sanjit Singh Mehat. Apache-2.0. The work was developed under his
direction with LLM assistance; see
[RIGHTS_AND_PROVENANCE.md](RIGHTS_AND_PROVENANCE.md).

# TrackB v0.2.0 release notes

Status: prepared and locally validated; publish only from the exact validated
commit.

## Added

- one canonical vector-indexed Boolean semantics shared by replay, search, and
  safety checking;
- exhaustive exact-depth state reachability;
- bounded counterexample search soundness and completeness;
- proof-carrying `UNSAFE`, `SAFE_WITHIN_BOUND`, and `GLOBALLY_SAFE` outcomes;
- independent finite closed-state certificate checking;
- native global-result parsing and checking;
- exact guarded-fixture-to-theorem correspondence checking;
- concrete global-safety theorems for email approval, delete confirmation, and
  vendor payment;
- strict object-shape validation at the native JSON boundary;
- an optional fail-closed Z3 witness proposer; and
- expanded release, axiom, hash, parser, and negative-test gates.

## Compatibility

The external workflow and native replay-result schema remains version `0.1`.
Existing valid v0.1 counterexample pairs remain supported. v0.2 deliberately
rejects unknown members in schema-defined workflow, action, forbidden-wrapper,
trace-step, violation, and result objects.

Duplicate member names, noncanonical numeric spellings, and JSON extensions
are outside the citable input subset.

## New executables

- `trackb-reachability`
- `trackb-global-safety-check`
- `trackb-guarded-fixture-check`

The existing `trackb-replay-check` remains the native `UNSAFE` authority.

## Validation summary

- clean source-only build: PASS;
- 33 build jobs: PASS;
- 19 tests: PASS;
- 27-theorem dependency audit: PASS;
- only `propext`, `Classical.choice`, and `Quot.sound`: PASS;
- guarded fixture hashes and Lean correspondence: 3 of 3 PASS;
- real optional Z3 SAT and UNSAT-advisory smoke cases: PASS.

See [VALIDATION_REPORT.md](VALIDATION_REPORT.md).

## Claim boundary

Bounded completeness is only for `BoundedCounterexample` in the exact compiled
TrackB model. Global safety is only all-depth non-forbidden reachability in the
exact closed model. Neither result proves model completeness, objective truth,
external authorization, universal filesystem safety, or ReplayGuard/Evidence-
to-Action correctness.

## Publication dependency

The existing replay-obstruction correspondence release is pinned to the
v0.1.0 checker identity. A v0.2 correspondence update must be prepared and
validated only after this exact checker commit is published at an immutable
revision. Do not point that package at an uncommitted worktree or mutable
branch.

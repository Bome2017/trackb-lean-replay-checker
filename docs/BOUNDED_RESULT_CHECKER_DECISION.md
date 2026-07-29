# Bounded-result checker decision for v0.2.1

## Decision

Disposition: `DEFERRED_TO_v0.2.2_OR_v0.3.0`.

The independently recheckable `BoundedSafetyResult` JSON checker is deferred
from v0.2.1 to v0.2.2 or v0.3.0.

This is a scope decision, not an unresolved defect in the repaired in-process
emission path. The v0.2.1 executable emits the exact `BoundedSafetyResult`
stored in `CheckedGeneratedBoundedSafety`. That package also stores:

- the exact `visited` and `frontier` kernel-state lists;
- an equality connecting those lists to the authoritative reachability-engine
  outcome;
- an equality connecting the native result to
  `makeBoundedSafetyResult workflow visited frontier`; and
- the bounded no-counterexample theorem obtained from that exact engine
  outcome.

`SearchMain` serializes `generated.result` directly. It does not discard the
checked package and call `makeBoundedSafetyResult` independently.

The regression in `tests/test_bounded_result_emission.py` checks this boundary
in two ways:

1. A temporary Lean probe imports the release module, typechecks use of the
   package's engine, generated-result, and semantic evidence, and serializes the
   directly carried result.
2. The real `trackb-reachability` output is compared with that carried result
   and with the exact expected workflow, schema, bound, status, visited,
   frontier, and claim-boundary fields.

The test also constructs one-field substitutions for workflow, schema, bound,
visited, frontier, status, and claim boundary. Lean's decidable equality
distinguishes every substituted value from the carried object. This is an
identity regression only: v0.2.1 does not accept supplied bounded-result JSON,
so these cases are not described as rejection tests for an external checker.

## Why implementation is deferred

The current release has a strict parser and checker for global-safety results,
but it has no `parseBoundedSafetyResult` and no Boolean validity checker for a
supplied bounded result. Adding only a parser, metadata comparisons, or
well-formed-state checks would be insufficient: those checks do not establish
that no bounded counterexample exists.

A sound independent checker must relate the supplied `visited` and `frontier`
lists to the bounded-search semantics. The narrowest credible design is to
compile the supplied workflow, recompute the authoritative reachability engine
at the supplied workflow bound, require the recomputed outcome to be
`safeWithinBound visited frontier`, and require the entire supplied result to
equal `makeBoundedSafetyResult workflow visited frontier`.

That change is more than a local parser addition. It requires:

- a strict exact-key JSON parser for `BoundedSafetyResult`;
- state parsing and exact workflow-variable/key validation;
- a separately defined validity proposition;
- a Boolean checker that compiles the workflow and compares the complete
  deterministic engine outcome and native object;
- soundness and completeness (or `check_iff`) theorems;
- a new checker executable and Lake target;
- hostile parser, metadata, state-list, status, and claim-boundary tampering
  tests; and
- release-gate, documentation, and theorem-inventory integration.

Introducing those surfaces during the mandatory v0.2.1 release-gate repair
would expand the trusted and tested release boundary. It is therefore deferred
rather than implemented partially.

## Required next-version acceptance criteria

An independent bounded-result checker is complete only when all of the
following hold:

1. The JSON parser rejects missing, duplicate, and extra object keys.
2. Workflow, schema, bound, status, and claim boundary must match exactly.
3. Every supplied state must have exactly the workflow's variable keys.
4. Workflow compilation must succeed.
5. The deterministic engine must return
   `safeWithinBound visited frontier` with the exact supplied lists.
6. The complete supplied object must equal the canonical result constructed
   from that workflow and those engine lists.
7. A separately defined proposition states this relation without referring to
   the checker Boolean.
8. The checker has soundness and completeness theorems, or an equivalence
   theorem.
9. Hostile tests change each field independently and demonstrate rejection.
10. The theorem and axiom inventory covers every new proof declaration.

Checking only that supplied states are well formed, or that no supplied state
is forbidden, does not satisfy these criteria.

## Claim boundary

The v0.2.1 regression closes the original in-process output-binding issue:
the emitted object is the object carried by the proof-bearing checked outcome.
It does not make bounded-result JSON independently recheckable, and
`SAFE_WITHIN_BOUND` remains a statement about the configured finite bound in
the exact TrackB Boolean workflow model, not global safety or real-world
safety.

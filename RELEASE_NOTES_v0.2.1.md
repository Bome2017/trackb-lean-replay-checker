# TrackB v0.2.1 repair notes

Status: local successor candidate; not tagged, pushed, published, signed, or
publicly reproduced.

TrackB v0.2.1 preserves the external workflow schema `0.1` and the finite
Boolean operational semantics introduced by v0.2.0. It repairs proof-to-output,
release-gate, fixture-compilation, and documentation defects found by the
read-only audit of the exact historical baseline.

## Baseline and supersession

The audited v0.2.0 baseline remains immutable:

- commit: `5a637f8c29d26b79160c6812984cd610ac0d78f6`;
- tree: `70831205d8165d4a513590487a64bf4f69a8394b`.

That identity remains usable only for its accurately bounded historical claims.
It is superseded as the current release candidate by this repair branch because
its emitted `SAFE_WITHIN_BOUND` artifact was not definitionally connected to
the semantic proof retained by the search layer, and its axiom gate covered
only 28 of 46 explicit theorem declarations.

## Repairs

1. `CheckedGeneratedBoundedSafety` now carries one exact
   `BoundedSafetyResult`, the exact `reachabilityEngine` outcome and
   visited/frontier lists that generated it, the result-generation equality,
   and the semantic no-counterexample theorem.
2. `SearchMain` emits that carried bounded result. It no longer discards the
   proof and reconstructs a fresh JSON-shaped value.
3. `EndToEndBoundedSafety` is parameterized by the exact native result, and
   `checked_bounded_safe_endToEnd` establishes the result, engine, and semantic
   bindings together. `AxiomCheck.lean` compile-checks this exact theorem shape.
4. The axiom gate covers all 44 remaining explicit theorem declarations.
   `scripts/verify_release.py` also compares the complete source theorem
   inventory with that gate, so an added, removed, or renamed declaration fails
   closed until coverage is deliberately updated.
5. The two projection-only lemmas
   `generated_result_passes_checker` and
   `generated_global_result_passes_checker` were removed. Their underlying
   accepted fields remain part of the proof-bearing structures; the removed
   wrappers were not independent results.
6. The fixture compiler no longer returns a fabricated kernel on failure.
   Its private helper requires a reduction proof that compilation succeeds and
   returns a `CompiledWorkflow`. Each exported fixture kernel is obtained from
   that proof-bearing value.
7. The always-true `trace.states ≠ []` conjunct and Boolean test were removed
   from `BoundedCounterexample`. `SemanticTrace` has no empty constructor, so
   this is a logically equivalent simplification rather than a weaker safety
   condition.
8. Documentation now describes the global certificate as an
   initial-containing, non-forbidden, successor-closed state set. The
   independent certificate checker does not require every supplied member to
   be reachable.
9. ReplayGuard/Evidence-to-Action absence is classified as an external future
   formalization boundary, not as a broken TrackB theorem or a small TrackB
   repair.

## Local validation

The repaired working tree passed:

- `lake build`: 33 jobs;
- the fail-closed release gate: `RELEASE_GATE=PASS`;
- 19 positive and hostile Python tests;
- all 44 explicit theorem axiom queries;
- the exact guarded-fixture digest and parser-to-theorem correspondence checks;
- the allowed axiom set: `propext`, `Classical.choice`, and `Quot.sound`.

These results are local engineering evidence. A release claim still requires an
exact committed identity, a fresh clean-checkout receipt for that identity, and
immutable public artifacts if public reproducibility is claimed.

## Nonclaims

This repair does not establish independent authorship or third-party
validation, public reproducibility, model completeness, real-world truth,
authenticated authorization, ReplayGuard/Evidence-to-Action formal
correctness, Python-to-Lean correspondence for those projects, hostile-kernel
resistance, universal filesystem safety, or any unbounded-domain result.

# TrackB v0.2.1 repair notes

Status: local successor source. Publication readiness is established only by
the external release receipt, deterministic source archive, and local annotated
release-candidate tag for the exact final commit. No public push, public tag,
signature, or GitHub release is asserted here.

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
4. `TheoremInventory.lean` replaces source-regex and manually listed theorem
   discovery. It loads all release roots into Lean environments, restricts
   declarations by origin module, preserves full names, records types and
   transitive axioms, distinguishes authored and generated theorem constants,
   and emits deterministic JSON. The gate regenerates and byte-compares the
   reviewed inventory, then audits every owned theorem and every owned constant
   against the exact axiom allowlist.
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
10. Hostile generated fixtures exercise multiline, Unicode, quoted, nested,
    duplicate-leaf, attributed, unusual-whitespace, imported, generated, and
    `sorryAx`-dependent declarations. The fixtures exist only in a system
    temporary directory and cannot enter the release archive.
11. `GlobalSafetyResult.semanticCheck_sound` derives global safety from the
    semantic certificate path. `metadataCheck_iff` separately characterizes
    native metadata consistency, and the combined `check_sound` theorem returns
    both results.
12. The bounded-output regression checks that the executable serializes the
    exact `BoundedSafetyResult` carried by the checked engine outcome and
    rejects equality after substituting each native field.
13. The independently recheckable bounded-result JSON checker is deferred to
    v0.2.2 or v0.3.0. A correct checker needs a strict parser and an
    independently justified search/certificate relation; a shallow
    well-formed-state check would not prove bounded safety.

## Local validation

The reviewed environment-derived inventory at this source state records:

- 853 owned Lean constants audited for forbidden transitive axioms;
- 311 owned theorem constants, comprising 47 authored declarations and 264
  generated theorem constants;
- no owned axiom declarations;
- no unsafe declarations in the owned release modules; and
- only `propext`, `Classical.choice`, and `Quot.sound` as permitted transitive
  axioms.

Those numbers are generated evidence, not manually maintained discovery
authority. `validation/theorem_inventory.json` is authoritative only when the
complete release gate regenerates it byte-for-byte from the pinned Lean
environment. The same gate runs the full build, all Python tests, hostile
inventory tests, exact fixture correspondence, bounded-output regression,
semantic/metadata theorem checks, deterministic archive reconstruction, and
before/after source fingerprint comparison.

Final clean-clone and source-only results, exact commit/tree, test count,
archive hash, and receipt hash belong to the external immutable release
evidence. Public reproducibility is not claimed until those exact assets are
published under explicit authorization.

## Nonclaims

This repair does not establish independent authorship or third-party
validation, public reproducibility, model completeness, real-world truth,
authenticated authorization, ReplayGuard/Evidence-to-Action formal
correctness, Python-to-Lean correspondence for those projects, hostile-kernel
resistance, universal filesystem safety, or any unbounded-domain result.

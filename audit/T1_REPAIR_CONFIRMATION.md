# T1 Repair Confirmation

Status: PASS

Baseline inspected:

- commit: `07fe7333a004330c78eb2be484ae10d62e42c139`
- tree: `c8c71b580fb7173fe844654fe54b0612a90037d0`

## Proof-bound bounded-safety output

`CheckedGeneratedBoundedSafety` in `TrackBResults.lean:256` carries:

- the exact visited state list;
- the exact frontier state list;
- the exact native `BoundedSafetyResult`;
- equality between the reachability engine and the corresponding
  `safeWithinBound` outcome;
- equality between the native result and
  `makeBoundedSafetyResult workflow visited frontier`; and
- the semantic theorem excluding a bounded counterexample.

`packageGeneratedBoundedSafety` constructs this package at
`TrackBResults.lean:271-286`, deriving its semantic field from
`reachabilityEngine_safeWithinBound_sound`.

`CheckedReachability.safeWithinBound` accepts only the proof-bearing package at
`TrackBResults.lean:303-304`. `runCheckedReachability` builds that package from
the exact engine equality at `TrackBResults.lean:326-329`.

`SearchMain.lean:31-32` serializes `generated.result` directly. It does not call
`makeBoundedSafetyResult` or reconstruct another native object.

Result: PASS.

## Fail-closed fixture compilation

The private `compileFixture` helper at `GuardedExamples.lean:30-37` requires a
proof that `workflow.compile.isOk = true` and returns a
`CompiledWorkflow workflow`. Its error branch is eliminated by contradiction;
there is no fallback kernel.

The email, delete, and vendor-payment fixtures obtain their kernels through
proof-bearing compiled values at `GuardedExamples.lean:117-121`,
`GuardedExamples.lean:200-204`, and `GuardedExamples.lean:312-317`.

Result: PASS.

## Projection-only wrapper disposition

The former declarations `generated_result_passes_checker` and
`generated_global_result_passes_checker` are absent from current Lean source.
Their historical removal is disclosed in `RELEASE_NOTES_v0.2.1.md:39-43`.

`checked_unsafe_endToEnd`, `checked_bounded_safe_endToEnd`, and
`checked_global_endToEnd` are described as packaging theorems in
`README.md:41-45`; they are not counted as independent derivations of their
inputs. The bounded packaging proposition at `TrackBResults.lean:360-383`
includes the exact native result, engine equality, generation equality, and
semantic theorem.

Result: PASS.

## Certificate terminology

Current documentation describes the global certificate as an
initial-containing, non-forbidden, successor-closed state set in
`README.md:55` and `RELEASE_NOTES_v0.2.1.md:52-55`.
`CLAIM_BOUNDARIES.md:69-96` separately explains that induction proves every
reachable state belongs to the supplied set; it does not claim that every
supplied member is reachable.

Result: PASS.

All mandatory pre-existing repairs are present. Subsequent stages may harden
the theorem inventory and release boundary without redesigning the shared
TrackB semantics.

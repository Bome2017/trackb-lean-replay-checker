# Claim boundaries

## Shared semantics boundary

TrackB v0.2 has one operational semantics:
`TrackBReplay.Kernel.successors`. The replay checker, bounded reachability
engine, trace reconstruction, and finite-closure checker all use that kernel.
Malformed external workflows fail during validation or compilation; they are
not assigned a safety meaning.

The external JSON schema version is `0.1`. The Lean package implementing the
shared kernel is version `0.2.1`.

## Native replay `PASS`

A `PASS` from `trackb-replay-check` means the exact parsed workflow/result pair
contains a well-formed concrete first-bad trace such that:

- workflow/result identity, schema version, bound, and forbidden condition
  agree;
- step 0 is the exact initial state;
- every later step is a transition of the shared kernel;
- each reported state delta is exact;
- action count is at most the workflow bound;
- every earlier state is non-forbidden; and
- the final state is forbidden.

`TrackBReplay.check_sound` proves that executable acceptance entails
`TrackBReplay.ValidCounterexample`.

The authoritative search executable uses a proof-carrying pure result. For an
emitted counterexample, `TrackBReplay.checked_unsafe_endToEnd` binds one exact
semantic `BoundedCounterexample`, its definitionally generated native result,
and ordinary replay-checker acceptance.

## Bounded search completeness

The proved completeness statement is relational and bounded:

> If there exists a `TrackBReplay.BoundedCounterexample` whose action count is
> at most `bound` in the exact compiled kernel, then
> `TrackBReplay.reachabilityEngine` returns some `unsafeFound` trace satisfying
> that proposition.

The proof is `TrackBReplay.reachabilityEngine_bounded_complete`. Exact-depth
state layers are proved equivalent to `Kernel.ReachableAt`; action-path
enumeration runs only after a bad reachable state is found so a native trace
can be reconstructed.

This is not completeness of retrieval, modeling, natural-language
understanding, real-world observation, or any workflow outside the frozen
Boolean schema.

## `SAFE_WITHIN_BOUND`

`SAFE_WITHIN_BOUND` means no semantic first-bad trace exists with action count
at or below the configured bound. The theorem is
`TrackBReplay.reachabilityEngine_safeWithinBound_sound`; the proof-carrying
executable boundary is `TrackBReplay.checked_bounded_safe_endToEnd`. Its exact
`BoundedSafetyResult` is carried in `CheckedGeneratedBoundedSafety` together
with the engine-outcome equality, generated-result equality, and semantic
no-counterexample proof. The executable emits that carried result rather than
reconstructing another artifact.

It does not mean all-depth safety. A regression test uses a workflow that is
safe at bound 0 but reaches a forbidden state at step 1, and verifies that the
engine returns only `SAFE_WITHIN_BOUND`.

## `GLOBALLY_SAFE`

`GLOBALLY_SAFE` means every state reachable at any finite depth under the exact
closed TrackB kernel is non-forbidden. It is emitted only if an independent
finite certificate check verifies:

1. the initial state is in the supplied set;
2. every supplied state is non-forbidden; and
3. every enabled successor of every supplied state is also in the set.

The `Workflow.GloballySafe` proposition also contains a witness that the
workflow compiled successfully. A malformed workflow therefore cannot satisfy
the proposition merely because there is no compiled kernel to inspect.

Induction on reachability then proves that every reachable state is in that
set. The relevant results are:

- `TrackBReplay.SafetyCertificate.check_sound`;
- `TrackBReplay.reachabilityEngine_globallySafe_sound`; and
- `TrackBReplay.GlobalSafetyResult.semanticCheck_sound`.

Native metadata is a separate proposition:
`TrackBReplay.GlobalSafetyResult.MetadataConsistent`. The theorem
`TrackBReplay.GlobalSafetyResult.metadataCheck_iff` states that the executable
metadata check is equivalent to that proposition. The full
`TrackBReplay.GlobalSafetyResult.check_sound` theorem returns both
`Workflow.GloballySafe` and `MetadataConsistent`; neither half is presented as
establishing the other. `check_globallySafe` is the compatibility projection
for callers that need only the semantic consequence.

`TrackBReplay.checked_global_endToEnd` additionally binds the emitted native
global result to the exact closure that generated it, its checker acceptance,
and the `Workflow.GloballySafe` proposition.

This is an all-depth theorem about the exact declared finite transition model.
It is not universal filesystem safety, external-system safety, objective truth,
or proof that the model includes every runtime behavior.

## Concrete guarded workflows

Lean proves the following exact typed workflows globally safe:

- `email_requires_approval_globally_safe`;
- `delete_requires_confirmation_globally_safe`; and
- `vendor_payment_guarded_globally_safe`.

Their finite certificates contain 6, 5, and 16 states respectively. The
concrete checks reduce in the Lean kernel. Separately,
`trackb-guarded-fixture-check` confirms that each checked-in JSON file parses to
the exact typed workflow used by its theorem, and the release gate fixes each
file by SHA-256.

These results prove the modeled guard properties only. They do not authenticate
approval, confirmation, vendor identity, reviewer identity, external service
behavior, or filesystem effects.

## Optional Z3 boundary

The Z3 module is outside the theorem-backed search authority. It may propose a
native `UNSAFE` witness, but:

- SAT has no authority until the exact pair passes Lean replay;
- UNSAT is only `no_candidate_advisory`;
- unknown, error, and timeout are explicit nonzero outcomes; and
- no solver response becomes `SAFE` or `GLOBALLY_SAFE`.

The authoritative bounded-safe and global-safe decisions come from the Lean
reachability engine and certificate checker, not Z3.

## ReplayGuard and Evidence-to-Action

This repository contains no Lean semantics or proofs for ReplayGuard or
Evidence-to-Action and does not establish:

- ReplayGuard schema-1.1 certificate validity;
- correctness of ReplayGuard evaluation recomputation performed by a separate
  Evidence-to-Action runtime;
- correctness of a separate runtime's exact certificate-to-route authorization
  binding;
- Python-to-Lean correspondence for those projects; or
- global safety of their host-language or filesystem behavior.

Separate ReplayGuard/Evidence-to-Action releases may implement and test those
runtime contracts, but they remain outside this TrackB theorem boundary. The
design document in this repository is future formalization work, not an
implemented TrackB layer.

## Trusted computing base

The theorems cover pure Lean structures and functions after parsing. The
following remain trusted:

- the Lean parser, elaborator, kernel, compiler, code generator, and runtime;
- operating-system I/O and process execution;
- the exact toolchain identified by `lean-toolchain`;
- SHA-256 implementations used by release/receipt tooling; and
- the user's assertion of authorship and authorization for the included work.

The parser-to-concrete-model boundary is checked by a Lean executable rather
than a Python semantic translator. No claim is made that the JSON parser itself
has been formally verified.

## Explicit nonclaims

TrackB v0.2.1 does not prove:

- completeness or truth of a workflow model;
- complete retrieval or evidence collection;
- model understanding or agent intent;
- authenticated human identity or authorization outside modeled Boolean bits;
- hostile-kernel, compiler, OS, or hardware resistance;
- universal or production filesystem safety;
- production certification;
- ReplayGuard/Evidence-to-Action cross-project correctness; or
- any SAT, complexity-class, RCV, or P-versus-NP claim.

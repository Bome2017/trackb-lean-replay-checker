# Claim boundaries

## What a PASS means

A `PASS` means the exact parsed TrackB v0.1 workflow/result pair contains a
well-formed concrete trace such that:

- the workflow and result identifiers, schema version, bound, and forbidden
  condition agree;
- step 0 exactly matches the workflow's initial state;
- every later step names a declared action whose preconditions hold;
- each next state is exactly the prior state with that action's effects applied,
  including persistence of variables without effects;
- each reported state delta is exact;
- trace steps are sequential and the action count is at most the workflow
  bound;
- no earlier trace state is forbidden; and
- the final trace state satisfies the forbidden predicate.

`TrackBReplay.check_sound` proves in Lean that an executable `true` result
entails the proposition `TrackBReplay.ValidCounterexample`.

## What a PASS does not mean

A `PASS` does not prove:

- global safety or unsafety beyond the supplied bounded model;
- `SAFE_WITHIN_BOUND`;
- completeness, optimality, or first-found behavior of the Python BFS or Z3
  backend;
- equivalence between arbitrary Action Gate inputs and TrackB workflows;
- correctness of the Lean JSON parser, compiler, code generator, runtime, OS,
  or SHA-256 wrapper;
- production certification; or
- any SAT, complexity-class, RCV, or P-versus-NP claim.

## Trusted boundary

The proof covers the pure Lean structures produced by parsing and the checker
defined over those structures. The Lean JSON parser, compiler/kernel/code
generator/runtime, operating-system I/O, and Python digest wrapper remain in the
trusted computing base. The Python wrapper does not translate workflow
semantics: it copies exact input bytes, launches the Lean executable, and hashes
the same bytes for the receipt.

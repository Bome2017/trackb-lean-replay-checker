# Semantics and input domain

## Canonical model

A valid TrackB workflow contains:

- `schema_version` exactly `"0.1"`;
- a non-empty workflow name;
- a non-negative natural-number action bound;
- uniquely named Boolean state variables;
- one total initial Boolean assignment;
- uniquely named actions with partial Boolean preconditions and effects; and
- one conjunctive partial Boolean forbidden condition under
  `forbidden.all`.

Validation compiles names and maps into a typed
`Vector Bool variables.length` state. Preconditions, effects, and the forbidden
condition become vectors of `Option Bool`. After compilation,
`Kernel.successors` is the sole transition implementation.

The workflow-level global-safety proposition requires an explicit successful
compilation witness. Compilation failure is not interpreted as global safety.

An enabled action produces exactly one successor. Variables absent from its
effects persist. Multiple enabled actions may produce the same successor.
Repeated actions and no-op transitions are allowed.

## Strict object shapes

The Lean parser rejects unknown members in:

- the workflow root;
- action objects;
- the `forbidden` wrapper;
- native `UNSAFE` result roots;
- violation objects;
- trace-step objects; and
- native `GLOBALLY_SAFE` result roots.

Boolean maps and `state_variables` intentionally have data-dependent member
names.

## Canonical JSON subset

Citable inputs should use:

- UTF-8 JSON;
- unique object member names;
- ordinary non-negative integer spellings for natural-number fields;
- JSON Boolean values for state values; and
- no NaN, Infinity, comments, or implementation-specific extensions.

The underlying JSON object representation canonicalizes member order. The
semantics is name-based before compilation, so source member order is not a
behavioral control. Duplicate member names and alternative numeric spellings
are outside the citable input subset even if a particular parser invocation
normalizes them.

## Edge cases

The formal kernel permits empty variable, action, precondition, effect, and
forbidden maps when the workflow otherwise validates.

- An empty precondition is always enabled.
- An empty effect is a no-op.
- An empty action list has no successors.
- An empty forbidden condition is true in every state, so the initial state is
  already forbidden and bounded search returns an action-count-zero
  counterexample.

These are mathematical schema behaviors, not recommendations for production
workflow design.

## Bounds and resources

The completeness theorem is mathematical for every natural bound. The
executable performs explicit state exploration and may consume exponential
time or memory in the number of Boolean variables. Resource exhaustion,
termination by the operating system, or unavailable runtime dependencies is an
error, never a safety conclusion.

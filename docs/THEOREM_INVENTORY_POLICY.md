# Theorem inventory policy

## Authority

`TheoremInventory.lean` is the authoritative theorem and axiom inventory.
It loads compiled modules through Lean, enumerates constants from each imported
kernel environment, resolves each constant's origin with
`Environment.getModuleIdxFor?`, and obtains transitive axioms with
`Lean.collectAxioms`.

Source text, `rg`, Python regular expressions, line layout, comments, strings,
and a manually maintained theorem count are not inputs to discovery. A future
source-text comparison may exist only as a nonauthoritative lint.

The tool is pinned to the repository's Lean toolchain. Its
`Lean.Expr.repr-v1` type representation is deterministic for that pinned Lean
version; a toolchain change requires review of the generated inventory hash.

## Complete release surface

The default import roots are:

- `AxiomCheck`;
- `Main`;
- `SearchMain`;
- `SafetyMain`; and
- `FixtureMain`.

`AxiomCheck` transitively imports the proof-bearing library surface. The four
executables are loaded in independent environments because each intentionally
defines the global name `main`. The deterministic union is restricted by this
explicit owned-module allowlist:

- `TrackBSemantics`;
- `TrackBSafety`;
- `TrackBSearch`;
- `TrackBReplay`;
- `TrackBResults`;
- `GuardedExamples`;
- `AxiomCheck`;
- `Main`;
- `SearchMain`;
- `SafetyMain`; and
- `FixtureMain`.

Every allowlisted module must actually be present in at least one loaded
environment. Imported Lean or third-party declarations are excluded by origin
module, not by namespace spelling. `TheoremInventory` is release-audit tooling,
not a release semantics module, and is intentionally outside the owned-module
set. Its three `unsafe` declarations (`buildInventory`, `run`, and `main`) form
one narrow runtime call chain required by Lean's module-initializer loading API.
The release verifier permits exactly those reviewed audit-tool declarations;
they confer no unsafe declaration on an owned module.

Repeated observations of the same declaration from a shared import are
deduplicated only by origin module plus full declaration name. Inconsistent
types for the same identity fail the gate. Full theorem names remain the JSON
identity; leaf names are diagnostic only. Duplicate leaf names are preserved as
groups rather than collapsed.

## Authored and generated theorem constants

All owned `ConstantInfo.thmInfo` constants are inventoried and axiom-audited.
Lean also creates theorem constants for equation lemmas, proof helpers,
injectivity results, structure-field projections whose codomain is `Prop`, and
other elaboration products. These are not authored theorem commands.

Authorship is decided only from Lean environment metadata:

1. the declaration must have an exact entry in Lean's declaration-range
   extension; and
2. `Environment.isProjectionFn` must be false.

The exact-range lookup does not read or parse source locations. Generated
projections are therefore not mislabeled as authored even though Lean records a
field declaration range for them. All other theorem constants without an exact
authored range remain `generated`. Both sets retain their full types and
transitive axioms in the output.

The inventory reports separate counts for:

- every owned theorem constant;
- authored theorem declarations; and
- generated theorem constants.

## Classification

Every theorem record carries four Boolean decisions and one category:

- `publicApi`;
- `externallyCited`;
- `internalHelper`; and
- `exampleTheorem`.

Generated theorem constants have category `generated` and all four authored
classification flags are false.

For authored declarations, the deterministic default is `public_api`. Entries
listed in `internalHelpers` in
`docs/theorem_inventory_classification.json` become `internal_helper`.
Authored declarations originating in a listed `exampleModules` module become
`example_theorem`, unless explicitly classified as an internal helper.
`externallyCited` is an independent reviewed flag and does not change the main
category.

Every theorem name in the manifest must resolve to the environment-derived
authored subset. A missing name, a generated theorem name, a duplicate manifest
entry, an unknown example module, or a contradictory internal-and-cited entry
fails closed. The manifest classifies the discovered set; it never defines that
set or its count.

## Fail-closed checks

The default permitted transitive axioms are exactly:

- `Classical.choice`;
- `Quot.sound`; and
- `propext`.

The tool runs `Lean.collectAxioms` for:

1. every owned theorem constant, for per-theorem evidence; and
2. every owned constant of every declaration kind, so a definition or opaque
   declaration depending on a forbidden axiom cannot escape the theorem gate.

For any failure, `axiomOffendingConstants` records the exact origin module,
full name, declaration kind, and forbidden axiom list. The gate also fails on:

- any owned `axiomInfo`, including `sorryAx`;
- any unsafe owned declaration;
- an unloaded owned module;
- a forbidden transitive axiom;
- an inconsistent repeated theorem identity;
- a duplicate full theorem name across isolated release roots; or
- an invalid classification manifest.

The tool writes deterministic JSON before returning exit code `1` for a gate
failure, allowing hostile tests to inspect the evidence. Tool/configuration
errors return `2`; a complete passing inventory returns `0`.

## Generation

After the release modules have been built:

```text
python3 scripts/export_theorem_inventory.py
```

The wrapper invokes the Lean tool, validates only its schema and PASS status,
and hashes the exact emitted bytes. It performs no theorem discovery,
classification, or axiom analysis.

For isolated hostile modules, the same tool accepts repeatable `--import` and
`--owned-module` arguments:

```text
lake env lean --run /absolute/path/to/TheoremInventory.lean \
  --import Hostile \
  --owned-module Hostile \
  --output /absolute/path/to/inventory.json
```

The hostile module must first be compiled to an `.olean` in that Lake
environment. Quoted identifiers, Unicode identifiers, multiline syntax,
unusual whitespace, comments, and strings require no special handling because
the tool observes only the elaborated environment.

The Lean output retains `authored` as a receipt-oriented alias of its
`authoredDeclaration` decision, and the gate requires the two fields to be
identical. The wrapper does not rewrite theorem records. The release receipt
may mechanically compute SHA-256 over the UTF-8 bytes of an exact
`Lean.Expr.repr-v1` representation; that receipt-only digest is not a second
discovery or pretty-printing path.

`validation/theorem_inventory.json` and
`validation/theorem_inventory.sha256` are reviewed release inputs. A release
gate must regenerate both and compare their exact bytes to the reviewed
versions. A change is accepted only with the corresponding reviewed source,
classification-policy, or pinned-toolchain change.

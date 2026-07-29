# Hostile theorem-inventory gate

## Purpose

The TrackB theorem inventory is derived from Lean's elaborated environment.
This hostile suite verifies that valid Lean syntax and generated declarations
cannot bypass or confuse that inventory in the ways a source-text regular
expression can.

The suite invokes the same runtime `TheoremInventory.lean` program used by the
release gate. It does not use source parsing to decide which declarations are
theorems or which axioms they transitively depend on.

## Isolation

`tests/test_theorem_inventory_gate.py` generates three modules under a fresh
system temporary directory:

- `InventoryExternalFixture`, containing a theorem that is imported but not
  owned;
- `InventoryHostileSyntax`, containing valid hostile syntax and generated
  declarations; and
- `InventoryHostileUnsafe`, containing one theorem whose proof introduces
  `sorryAx`.

The modules are compiled to temporary `.olean` files before the inventory
program imports them. The temporary directory is placed on `LEAN_PATH` only for
the fixture compilation and inventory processes. The test removes it on
completion.

No hostile `.lean` or `.olean` fixture is stored in the repository. The
source-tracked Python test is a generator and test harness, not a TrackB theorem
module. Consequently no deliberately unsafe theorem is imported by the release
module surface.

## Required cases

| Case | Required result |
| --- | --- |
| Multiline theorem declaration | Discovered as an authored theorem |
| Unicode theorem name | Discovered with its full name and origin module |
| Quoted identifier | Discovered with its full name and uncollapsed leaf |
| Nested namespace | Namespace retained in the full name |
| Duplicate leaf names | Both distinct full names retained and reported |
| `sorryAx` dependency | The theorem is discovered and the gate exits 1 |
| Theorem-like comment text | Ignored |
| Theorem-like string text | Ignored |
| `def` containing the word `theorem` | Not classified as a theorem |
| Generated proof projection and recursor | Not classified as authored |
| Imported external theorem | Excluded from the explicitly owned set |
| Local owned theorem | Included with the temporary module as origin |
| Attribute block spanning lines | Authored theorem discovered |
| Unusual valid whitespace | Authored theorem discovered |

## Fail-closed axiom behavior

The syntax-only fixture must return exit code 0 and report:

- `checks.result = "PASS"`;
- `allOwnedConstantAxiomGatePassed = true`;
- `theoremAxiomGatePassed = true`;
- no owned axioms; and
- no axiom-offending constants.

The unsafe fixture must return exit code 1 while still writing its deterministic
inventory report. Its `sorryAx`-dependent theorem must:

- appear under the full name
  `InventoryHostileUnsafe.sorryAxDependent`;
- report `sorryAx` in `transitiveAxioms`;
- appear among `axiomOffendingConstants`; and
- make both the theorem and all-owned-constant axiom gates fail.

This proves that the authoritative environment enumeration sees the hostile
theorem before the axiom policy rejects it. A missing theorem cannot be treated
as a successful axiom audit.

## Generated declarations

A proof-valued structure projection may appear in the environment theorem
collection because its type is a proposition. When it appears, the inventory
must set:

- `authoredDeclaration = false`;
- `environmentProvenance.generatedProjection = true`;
- `environmentProvenance.kind = "generated"`; and
- `classification.category = "generated"`.

The structure recursor is an environment constant of recursor kind rather than
an authored theorem and must not enter the authored theorem set.

## Deterministic report

`validation/hostile_theorem_inventory_report.json` records the expected result
of every required case and SHA-256 hashes of the exact generated module source
strings. It contains no timestamp, temporary path, tool output ordering, or
machine-specific value. The test reconstructs the report and requires exact
equality with the source-tracked JSON.

The report's `PASS` describes this hostile regression only. It does not replace
the release inventory, the complete release axiom audit, the source-only clean
reproduction, or the immutable release receipt.

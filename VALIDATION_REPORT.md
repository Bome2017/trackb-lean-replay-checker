# Validation report

Date: 2026-07-27

## Release result

The narrow package passed its clean-build, proof-trust, negative-test, and
archived-runtime correspondence gates.

| Gate | Result |
|---|---|
| Build from a copy containing no `.lake`, `.olean`, `.ilean`, C, or object artifacts | PASS |
| Pinned toolchain | Lean 4.32.1, commit `f054605aea4b840552cca2e725580bffd1e1b704` |
| Lake dependencies | None |
| Source-tree symlinks | None |
| Registered/default Lean targets | 3 of 3 |
| End-to-end tests | 5 of 5 passed |
| Archived `UNSAFE` workflow/result pairs with matching source workflows | 19 of 19 passed |
| Active `sorry`, `admit`, `axiom`, or `unsafe` tokens in release Lean source | None |
| Exported checker theorem trust | Only `propext` and `Quot.sound` |

The 19 archived pairs include brute-force and Z3 results. Passing them
demonstrates that this checker accepts those concrete emitted traces under its
directly parsed TrackB v0.1 semantics. It does not prove either search backend
complete. The pair-level results are preserved in
`validation/archived_unsafe_pair_results.csv`, and one exact-input receipt is
preserved in `validation/agent_email_exfiltration_receipt.json`.

## Clean-build procedure

The source tree was copied to a fresh temporary directory while excluding
`.lake` and Python caches. Before the build, the copy contained no Lean build
artifacts. The following were then run in that copy:

```sh
lake --version
lean --version
lake build
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
lake env lean AxiomCheck.lean
```

Observed theorem-trust output:

```text
'TrackBReplay.check_iff' depends on axioms: [propext, Quot.sound]
'TrackBReplay.check_sound' depends on axioms: [propext, Quot.sound]
'TrackBReplay.check_complete' depends on axioms: [propext, Quot.sound]
```

## Tests

The release tests cover:

1. a valid concrete bounded counterexample;
2. a tampered successor state;
3. a workflow/result bound mismatch;
4. fail-closed rejection of a `SAFE_WITHIN_BOUND` result; and
5. SHA-256 receipt binding to exact workflow and result bytes.

## Reproduction

Run:

```sh
python3 scripts/verify_release.py
```

For the exact-input receipt path, build first and then use
`scripts/check_pair.py` as documented in the README.

This report is evidence for the enumerated package only. It is not a validation
report for the historical Lean corpus.

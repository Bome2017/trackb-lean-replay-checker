# TrackB v0.2 validation report

Date: 2026-07-27

Status: local release candidate; no v0.2 tag or remote push is asserted by this
report.

## Result

The v0.2 shared semantics, bounded search, native result packaging, global
certificate checker, and three concrete guarded-workflow proofs passed the
current clean-source gate.

| Gate | Result |
|---|---|
| Pre-build clean source copy | PASS: 42 files; no `.lake`, `.olean`, `.ilean`, C/object output, Python cache, or symlink |
| Pinned toolchain | PASS: Lean 4.32.1, commit `f054605aea4b840552cca2e725580bffd1e1b704`; Lake `5.0.0-src+f054605` |
| Lake dependencies | PASS: none |
| Registered default targets | PASS: 7 Lean libraries and 4 executables |
| Clean build | PASS: 33 build jobs |
| Python end-to-end and negative tests | PASS: 19 of 19 |
| Exported theorem dependency audit | PASS: 27 theorem checks |
| Permitted theorem assumptions | `propext`, `Classical.choice`, `Quot.sound` only |
| Incomplete/native-shortcut source tokens | PASS: none in release Lean source |
| Strict guarded fixture hashes | PASS: 3 of 3 |
| Lean JSON-to-theorem-model correspondence | PASS: 3 of 3 |
| Independent native global certificates | PASS: closures of 6, 5, and 16 states |
| Optional real Z3 proposal smoke test | PASS with isolated `z3-solver` 5.0.0 |

## Formal surface checked

The axiom gate covers:

- replay `check_iff`, soundness, and completeness;
- canonical transition reflection;
- finite-closure soundness;
- exact-depth state-layer reachability;
- bounded counterexample search soundness and completeness;
- all three reachability outcome soundness results;
- native global-result soundness;
- generated-result checker acceptance;
- proof-carrying end-to-end `UNSAFE`, bounded-safe, and global-safe packaging;
- exact compilation and reducible certificate checks for all three guarded
  workflows; and
- all three concrete global-safety theorems.

No fixture theorem uses `native_decide`. The concrete compilation and
certificate equalities close by kernel reduction.

## Guarded fixture binding

| Workflow | SHA-256 | Closed states | Result |
|---|---|---:|---|
| `agent_email_requires_approval` | `88fc0c4eb52487cf00a8dda32fb9dc14473b44ab694919ca82cbdf50097dabf9` | 6 | `GLOBALLY_SAFE` |
| `agent_delete_requires_confirmation` | `2c1adc8dfaac1ae2b16bf53115305024bdcee9b2ed9900927c4f557fa0836acd` | 5 | `GLOBALLY_SAFE` |
| `agent_vendor_payment_guarded` | `39a0ebcd1de6ba8ff673a98414b65ee344a22d2089a997e32822f6a673f4f740` | 16 | `GLOBALLY_SAFE` |

For every row:

1. the release gate recomputed the exact fixture digest;
2. `trackb-guarded-fixture-check` confirmed the Lean parser produced the exact
   typed workflow used by the concrete theorem;
3. `trackb-reachability` emitted a native closed-state certificate; and
4. `trackb-global-safety-check` independently accepted that certificate.

## Test coverage

The 19 tests comprise:

- 5 native replay/receipt tests;
- 6 reachability, result-lattice, fixture-correspondence, strict-parser, and
  global-certificate tests; and
- 8 optional-Z3 status/timeout/error/comparison-boundary tests.

Important negative cases include:

- tampered transitions;
- workflow/result bound mismatch;
- `SAFE_WITHIN_BOUND` sent to the `UNSAFE` checker;
- a workflow safe at bound 0 but bad at step 1;
- incomplete global closure;
- changed JSON that no longer matches the frozen theorem model;
- an extra forbidden-wrapper key;
- Z3 SAT rejected by Lean;
- Z3 unknown, timeout, and error; and
- Lean validation timeout.

## Optional Z3 smoke test

The repository has no required Z3 dependency. For one isolated validation, an
ephemeral virtual environment installed `z3-solver==5.0.0.0` (solver version
reported as `5.0.0`).

- The unsafe fixture produced `candidate_unsafe`; the exact generated pair was
  accepted by `trackb-replay-check`.
- The guarded delete fixture produced `no_candidate_advisory`, not any safety
  status.

This validates the adapter control flow for those cases. It does not give Z3
safety authority or prove its encoding complete.

## Clean-source procedure

A source-only copy was created while excluding `.git`, `.lake`, Lean build
artifacts, and Python caches. Before building, the copy contained 42 ordinary
files and no symlinks or generated artifacts. The following gate then passed:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify_release.py
```

That command performed the full build, 19 tests, guarded-fixture digest and
correspondence checks, and 27-theorem dependency audit.

## Nonclaims

This report validates only the enumerated local v0.2 release-candidate bytes.
It is not:

- a published release identity;
- a validation of the historical Lean corpus;
- proof that a workflow model is complete or true;
- universal runtime or filesystem safety; or
- ReplayGuard/Evidence-to-Action cross-project correctness.

See [CLAIM_BOUNDARIES.md](CLAIM_BOUNDARIES.md).

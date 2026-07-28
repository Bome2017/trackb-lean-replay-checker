# Optional Z3 witness proposer

`scripts/z3_witness_proposer.py` is an optional, proposal-only acceleration
layer. It is not part of the authoritative TrackB semantics kernel and it never
emits `SAFE` or `SAFE_WITHIN_BOUND`.

The authority flow is:

```text
exact native workflow JSON
  -> optional Z3 encoding
  -> possible native UNSAFE-shaped result
  -> exact-byte local TrackB Lean replay check
  -> candidate_unsafe proposal record
```

The final authority is the existing Lean replay checker applied to the exact
workflow/result pair. A consumer should preserve the candidate file and create
the normal `scripts/check_pair.py` receipt; it must not treat the proposer
record itself as a proof object.

## Status lattice and process exit

| Status | Meaning | CLI exit |
| --- | --- | ---: |
| `candidate_unsafe` | Z3 proposed a trace and the local Lean checker accepted the exact native pair | 0 |
| `no_candidate_advisory` | Every attempted Z3 query returned UNSAT | 0 |
| `inconclusive_unknown` | Z3 returned UNKNOWN for at least one query | 20 |
| `timeout` | Z3 or the Lean validation process timed out | 21 |
| `error` | Loading, encoding, solver, process, or validation failed | 22 |
| `error` with `comparison.status=mismatch` | Z3 proposed SAT but Lean rejected the candidate | 23 |

`no_candidate_advisory` is deliberately not a safety conclusion. The Z3
implementation, the proposal encoding, and Z3's UNSAT answer are not the
verified reachability kernel. Only `trackb-reachability`, backed by the proved
Lean state-layer engine, may authoritatively return a bounded-safe or
global-safe outcome.

## Captured provenance

Every proposal record includes:

- SHA-256 and byte length of the exact workflow;
- a length-framed SHA-256 digest covering the encoding identifier, workflow
  digest, timeout, and every SMT-LIB query attempted;
- solver version;
- per-query timeout;
- queried depths;
- `reason_unknown` when supplied by Z3;
- the Lean checker exit code and streams for SAT candidates;
- SHA-256 of an accepted native candidate.

The solver timeout is applied separately to each queried depth. The Lean
checker has a separate timeout.

## Optional dependency and usage

The repository does not require `z3-solver` to build or run its authoritative
Lean checker. Install the Python `z3-solver` package only when this optional
proposer is wanted, and record the version already captured by the output.

```sh
python3 scripts/z3_witness_proposer.py workflow.json \
  --output /tmp/z3-proposal.json \
  --candidate-result /tmp/z3-candidate.json \
  --timeout-ms 5000
```

If the status is `candidate_unsafe`, bind the exact accepted pair through the
normal receipt path:

```sh
python3 scripts/check_pair.py workflow.json /tmp/z3-candidate.json \
  --receipt /tmp/trackb-lean-replay-receipt.json
```

## Archived defect and correction

The immutable archived Z3 backend checked `result == sat` inside a loop and,
after every other response fell through, emitted `SAFE_WITHIN_BOUND`. That
conflated UNSAT with UNKNOWN and therefore also with common timeout outcomes.
The archive remains unchanged for provenance.

This proposer corrects the control flow:

- SAT is decoded only as a candidate and must pass Lean replay;
- UNSAT becomes `no_candidate_advisory`;
- UNKNOWN captures `reason_unknown`;
- timeout has a distinct status;
- import, encoding, solver, and process failures become `error`;
- a SAT/Lean disagreement is a nonzero comparison mismatch.

The Z3 encoding still duplicates enough transition structure to propose a
model. It is explicitly untrusted. No theorem or release claim should depend on
that encoding agreeing with the frozen TrackB semantics; the Lean checker
boundary exists precisely to remove that trust requirement for positive
counterexamples.

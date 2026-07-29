# Migrating from TrackB v0.1.0 to v0.2.1

TrackB v0.2.1 preserves the v0.1 native replay use case and adds one shared
Lean transition kernel, authoritative bounded search, and checked finite-state
global-safety certificates. Migration does not modify or reinterpret the
historical v0.1.0 release.

## Choose the release deliberately

Continue to cite v0.1.0 for evidence produced and retained under that exact
release. Use v0.2.1 only after the public `v0.2.1` tag exists and its peeled
commit, release receipt, and deterministic source archive have been verified.
A local candidate tag or mutable branch is not a public dependency.

For source dependencies, pin the exact public v0.2.1 commit recorded by the
release manifest. Do not pin `main`.

## Compatibility

- The external workflow `schema_version` remains `"0.1"`.
- Existing valid v0.1 `UNSAFE` workflow/result pairs remain supported by
  `trackb-replay-check`.
- The pinned Lean toolchain remains `leanprover/lean4:v4.32.1`.
- `TrackBReplay.check_sound` remains the native replay acceptance theorem.
- The public v0.1 map observations and transition name remain compatibility
  adapters over the single typed kernel.
- No Mathlib or other Lake package is introduced.

Re-run inputs rather than assuming byte-level acceptance. v0.2.1 uses strict
object-shape validation and the citable JSON subset requires unique member
names, ordinary non-negative integer spellings, JSON Booleans, and no parser
extensions.

## New capabilities

In addition to `trackb-replay-check`, v0.2.1 supplies:

- `trackb-reachability`, which emits exactly one of `UNSAFE`,
  `SAFE_WITHIN_BOUND`, or `GLOBALLY_SAFE`;
- `trackb-global-safety-check`, which independently checks a native global
  finite-closure result; and
- `trackb-guarded-fixture-check`, which checks exact JSON-to-typed-theorem
  correspondence for the guarded fixtures.

The status meanings are not interchangeable:

| Status | Migrated interpretation |
|---|---|
| `UNSAFE` | A native first-bad trace at or below the configured bound passed the replay checker |
| `SAFE_WITHIN_BOUND` | No semantic first-bad trace exists at or below that bound; this is not an all-depth claim |
| `GLOBALLY_SAFE` | A checked finite initial-containing, non-forbidden, successor-closed set proves all-depth safety in the exact declared finite model |
| process error | Parsing, compilation, reconstruction, packaging, or I/O failed; there is no safety result |

All semantic statuses use exit code 0 and must be distinguished through the
JSON `status` field. Errors use exit code 2. A certificate-check failure uses
exit code 1.

## Minimal operational migration

Build the exact pinned source and run its complete gate:

```sh
lake build
candidate_commit="$(git rev-parse HEAD)"
candidate_tree="$(git rev-parse 'HEAD^{tree}')"
candidate_branch="$(git branch --show-current)"
candidate_remote="$(git remote get-url origin)"
PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify_release.py \
  --expected-commit "$candidate_commit" \
  --expected-tree "$candidate_tree" \
  --expected-branch "$candidate_branch" \
  --expected-remote "$candidate_remote" \
  --require-no-lake-at-start
```

The v0.1 replay command is unchanged:

```sh
lake exe trackb-replay-check \
  fixtures/unsafe_workflow.json \
  fixtures/unsafe_result.json
```

For authoritative bounded search:

```sh
lake exe trackb-reachability workflow.json > result.json
```

Read `result.json` only after the process succeeds, then branch on its exact
`status`. Never translate process failure into `SAFE_WITHIN_BOUND` or
`GLOBALLY_SAFE`.

For a `GLOBALLY_SAFE` result, perform the independent native certificate check:

```sh
lake exe trackb-global-safety-check workflow.json result.json
```

The v0.2.1 release does not include an independent native JSON parser/checker
for `SAFE_WITHIN_BOUND`. That JSON result is trustworthy at the executable
boundary because the emitter serializes the exact result carried by the
proof-bearing checked outcome. A detached bounded-result JSON file is not a
portable independently recheckable certificate in this release.

## Lean API migration

The implementation is now split across focused modules:

- `TrackBSemantics` defines and compiles the external model into the typed
  Boolean kernel;
- `TrackBSafety` defines reachability and finite-closure safety;
- `TrackBSearch` defines exact-depth exploration and bounded completeness;
- `TrackBReplay` retains native `UNSAFE` replay checking;
- `TrackBResults` packages proof-bound native outcomes; and
- `GuardedExamples` contains the concrete guarded-workflow theorems.

Existing replay-only users may continue importing `TrackBReplay`. Users of
result packaging should import `TrackBResults`; users should import the
narrowest module that owns the definition or theorem they consume.

For global results, migrate away from treating one Boolean check as a single
undifferentiated proposition:

- `GlobalSafetyResult.semanticCheck_sound` establishes
  `Workflow.GloballySafe`;
- `GlobalSafetyResult.MetadataConsistent` is the native metadata proposition;
- `GlobalSafetyResult.metadataCheck_iff` connects the executable metadata
  check to that proposition; and
- `GlobalSafetyResult.check_sound` returns both semantic safety and metadata
  consistency.

Do not describe the semantic theorem as proving metadata consistency, or the
metadata theorem as proving global safety.

For bounded results, use the exact proof-bearing packaging theorem
`checked_bounded_safe_endToEnd`. The result carried by
`CheckedGeneratedBoundedSafety` is definitionally tied to the engine outcome,
generated visited/frontier sets, and no-counterexample theorem. Do not discard
that package and reconstruct a lookalike JSON object.

## Evidence and receipt migration

Do not carry a v0.1 receipt forward as evidence for v0.2.1. Generate new
receipts with the exact v0.2.1 executable and exact input bytes. For release
evidence, verify:

- the public tag object and peeled commit;
- `RELEASE_MANIFEST.json`;
- `trackb-v0.2.1-release-receipt.json` and its sidecar digest;
- `SHA256SUMS`;
- the deterministic source archive and archive-content manifest; and
- the environment-derived theorem inventory and its digest.

The authoritative theorem gate is environment-derived. `AxiomCheck.lean`
compile-checks important theorem shapes but is not a hand-maintained inventory
of release theorems.

## Claim migration

The new search and safety results remain bounded by the declared Boolean model:

- bounded completeness is only for semantic first-bad traces in the exact
  compiled kernel;
- `SAFE_WITHIN_BOUND` is never global safety;
- `GLOBALLY_SAFE` is all-depth only within the exact finite model;
- neither status proves model completeness, real-world truth, authenticated
  authorization, external service behavior, or universal filesystem safety;
  and
- TrackB v0.2.1 does not prove ReplayGuard or Evidence-to-Action correctness.

Review `CLAIM_BOUNDARIES.md` and `SEMANTICS_AND_INPUT_DOMAIN.md` before citing
or integrating a new status.

## Correspondence packages

The existing replay-obstruction correspondence v0.1.1 remains valid at its
exact TrackB v0.1.0 pin. No migration is required merely because TrackB
v0.2.1 is published.

If a correspondence package adopts or cites TrackB v0.2.1, release a new
correspondence version. Pin the exact public v0.2.1 peeled commit, update the
dependency and citation evidence, and re-run the correspondence package's
complete clean-source validation. Do not edit or retag the existing v0.1.1
release.

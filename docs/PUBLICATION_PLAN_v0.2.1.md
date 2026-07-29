# TrackB v0.2.1 publication plan

Status: plan only. Nothing in this document authorizes a push, a public tag, a
GitHub release, signing, or modification of an existing release.

## Publication boundary

TrackB v0.2.1 may be published only from the exact commit and tree recorded in
the completed local `RELEASE_MANIFEST.json`. The release manifest must also
bind the verified local annotated candidate tag, release receipt, deterministic
source archive, and archive-content manifest. A branch name or an uncommitted
worktree is not a publication identity.

The public `v0.1.0` tag and all of its assets are immutable historical
evidence. They must not be moved, deleted, replaced, or relabeled. Publication
of v0.2.1 is a new fast-forward commit, a new annotated `v0.2.1` tag, and a new
set of assets.

The public state observed during local preparation was:

- repository: `https://github.com/Bome2017/trackb-lean-replay-checker.git`;
- `main`: `888e112aab92a9313c095d803de695efa18fd700`;
- `v0.1.0` tag object:
  `f6de933a347cff5c59ac4b01d672d49bf56e7dd9`;
- `v0.1.0` peeled commit:
  `e4902a09f0f59447225555cf97b9c244631e9cb8`; and
- no public `v0.2.1` tag.

That is a dated observation, not permission to assume the remote remains
unchanged. The publication operator must fetch and compare the live state
immediately before pushing. Any discrepancy stops publication for review.

## Required local inputs

The publication operator must have:

1. the clean repository containing the verified final commit;
2. the completed external local release package;
3. `validation/RELEASE_MANIFEST.json` from that package;
4. the exact local annotated tag named by that manifest;
5. explicit authorization covering the exact commit, public tag, and assets;
   and
6. authenticated, least-privilege access to the configured public remote.

The following values are fail-closed inputs, not editable publication choices:

| Variable | Authoritative source |
|---|---|
| final commit | `RELEASE_MANIFEST.json` repository commit |
| final tree | `RELEASE_MANIFEST.json` repository tree |
| local candidate tag | `RELEASE_MANIFEST.json` local-tag name |
| local tag object | `RELEASE_MANIFEST.json` local-tag object |
| local tag peeled commit | `RELEASE_MANIFEST.json` local-tag peeled commit |
| receipt filename and SHA-256 | `RELEASE_MANIFEST.json` receipt fields |
| source archive filename and SHA-256 | `RELEASE_MANIFEST.json` source-archive fields |
| archive manifest filename and SHA-256 | `RELEASE_MANIFEST.json` archive-manifest fields |

The proposed public tag is exactly `v0.2.1`. It must point at the manifest's
final commit. It must not be an alias for, or rename of, the local
`v0.2.1-local-release-candidate` tag.

## Proposed immutable release assets

Upload the exact bytes from the completed local release package:

- the deterministic source archive named by the release manifest;
- its archive-content manifest;
- `trackb-v0.2.1-release-receipt.json`;
- `trackb-v0.2.1-release-receipt.sha256`;
- `RELEASE_MANIFEST.json`;
- `SHA256SUMS`;
- `theorem_inventory.json`;
- `theorem_inventory.sha256`;
- `release-gate-summary.json`;
- `source-only-release-gate-summary.json`;
- `bounded_result_emission_report.json`; and
- `hostile_theorem_inventory_report.json`.

Do not rebuild, normalize, rename, recompress, or replace an asset during
publication. GitHub-generated source archives are convenience downloads, not
the deterministic archive identified by the TrackB receipt. If any upload is
wrong, stop and issue a new version under a new tag; do not overwrite an
asset that has been cited or downloaded.

No binary is proposed as a v0.2.1 release asset. The citable artifact is the
pinned source plus its source-only reproduction evidence.

## Fail-closed prepublication checks

After explicit authorization, but before the first mutation of the remote:

1. Parse every required identity and digest from `RELEASE_MANIFEST.json`.
   Reject absent, empty, malformed, or duplicate values.
2. Verify the release manifest and receipt against their sidecar hashes and
   `SHA256SUMS`.
3. Verify that the local candidate tag object equals the manifest's tag object,
   peels to the manifest's final commit, and contains the receipt and source
   archive SHA-256 values.
4. Verify that the final commit resolves to the manifest's tree and that the
   worktree is clean.
5. Verify that the final commit descends from both the immutable public
   `v0.1.0` commit and the freshly fetched public `main`.
6. Verify that the fetched public `main` is still the exact reviewed
   prepublication commit.
7. Verify that the public `v0.1.0` tag object and peeled commit are unchanged.
8. Verify that `refs/tags/v0.2.1` is absent both locally and remotely.
9. Verify that every proposed asset exists exactly once and hashes to the
   value bound by the package manifests.
10. Verify that `RELEASE_NOTES_v0.2.1.md`,
    `docs/MIGRATION_v0.1.0_TO_v0.2.1.md`, `CITATION.cff`, and
    `CLAIM_BOUNDARIES.md` are present in the final tree.

Any failed check ends the attempt without a push.

## Exact authorized publication sequence

The operator must substitute only local filesystem locations and the freshly
reviewed prepublication `main` value. All release identities and hashes come
from the manifest or Git object database.

1. Fetch `main`, `v0.1.0`, and the remote tag namespace. Re-run every
   prepublication check above.
2. Perform a dry-run of exactly the final commit to `refs/heads/main`.
3. Push only the final commit to `refs/heads/main`. A non-fast-forward rejection
   is a stop condition; do not force.
4. Fetch `main` again and require its remote object ID to equal the manifest's
   final commit.
5. Create one annotated local tag named `v0.2.1` at that exact commit. Its
   annotation must record the final commit, tree, release-receipt SHA-256,
   source-archive SHA-256, and archive-manifest SHA-256. Do not sign it unless a
   separate signing policy and authorization are supplied.
6. Verify the new tag locally, then push only
   `refs/tags/v0.2.1:refs/tags/v0.2.1`.
7. Fetch the tag from the remote and require its peeled commit to equal the
   manifest's final commit.
8. Create the GitHub release from the existing `v0.2.1` tag. Use
   `RELEASE_NOTES_v0.2.1.md` as the release-note source and upload only the
   assets listed above.
9. Download the published assets into a fresh empty directory and recompute
   every SHA-256. Require byte identity with the local package.
10. Record the public tag object, peeled commit, release URL, asset names,
    sizes, and hashes in the publication record. Make no post-publication
    mutation to v0.2.1.

The branch push, tag push, and release creation are deliberately separate.
That makes each remote transition observable and prevents a broad `--tags` or
multi-ref push.

After the manifest values have been loaded and all checks above have passed,
the only permitted Git ref mutations are equivalent to this sequence:

```bash
set -euo pipefail

: "${FINAL_COMMIT:?load from the verified release manifest}"
: "${FINAL_TREE:?load from the verified release manifest}"
: "${LOCAL_CANDIDATE_TAG:?load from the verified release manifest}"
: "${LOCAL_TAG_OBJECT:?load from the verified release manifest}"
: "${LOCAL_TAG_PEELED_COMMIT:?load from the verified release manifest}"
: "${RECEIPT_SHA256:?load from the verified release manifest}"
: "${SOURCE_ARCHIVE_SHA256:?load from the verified release manifest}"
: "${ARCHIVE_MANIFEST_SHA256:?load from the verified release manifest}"

PUBLIC_TAG=v0.2.1
EXPECTED_PUBLIC_MAIN=888e112aab92a9313c095d803de695efa18fd700
V010_TAG_OBJECT=f6de933a347cff5c59ac4b01d672d49bf56e7dd9
V010_COMMIT=e4902a09f0f59447225555cf97b9c244631e9cb8

test "$(git remote get-url origin)" = \
  "https://github.com/Bome2017/trackb-lean-replay-checker.git"
git fetch --no-tags origin refs/heads/main
test "$(git rev-parse FETCH_HEAD)" = "$EXPECTED_PUBLIC_MAIN"
test "$(git rev-parse "$FINAL_COMMIT^{tree}")" = "$FINAL_TREE"
test "$(git rev-parse "refs/tags/$LOCAL_CANDIDATE_TAG")" = \
  "$LOCAL_TAG_OBJECT"
test "$(git rev-parse "refs/tags/$LOCAL_CANDIDATE_TAG^{commit}")" = \
  "$LOCAL_TAG_PEELED_COMMIT"
test "$LOCAL_TAG_PEELED_COMMIT" = "$FINAL_COMMIT"
git merge-base --is-ancestor "$EXPECTED_PUBLIC_MAIN" "$FINAL_COMMIT"
git merge-base --is-ancestor "$V010_COMMIT" "$FINAL_COMMIT"
test "$(git rev-parse refs/tags/v0.1.0)" = "$V010_TAG_OBJECT"
test "$(git rev-parse "refs/tags/v0.1.0^{commit}")" = "$V010_COMMIT"

REMOTE_V010_OBJECT=$(
  git ls-remote --tags origin refs/tags/v0.1.0 |
    awk '$2 == "refs/tags/v0.1.0" { print $1 }'
)
REMOTE_V010_COMMIT=$(
  git ls-remote --tags origin "refs/tags/v0.1.0^{}" |
    awk '$2 == "refs/tags/v0.1.0^{}" { print $1 }'
)
test "$REMOTE_V010_OBJECT" = "$V010_TAG_OBJECT"
test "$REMOTE_V010_COMMIT" = "$V010_COMMIT"

if git show-ref --verify --quiet "refs/tags/$PUBLIC_TAG"; then
  exit 1
fi
REMOTE_V021=$(
  git ls-remote --tags origin "refs/tags/$PUBLIC_TAG" \
    "refs/tags/$PUBLIC_TAG^{}"
)
test -z "$REMOTE_V021"

git push --dry-run origin "$FINAL_COMMIT:refs/heads/main"
git push origin "$FINAL_COMMIT:refs/heads/main"
REMOTE_MAIN=$(
  git ls-remote --heads origin refs/heads/main |
    awk '$2 == "refs/heads/main" { print $1 }'
)
test "$REMOTE_MAIN" = "$FINAL_COMMIT"

git tag -a "$PUBLIC_TAG" "$FINAL_COMMIT" \
  -m "TrackB v0.2.1" \
  -m "commit $FINAL_COMMIT" \
  -m "tree $FINAL_TREE" \
  -m "release receipt sha256 $RECEIPT_SHA256" \
  -m "source archive sha256 $SOURCE_ARCHIVE_SHA256" \
  -m "archive manifest sha256 $ARCHIVE_MANIFEST_SHA256"
test "$(git rev-parse "$PUBLIC_TAG^{commit}")" = "$FINAL_COMMIT"
git push origin "refs/tags/$PUBLIC_TAG:refs/tags/$PUBLIC_TAG"
REMOTE_V021_COMMIT=$(
  git ls-remote --tags origin "refs/tags/$PUBLIC_TAG^{}" |
    awk -v ref="refs/tags/$PUBLIC_TAG^{}" '$2 == ref { print $1 }'
)
test "$REMOTE_V021_COMMIT" = "$FINAL_COMMIT"
```

Before this block, the operator must also compare the live remote v0.1.0 tag
object and peeled commit with `V010_TAG_OBJECT` and `V010_COMMIT`; the local
checks alone are insufficient. If the current public `main` is no longer
`EXPECTED_PUBLIC_MAIN`, stop and review the new ancestry and release evidence
instead of editing the variable and continuing.

## Release notes and citation

The public release notes are `RELEASE_NOTES_v0.2.1.md`. They must preserve the
bounded claim language in `CLAIM_BOUNDARIES.md`, including the separation
between global-safety semantics and native metadata consistency and the
deferral of an independent bounded-result JSON checker.

`CITATION.cff` in the final tree already identifies version `0.2.1` and the
public repository. After publication, citations should identify the
`v0.2.1` release and its exact peeled commit. Do not cite the local candidate
tag as a public release. If a DOI is minted later, add it to external release
metadata without moving this tag; a source-level citation change belongs in a
new commit and, if released, a new version.

If any citation or release-note source field must change before publication,
make that change before the final validation and rebuild the complete local
release package. Do not patch the validated tree after its receipt is made.

## Correspondence package disposition

The existing replay-obstruction correspondence package v0.1.1 remains valid
and immutable at its existing TrackB v0.1.0 pin. Publishing TrackB v0.2.1 does
not invalidate it and does not by itself require a correspondence release.

A new correspondence-package version is required only if that package adopts
or cites TrackB v0.2.1. Such a version must pin the exact public v0.2.1 peeled
commit, update its citation and dependency evidence, and pass that project's
complete validation from a clean source checkout. It must not rewrite the
existing v0.1.1 release or point at a mutable branch or local candidate tag.

## Stop point

This plan stops before publication. The sole next action after all mandatory
local gates pass is to obtain explicit authorization to push the exact
validated commit, create the public `v0.2.1` tag, and publish the immutable
release assets.

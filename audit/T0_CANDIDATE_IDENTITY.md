# T0 Candidate Identity

Status: PASS

Recorded at: `2026-07-29T14:53:15Z`

## Candidate

- Path alias: `<local-candidate-worktree>` (absolute local path redacted from
  release source)
- Branch: `formal/v0.2.1-audit-repairs-2026-07-28`
- Starting commit: `07fe7333a004330c78eb2be484ae10d62e42c139`
- Starting tree: `c8c71b580fb7173fe844654fe54b0612a90037d0`
- Expected commit matched: yes
- Expected tree matched: yes
- Starting status: clean
- Tracked files: 43
- Tracked-index fingerprint: `ae80b7432b203e5fefdad1e7f0c8adbc3d3635325ea2ecc7bc17fed4ef59da7e`
- Porcelain-status fingerprint: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- Worktree diff fingerprint: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- Linked worktree: yes
- Common Git directory alias: `<local-canonical-public-worktree>/.git`
- Configured remote: `https://github.com/Bome2017/trackb-lean-replay-checker.git`
- Existing ignored build cache: `.lake/`, approximately 423 MiB
- `.lake`, Lean objects, Python caches, or generated build material tracked: no
- Git object alternates file: absent

The existing ignored `.lake` directory was not treated as reproducibility
evidence. Clean reproduction must start from a source-only tree without it.

## Toolchain and Lake project

- `lean-toolchain`: `leanprover/lean4:v4.32.1`
- Lean: `4.32.1`, commit `f054605aea4b840552cca2e725580bffd1e1b704`
- Lake: `5.0.0-src+f054605`
- Lake package: `trackb_lean_replay_checker`
- Lake package version: `0.2.1`
- External Lake packages: none

## Historical release ancestry

- Local tag: `v0.1.0`
- Tag object: `f6de933a347cff5c59ac4b01d672d49bf56e7dd9`
- Peeled commit: `e4902a09f0f59447225555cf97b9c244631e9cb8`
- Peeled tree: `3f7437318985ac231019d4e3cf61ed04f4bcfed4`
- Candidate descends from the peeled `v0.1.0` commit: yes

## Canonical public worktree and live remote

- Path alias: `<local-canonical-public-worktree>` (absolute local path redacted
  from release source)
- Branch: `main`
- Commit: `888e112aab92a9313c095d803de695efa18fd700`
- Tree: `98af1497765f2ccb14bdc9f3b93c6d7c0462c152`
- Starting status: clean
- Tracked files: 24
- Tracked-index fingerprint: `b24db796c80b81c71d66c5124e83b7999d11233c97140695defe2aea772d9674`
- Porcelain-status fingerprint: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- Worktree diff fingerprint: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- Live remote `refs/heads/main`: `888e112aab92a9313c095d803de695efa18fd700`
- Live remote `refs/tags/v0.1.0`: tag object
  `f6de933a347cff5c59ac4b01d672d49bf56e7dd9`, peeled commit
  `e4902a09f0f59447225555cf97b9c244631e9cb8`
- Public `v0.2.1` tag: absent

No remote mutation is authorized by this workstream.

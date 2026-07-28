# Rights and provenance

## Authorship and authorization

Sanjit Singh Mehat states that the authored project materials and underlying
system ideas are his work, developed under his direction with LLM assistance.
He authorized this narrow release and is named as its copyright holder.

LLM systems, including Claude and Codex, assisted with drafting,
implementation, and audit work. They are treated as tools, not authors or
rights holders. The human author selected the scope, supplied the source
systems and requirements, directed the work, and authorized the resulting
license.

## Clean release boundary

This package is a new, narrow implementation of the TrackB v0.2 shared
semantics, replay, bounded-search, and finite-certificate kernel. It does not
vendor:

- historical `.lake` build output or package caches;
- the absolute package symlinks found in archival Lean trees;
- the superseded loose `RSVT_Final.lean`;
- archival theorem families unrelated to concrete replay checking; or
- Python code from the archived TrackB verifier.

The runtime schema and examples informed the interface and acceptance tests.
Three guarded workflow fixtures are included byte-for-byte from the author's
archive and are covered by his authorization. The Lean implementation, Python
SHA-256 receipt wrapper, and optional fail-closed Z3 proposal adapter in this
package were written for this release.

## Reviewed source snapshot

The clean-room interface and tests were checked against these local source
bytes on 2026-07-27:

| Source | SHA-256 |
|---|---|
| `docs/TRACE_SCHEMA_CONTRACT.md` | `56729d2d53ab2733334f51f9ef67d93ba3016b46e68a6fa03b90aa83d0deb451` |
| `src/replay_model.py` | `d4c84ccb747c923cd3fa6526c77320727b404940358882dcc5fe2b1339c16bb1` |
| `src/solver_bruteforce.py` | `9096343b0a0304e33606d704edd30db6e4facf0b1b3d7ded5085e56fd51bf262` |
| `src/solver_z3.py` | `c06afe096cbf6495d8d9b9eb78efd097464afca0f0a812b57e6528e426f8e2a3` |
| `examples/agent_email_exfiltration/workflow.json` | `5175dcb7bd4b6b16ed06adac609beeddf99b854bc1a48b2460e6d38e9d97ace1` |
| `outputs/agent_email_exfiltration/result.json` | `3faef75267325b7c0187c2b6b771722c45911432c4df36e66f0bb5bbd1060f54` |
| `crsl_fork/FiniteReplay.lean` | `250eacb7cf7f901330daf71f5b6f6a5a54b2c237c59c3ca60ac5edb4694eb541` |

The table identifies reviewed inputs; it does not import or relicense those
historical files.

## License scope

Unless a file says otherwise, authored source, tests, fixtures, and
documentation in this repository are licensed under Apache License 2.0. The
license does not relicense external tools, Python, Lean, or any material not
included in this repository.

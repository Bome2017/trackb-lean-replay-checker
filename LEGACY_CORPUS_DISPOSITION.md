# Legacy corpus disposition

The external release boundary is this repository. The larger historical Lean
corpus is retained as research history and is not silently represented as
release-complete.

Known historical issues deliberately excluded from this package:

- the superseded loose `RSVT_Final.lean` contains two live proof-body `sorry`
  declarations;
- `rcv-proof/RCV/Epistemics.lean` contains a source-declared tautological axiom;
- `crsl_fork` has 13 registered libraries omitted from `defaultTargets`;
- `BRVReplaySatisfiabilityOfOutputPayloadsMatch.lean` is an unregistered,
  unimported source in the broad fork;
- `proposed_extensions/lake-manifest.json` has a root-name mismatch copied from
  `canonical_traced3sat`; and
- archival `.lake/packages` paths are absolute cache symlinks and are not
  portable release dependencies.

Those facts do not enter this package's proof closure. None of the affected
files is copied, imported, or cited as support for the checker theorem.

If a broader theorem-family release is later desired, it requires its own
curated source list, corrected Lake registration/default coverage, regenerated
manifest, fresh clean build, theorem-by-theorem axiom gate, and separate
rights/provenance record. Passing this package's gate must not be generalized to
that corpus.

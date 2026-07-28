# Frozen ReplayGuard to Evidence-to-Action certificate boundary

Status: design only. This document does not claim ReplayGuard or
Evidence-to-Action formal correctness.

TrackB v0.2 supplies the shared-kernel pattern needed for the next workstream:
one semantics must drive checking, search, and any safety certificate. The
downstream projects must not treat producer-supplied status or digest fields as
verified facts.

## Versioned certificate envelope

The proposed strict envelope is:

- certificate schema:
  `replayguard-assurance-certificate-v1`;
- evaluator profile:
  `schema11-deterministic-v1`;
- canonicalization:
  `replayguard-canonical-json-v1`;
- fixture schema exactly `1.1`;
- exact fixture byte length and SHA-256;
- fixture, claim, and evaluation identifiers;
- canonical claim bytes and SHA-256;
- exactly the five declared response cases, with no missing or extra case;
- a frozen deterministic evaluator manifest and digest;
- the recomputed stable evaluation payload and digest; and
- certificate status `PASS`, `FAIL`, or `INVALID`.

Model-assisted or automatic evaluation is outside this profile. Structural
defects, profile mismatch, unsupported versions, missing cases, extra cases,
digest mismatch, or recomputation disagreement produce `INVALID`.

## Checker API

The security boundary should expose an opaque checked value:

```text
verifyCertificate(exactCertificateBytes)
  -> VerifiedAssurance | VerificationError
```

Only the checker may construct `VerifiedAssurance`. It must:

1. parse the strict versioned envelope;
2. load or receive the exact bound fixture bytes;
3. recompute every declared digest;
4. run the frozen deterministic ReplayGuard evaluation;
5. compare the complete recomputed evaluation with the certificate;
6. enforce the five-case relational contract; and
7. return a checked value only for an exact passing certificate.

`assurance_status=PASS` and `evaluation_sha256` remain untrusted input until
these steps succeed.

## Evidence-to-Action consumption

Evidence-to-Action should accept `VerifiedAssurance`, not raw status/digest
fields. An execution attempt must bind:

- exact certificate digest;
- exact recomputed evaluation digest;
- exact authorized route identifier and route definition digest;
- exact action/arguments digest;
- policy and contract versions; and
- the decision that selected that route.

The current literal fixture-schema `1.0` requirement must be replaced by an
explicit versioned boundary. Schema `1.1` must not be accepted by merely
changing a string constant; the checker and receipt contract must agree on the
full structure and semantics.

No execution path may be reachable from an unchecked producer assertion.
Validation outcomes such as escalation must not silently become action
authorization.

## Python to Lean correspondence

Passing Python tests cannot establish Python-to-Lean correspondence. Before a
formal cross-project claim, choose one:

1. make the Lean checker authoritative on the runtime path; or
2. generate the Python and Lean kernels from one frozen declarative
   specification, then prove/check the generated correspondence.

Duplicating the semantics manually in two languages is not an acceptable
long-term authority boundary.

## Target theorem

The strongest honest target is:

> Accepted ReplayGuard schema-1.1 certificates satisfy the declared relational
> evidence contracts, and every valid Evidence-to-Action execution attempt
> derives from that exact passing certificate and an exact authorized route.

This would still not prove objective truth, complete retrieval, model
understanding, authenticated reviewer identity, hostile-kernel resistance, or
universal filesystem safety.

## Acceptance gates

Implementation is not complete until all of the following pass:

- schema 1.0 is rejected or handled through an explicit separately specified
  compatibility profile;
- schema 1.1 is recomputed rather than trusted;
- changing any fixture, response, manifest, route, action, or digest fails;
- missing/extra response cases fail;
- model-assisted evaluation fails for the deterministic profile;
- an E2A execution attempt cannot be constructed from raw producer fields;
- the runtime route uses the authoritative checker/specification;
- Python/Lean correspondence is checked at the chosen boundary; and
- claim-language and axiom gates pass in a clean source copy.

/-
SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
SPDX-License-Identifier: Apache-2.0
-/

import GuardedExamples

/-
This historical module name is retained as a compatibility target.  It now
compile-checks release-critical theorem shapes only.  It is deliberately not
the axiom-inventory authority: `TheoremInventory.lean` enumerates every
TrackB-owned theorem constant from Lean's elaborated environment and queries
its transitive axioms.
-/

-- Compile-check the exact result-bearing bounded-safety theorem shape.  A
-- theorem that drops the native result parameter cannot satisfy this example.
example
    {workflow : TrackBReplay.Workflow}
    {compiled : TrackBReplay.CompiledWorkflow workflow}
    (generated :
      TrackBReplay.CheckedGeneratedBoundedSafety workflow compiled) :
    TrackBReplay.EndToEndBoundedSafety
      workflow compiled generated.result :=
  TrackBReplay.checked_bounded_safe_endToEnd generated

-- Compile-check that semantic acceptance alone establishes the semantic
-- proposition, without requiring or projecting a metadata proof.
example
    {workflow : TrackBReplay.Workflow}
    {result : TrackBReplay.GlobalSafetyResult}
    (accepted : result.semanticCheck workflow = true) :
    workflow.GloballySafe :=
  TrackBReplay.GlobalSafetyResult.semanticCheck_sound accepted

-- Compile-check the exact proposition-level meaning of metadata acceptance.
example
    {workflow : TrackBReplay.Workflow}
    {result : TrackBReplay.GlobalSafetyResult}
    (accepted : result.metadataCheck workflow = true) :
    result.MetadataConsistent workflow :=
  TrackBReplay.GlobalSafetyResult.metadataCheck_iff.mp accepted

-- The full native checker proves both independent halves.
example
    {workflow : TrackBReplay.Workflow}
    {result : TrackBReplay.GlobalSafetyResult}
    (accepted : result.check workflow = true) :
    workflow.GloballySafe ∧ result.MetadataConsistent workflow :=
  TrackBReplay.GlobalSafetyResult.check_sound accepted

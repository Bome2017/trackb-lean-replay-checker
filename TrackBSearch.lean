/-
SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
SPDX-License-Identifier: Apache-2.0

Authoritative executable bounded reachability for the frozen TrackB kernel.
-/

import TrackBSafety

namespace TrackBReplay

/--
A metadata-free semantic state trace.  The initial constructor makes every
trace nonempty; each step records only the selected action name and successor
kernel state.
-/
inductive SemanticTrace (arity : Nat) where
  | initial (state : KernelState arity)
  | step (prior : SemanticTrace arity) (actionName : String)
      (after : KernelState arity)
  deriving Repr, DecidableEq

def SemanticTrace.initialState : SemanticTrace arity → KernelState arity
  | .initial state => state
  | .step prior _ _ => prior.initialState

def SemanticTrace.finalState : SemanticTrace arity → KernelState arity
  | .initial state => state
  | .step _ _ after => after

def SemanticTrace.actionCount : SemanticTrace arity → Nat
  | .initial _ => 0
  | .step prior _ _ => prior.actionCount + 1

def SemanticTrace.states : SemanticTrace arity → List (KernelState arity)
  | .initial state => [state]
  | .step prior _ after => prior.states ++ [after]

def SemanticTrace.actions : SemanticTrace arity → List String
  | .initial _ => []
  | .step prior actionName _ => prior.actions ++ [actionName]

/-- Initial-state equality followed by a chain of the one kernel transition. -/
def SemanticTrace.Valid
    (kernel : Kernel arity) : SemanticTrace arity → Prop
  | .initial state => state = kernel.initial
  | .step prior actionName after =>
      prior.Valid kernel ∧
      kernel.Transition prior.finalState actionName after

def SemanticTrace.validB
    (kernel : Kernel arity) : SemanticTrace arity → Bool
  | .initial state => state == kernel.initial
  | .step prior actionName after =>
      prior.validB kernel &&
      kernel.transitionB prior.finalState actionName after

theorem SemanticTrace.validB_iff
    {kernel : Kernel arity}
    {trace : SemanticTrace arity} :
    trace.validB kernel = true ↔ trace.Valid kernel := by
  induction trace with
  | initial state =>
      simp [SemanticTrace.validB, SemanticTrace.Valid]
  | step prior actionName after ih =>
      simp [
        SemanticTrace.validB,
        SemanticTrace.Valid,
        ih,
        Kernel.transitionB_iff
      ]

theorem SemanticTrace.states_ne_nil
    (trace : SemanticTrace arity) :
    trace.states ≠ [] := by
  cases trace <;> simp [SemanticTrace.states]

def SemanticTrace.priorSafeB
    (kernel : Kernel arity)
    (trace : SemanticTrace arity) : Bool :=
  trace.states.dropLast.all fun state => !kernel.forbiddenHolds state

def SemanticTrace.PriorSafe
    (kernel : Kernel arity)
    (trace : SemanticTrace arity) : Prop :=
  ∀ state, state ∈ trace.states.dropLast → ¬kernel.Forbidden state

theorem SemanticTrace.priorSafeB_iff
    {kernel : Kernel arity}
    {trace : SemanticTrace arity} :
    trace.priorSafeB kernel = true ↔ trace.PriorSafe kernel := by
  simp [
    SemanticTrace.priorSafeB,
    SemanticTrace.PriorSafe,
    Kernel.Forbidden
  ]

/--
The lower-level bounded counterexample proposition.  It mentions only the
kernel state trace and semantic obligations; workflow/result metadata and
human-readable strings are deliberately absent.
-/
def BoundedCounterexample
    (kernel : Kernel arity)
    (bound : Nat)
    (trace : SemanticTrace arity) : Prop :=
  trace.states ≠ [] ∧
  trace.Valid kernel ∧
  trace.actionCount ≤ bound ∧
  trace.PriorSafe kernel ∧
  kernel.Forbidden trace.finalState

def boundedCounterexampleB
    (kernel : Kernel arity)
    (bound : Nat)
    (trace : SemanticTrace arity) : Bool :=
  decide (trace.states ≠ []) &&
  trace.validB kernel &&
  decide (trace.actionCount ≤ bound) &&
  trace.priorSafeB kernel &&
  kernel.forbiddenHolds trace.finalState

theorem boundedCounterexampleB_iff
    {kernel : Kernel arity}
    {bound : Nat}
    {trace : SemanticTrace arity} :
    boundedCounterexampleB kernel bound trace = true ↔
      BoundedCounterexample kernel bound trace := by
  simp [
    boundedCounterexampleB,
    BoundedCounterexample,
    SemanticTrace.validB_iff,
    SemanticTrace.priorSafeB_iff,
    Kernel.Forbidden,
    and_assoc
  ]

def SemanticTrace.expand
    (kernel : Kernel arity)
    (trace : SemanticTrace arity) : List (SemanticTrace arity) :=
  (kernel.successors trace.finalState).map fun successor =>
    .step trace successor.1 successor.2

/-- All valid semantic traces of exactly the requested action depth. -/
def traceLayer
    (kernel : Kernel arity) : Nat → List (SemanticTrace arity)
  | 0 => [.initial kernel.initial]
  | depth + 1 =>
      (traceLayer kernel depth).flatMap (SemanticTrace.expand kernel)

/-- All valid semantic traces whose action count is at most `bound`. -/
def tracesUpTo
    (kernel : Kernel arity)
    (bound : Nat) : List (SemanticTrace arity) :=
  (List.range (bound + 1)).flatMap (traceLayer kernel)

/--
Exact-depth state reachability.  This is the authoritative bounded-safe
engine: it keeps canonical states rather than every action-path history.
-/
def Kernel.stateLayer
    (kernel : Kernel arity) : Nat → List (KernelState arity)
  | 0 => [kernel.initial]
  | depth + 1 =>
      ((kernel.stateLayer depth).flatMap fun state =>
        (kernel.successors state).map Prod.snd).eraseDups

def Kernel.stateLayers
    (kernel : Kernel arity)
    (bound : Nat) : List (List (KernelState arity)) :=
  (List.range (bound + 1)).map kernel.stateLayer

def Kernel.ReachableAt
    (kernel : Kernel arity) : Nat → KernelState arity → Prop
  | 0, state => state = kernel.initial
  | depth + 1, state =>
      ∃ before,
        kernel.ReachableAt depth before ∧
        ∃ actionName, kernel.Transition before actionName state

theorem Kernel.mem_stateLayer_iff
    (kernel : Kernel arity)
    (depth : Nat)
    (state : KernelState arity) :
    state ∈ kernel.stateLayer depth ↔ kernel.ReachableAt depth state := by
  induction depth generalizing state with
  | zero =>
      simp [Kernel.stateLayer, Kernel.ReachableAt]
  | succ depth ih =>
      simp [
        Kernel.stateLayer,
        Kernel.ReachableAt,
        Kernel.Transition,
        ih
      ]

theorem SemanticTrace.Valid.reachableAt
    {kernel : Kernel arity}
    {trace : SemanticTrace arity}
    (hvalid : trace.Valid kernel) :
    kernel.ReachableAt trace.actionCount trace.finalState := by
  induction trace with
  | initial state =>
      simpa [
        SemanticTrace.Valid,
        SemanticTrace.actionCount,
        SemanticTrace.finalState,
        Kernel.ReachableAt
      ] using hvalid
  | step prior actionName after ih =>
      rcases hvalid with ⟨hprior, htransition⟩
      exact ⟨prior.finalState, ih hprior, actionName, htransition⟩

def Kernel.coveredStates
    (kernel : Kernel arity)
    (bound : Nat) : List (KernelState arity) :=
  (kernel.stateLayers bound).flatten.eraseDups

theorem Kernel.stateLayer_mem_stateLayers_of_le
    (kernel : Kernel arity)
    {depth bound : Nat}
    (hdepth : depth ≤ bound) :
    kernel.stateLayer depth ∈ kernel.stateLayers bound := by
  apply List.mem_map.mpr
  exact ⟨
    depth,
    List.mem_range.mpr (Nat.lt_succ_of_le hdepth),
    rfl
  ⟩

theorem Kernel.mem_coveredStates_of_reachableAt
    {kernel : Kernel arity}
    {depth bound : Nat}
    {state : KernelState arity}
    (hdepth : depth ≤ bound)
    (hreachable : kernel.ReachableAt depth state) :
    state ∈ kernel.coveredStates bound := by
  apply List.mem_eraseDups.mpr
  apply List.mem_flatten_of_mem
    (kernel.stateLayer_mem_stateLayers_of_le hdepth)
  exact (kernel.mem_stateLayer_iff depth state).mpr hreachable

def findBadState?
    (kernel : Kernel arity)
    (bound : Nat) : Option (KernelState arity) :=
  (kernel.coveredStates bound).find? kernel.forbiddenHolds

theorem findBadState?_none_no_boundedCounterexample
    {kernel : Kernel arity}
    {bound : Nat}
    (hnone : findBadState? kernel bound = none) :
    ¬∃ trace, BoundedCounterexample kernel bound trace := by
  intro hexists
  rcases hexists with ⟨trace, hcounterexample⟩
  have hcovered : trace.finalState ∈ kernel.coveredStates bound :=
    kernel.mem_coveredStates_of_reachableAt
      hcounterexample.2.2.1
      hcounterexample.2.1.reachableAt
  have hnoneAll :=
    List.find?_eq_none.mp hnone trace.finalState hcovered
  exact hnoneAll hcounterexample.2.2.2.2

theorem SemanticTrace.valid_mem_traceLayer
    {kernel : Kernel arity}
    {trace : SemanticTrace arity}
    (hvalid : trace.Valid kernel) :
    trace ∈ traceLayer kernel trace.actionCount := by
  induction trace with
  | initial state =>
      simp [SemanticTrace.Valid] at hvalid
      subst state
      simp [traceLayer, SemanticTrace.actionCount]
  | step prior actionName after ih =>
      rcases hvalid with ⟨hprefix, htransition⟩
      have hmem := ih hprefix
      simp only [SemanticTrace.actionCount, traceLayer, List.mem_flatMap]
      refine ⟨prior, hmem, ?_⟩
      simp only [SemanticTrace.expand, List.mem_map]
      exact ⟨(actionName, after), htransition, rfl⟩

theorem SemanticTrace.valid_mem_tracesUpTo
    {kernel : Kernel arity}
    {bound : Nat}
    {trace : SemanticTrace arity}
    (hvalid : trace.Valid kernel)
    (hbound : trace.actionCount ≤ bound) :
    trace ∈ tracesUpTo kernel bound := by
  apply List.mem_flatMap.mpr
  exact ⟨
    trace.actionCount,
    List.mem_range.mpr (Nat.lt_succ_of_le hbound),
    trace.valid_mem_traceLayer hvalid
  ⟩

def findBoundedCounterexample?
    (kernel : Kernel arity)
    (bound : Nat) : Option (SemanticTrace arity) :=
  (tracesUpTo kernel bound).find? (boundedCounterexampleB kernel bound)

theorem findBoundedCounterexample?_sound
    {kernel : Kernel arity}
    {bound : Nat}
    {trace : SemanticTrace arity}
    (hfind : findBoundedCounterexample? kernel bound = some trace) :
    BoundedCounterexample kernel bound trace := by
  apply boundedCounterexampleB_iff.mp
  exact List.find?_some hfind

/--
Bounded completeness: if a semantic counterexample exists at or below the
operational horizon, authoritative search returns some checked counterexample.
-/
theorem findBoundedCounterexample?_complete
    {kernel : Kernel arity}
    {bound : Nat}
    (hexists : ∃ trace, BoundedCounterexample kernel bound trace) :
    ∃ found,
      findBoundedCounterexample? kernel bound = some found ∧
      BoundedCounterexample kernel bound found := by
  rcases hexists with ⟨trace, hcounterexample⟩
  have hmember := trace.valid_mem_tracesUpTo
    hcounterexample.2.1 hcounterexample.2.2.1
  have hpredicate : boundedCounterexampleB kernel bound trace = true :=
    boundedCounterexampleB_iff.mpr hcounterexample
  have hisSome : (findBoundedCounterexample? kernel bound).isSome = true := by
    apply List.find?_isSome.mpr
    exact ⟨trace, hmember, hpredicate⟩
  cases hfound : findBoundedCounterexample? kernel bound with
  | none => simp [hfound] at hisSome
  | some found =>
      exact ⟨
        found,
        by simp,
        findBoundedCounterexample?_sound hfound
      ⟩

theorem findBoundedCounterexample?_none_iff
    {kernel : Kernel arity}
    {bound : Nat} :
    findBoundedCounterexample? kernel bound = none ↔
      ¬∃ trace, BoundedCounterexample kernel bound trace := by
  constructor
  · intro hnone hexists
    rcases findBoundedCounterexample?_complete hexists with
      ⟨trace, hsome, _⟩
    simp [hnone] at hsome
  · intro hnone
    cases hfind : findBoundedCounterexample? kernel bound with
    | none => rfl
    | some trace =>
        exact False.elim (hnone ⟨trace, findBoundedCounterexample?_sound hfind⟩)

def visitedStates
    (kernel : Kernel arity)
    (bound : Nat) : List (KernelState arity) :=
  kernel.coveredStates bound

def frontierStates
    (kernel : Kernel arity)
    (bound : Nat) : List (KernelState arity) :=
  kernel.stateLayer bound

/--
One result lattice for the configured operational horizon.  `globallySafe` is
emitted only when the reached set also passes the independent closure checker.
-/
inductive ReachabilityOutcome (arity : Nat) where
  | unsafeFound (trace : SemanticTrace arity)
  | safeWithinBound
      (visited : List (KernelState arity))
      (frontier : List (KernelState arity))
  | globallySafe (closure : SafetyCertificate arity)
  | error (message : String)
  deriving Repr, DecidableEq

def reachabilityEngine
    (kernel : Kernel arity)
    (bound : Nat) : ReachabilityOutcome arity :=
  match findBadState? kernel bound with
  | some _ =>
      match findBoundedCounterexample? kernel bound with
      | some trace => .unsafeFound trace
      | none =>
          .error "reachable forbidden state had no reconstructable first-bad trace"
  | none =>
      let visited := visitedStates kernel bound
      if SafetyCertificate.check kernel visited then
        .globallySafe visited
      else
        .safeWithinBound visited (frontierStates kernel bound)

theorem reachabilityEngine_unsafe_sound
    {kernel : Kernel arity}
    {bound : Nat}
    {trace : SemanticTrace arity}
    (hengine : reachabilityEngine kernel bound = .unsafeFound trace) :
    BoundedCounterexample kernel bound trace := by
  unfold reachabilityEngine at hengine
  split at hengine
  next badState hbad =>
    split at hengine
    next found hfind =>
      cases hengine
      exact findBoundedCounterexample?_sound hfind
    next hnone =>
      simp_all
  next hnoBad =>
    dsimp only at hengine
    split at hengine <;> simp_all

/--
The deduplicated state-layer test controls whether trace reconstruction runs.
If a bounded semantic counterexample exists, the engine cannot return a safe
or error outcome.
-/
theorem reachabilityEngine_bounded_complete
    {kernel : Kernel arity}
    {bound : Nat}
    (hexists : ∃ trace, BoundedCounterexample kernel bound trace) :
    ∃ trace,
      reachabilityEngine kernel bound = .unsafeFound trace ∧
      BoundedCounterexample kernel bound trace := by
  rcases hexists with ⟨witness, hwitness⟩
  have hcovered : witness.finalState ∈ kernel.coveredStates bound :=
    kernel.mem_coveredStates_of_reachableAt
      hwitness.2.2.1
      hwitness.2.1.reachableAt
  have hbadSome : (findBadState? kernel bound).isSome = true := by
    apply List.find?_isSome.mpr
    exact ⟨witness.finalState, hcovered, hwitness.2.2.2.2⟩
  cases hbad : findBadState? kernel bound with
  | none =>
      simp [hbad] at hbadSome
  | some badState =>
      rcases findBoundedCounterexample?_complete ⟨witness, hwitness⟩ with
        ⟨trace, htrace, hcounterexample⟩
      exact ⟨
        trace,
        by simp [reachabilityEngine, hbad, htrace],
        hcounterexample
      ⟩

theorem reachabilityEngine_not_unsafe_complete
    {kernel : Kernel arity}
    {bound : Nat}
    (hnotUnsafe :
      ∀ trace, reachabilityEngine kernel bound ≠ .unsafeFound trace) :
    ¬∃ trace, BoundedCounterexample kernel bound trace := by
  intro hexists
  rcases reachabilityEngine_bounded_complete hexists with
    ⟨trace, hengine, _⟩
  exact hnotUnsafe trace hengine

theorem reachabilityEngine_safeWithinBound_sound
    {kernel : Kernel arity}
    {bound : Nat}
    {visited frontier : List (KernelState arity)}
    (hengine :
      reachabilityEngine kernel bound =
        .safeWithinBound visited frontier) :
    ¬∃ trace, BoundedCounterexample kernel bound trace := by
  intro hexists
  rcases reachabilityEngine_bounded_complete hexists with
    ⟨trace, hunsafe, _⟩
  rw [hengine] at hunsafe
  contradiction

theorem reachabilityEngine_globallySafe_no_boundedCounterexample
    {kernel : Kernel arity}
    {bound : Nat}
    {closure : SafetyCertificate arity}
    (hengine : reachabilityEngine kernel bound = .globallySafe closure) :
    ¬∃ trace, BoundedCounterexample kernel bound trace := by
  intro hexists
  rcases reachabilityEngine_bounded_complete hexists with
    ⟨found, hunsafe, _⟩
  rw [hengine] at hunsafe
  contradiction

theorem reachabilityEngine_globallySafe_sound
    {kernel : Kernel arity}
    {bound : Nat}
    {closure : SafetyCertificate arity}
    (hengine : reachabilityEngine kernel bound = .globallySafe closure) :
    ∀ state, kernel.Reachable state → ¬kernel.Forbidden state := by
  unfold reachabilityEngine at hengine
  split at hengine
  next badState hbad =>
    split at hengine <;> simp_all
  next hnoBad =>
    dsimp only at hengine
    split at hengine
    next hclosed =>
      cases hengine
      exact SafetyCertificate.check_sound hclosed
    next hnotClosed =>
      simp_all

end TrackBReplay

/-
SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
SPDX-License-Identifier: Apache-2.0

The single frozen semantics kernel for TrackB v0.2.

JSON-facing maps are validated before compilation.  After compilation every
state, precondition, effect, and forbidden observation is indexed by the
workflow's fixed variable vector.  The replay checker, bounded reachability
engine, and global-safety checker all consume `Kernel.successors`; there is no
second transition implementation.
-/

import Lean.Data.Json

namespace TrackBReplay

abbrev BoolMap := List (String × Bool)

structure Action where
  name : String
  pre : BoolMap
  effects : BoolMap
  deriving Repr, DecidableEq

structure Workflow where
  schemaVersion : String
  name : String
  bound : Nat
  variables : List String
  initialState : BoolMap
  actions : List Action
  forbidden : BoolMap
  deriving Repr, DecidableEq

def BoolMap.keys (m : BoolMap) : List String :=
  m.map Prod.fst

def BoolMap.lookup (m : BoolMap) (key : String) : Option Bool :=
  match m.find? (fun entry => entry.1 == key) with
  | some entry => some entry.2
  | none => none

def BoolMap.keysWithin (variables : List String) (m : BoolMap) : Bool :=
  m.all (fun entry => variables.contains entry.1)

def Action.WellFormed (variables : List String) (action : Action) : Bool :=
  action.name != "" &&
  decide action.pre.keys.Nodup &&
  decide action.effects.keys.Nodup &&
  action.pre.keysWithin variables &&
  action.effects.keysWithin variables

def Workflow.WellFormed (workflow : Workflow) : Bool :=
  workflow.schemaVersion == "0.1" &&
  workflow.name != "" &&
  decide workflow.variables.Nodup &&
  workflow.variables.all (fun varName => varName != "") &&
  workflow.initialState.keys == workflow.variables &&
  decide workflow.initialState.keys.Nodup &&
  decide (workflow.actions.map Action.name).Nodup &&
  workflow.actions.all (Action.WellFormed workflow.variables) &&
  decide workflow.forbidden.keys.Nodup &&
  workflow.forbidden.keysWithin workflow.variables

def State.WellFormed (workflow : Workflow) (state : BoolMap) : Bool :=
  state.keys == workflow.variables && decide state.keys.Nodup

/-- A total canonical state indexed by the workflow's declared variables. -/
abbrev KernelState (arity : Nat) := Vector Bool arity

/--
An indexed partial assignment.  `none` means that the corresponding variable
is unconstrained (for a precondition/observation) or unchanged (for effects).
-/
abbrev KernelCondition (arity : Nat) := Vector (Option Bool) arity

structure KernelAction (arity : Nat) where
  name : String
  pre : KernelCondition arity
  effects : KernelCondition arity
  deriving Repr, DecidableEq

/--
The only operational model used by v0.2 proof-producing components.
`arity` is fixed by the type parameter, so malformed, missing, duplicate, or
extraneous external keys cannot survive as ambiguous kernel states.
-/
structure Kernel (arity : Nat) where
  variableNames : Vector String arity
  initial : KernelState arity
  actions : List (KernelAction arity)
  forbidden : KernelCondition arity
  deriving Repr, DecidableEq

def BoolMap.toKernelCondition
    (variables : List String)
    (mapping : BoolMap) : KernelCondition variables.length :=
  Vector.ofFn fun index => mapping.lookup (variables.get index)

def BoolMap.toKernelState
    (variables : List String)
    (mapping : BoolMap) : KernelState variables.length :=
  Vector.ofFn fun index =>
    (mapping[index.val]?).map Prod.snd |>.getD false

def KernelState.toBoolMap
    (variables : List String)
    (state : KernelState variables.length) : BoolMap :=
  List.ofFn fun index => (variables.get index, state.get index)

theorem KernelState.toBoolMap_keys
    (variables : List String)
    (state : KernelState variables.length) :
    (state.toBoolMap variables).keys = variables := by
  rw [KernelState.toBoolMap, BoolMap.keys, List.map_ofFn]
  change List.ofFn (fun index => variables[index.val]) = variables
  exact List.ofFn_getElem

theorem KernelState.toKernelState_toBoolMap
    (variables : List String)
    (state : KernelState variables.length) :
    (state.toBoolMap variables).toKernelState variables = state := by
  apply Vector.ext
  intro index hindex
  simp [
    BoolMap.toKernelState,
    KernelState.toBoolMap,
    Vector.ofFn,
    Vector.get
  ]

def Action.toKernel
    (variables : List String)
    (action : Action) : KernelAction variables.length :=
  {
    name := action.name
    pre := action.pre.toKernelCondition variables
    effects := action.effects.toKernelCondition variables
  }

/--
Validate and compile a JSON-facing workflow into the canonical indexed kernel.
Failure is an error, never a SAFE result.
-/
def Workflow.compile
    (workflow : Workflow) : Except String (Kernel workflow.variables.length) :=
  if workflow.WellFormed then
    .ok {
      variableNames := Vector.ofFn fun index => workflow.variables.get index
      initial := workflow.initialState.toKernelState workflow.variables
      actions := workflow.actions.map (Action.toKernel workflow.variables)
      forbidden := workflow.forbidden.toKernelCondition workflow.variables
    }
  else
    .error "workflow is outside the frozen TrackB v0.1 Boolean kernel domain"

def KernelCondition.holds
    (condition : KernelCondition arity)
    (state : KernelState arity) : Bool :=
  (List.range arity).all fun rawIndex =>
    if h : rawIndex < arity then
      match condition.get ⟨rawIndex, h⟩ with
      | none => true
      | some expected => state.get ⟨rawIndex, h⟩ == expected
    else
      false

def KernelCondition.apply
    (effects : KernelCondition arity)
    (state : KernelState arity) : KernelState arity :=
  Vector.ofFn fun index =>
    match effects.get index with
    | none => state.get index
    | some value => value

/--
All enabled named successors.  This list is the single executable transition
definition.  Every other component consumes it directly.
-/
def Kernel.successors
    (kernel : Kernel arity)
    (before : KernelState arity) : List (String × KernelState arity) :=
  kernel.actions.filterMap fun action =>
    if action.pre.holds before then
      some (action.name, action.effects.apply before)
    else
      none

def Kernel.transitionB
    (kernel : Kernel arity)
    (before : KernelState arity)
    (actionName : String)
    (after : KernelState arity) : Bool :=
  kernel.successors before |>.contains (actionName, after)

/-- The proposition reflected by `Kernel.transitionB`. -/
def Kernel.Transition
    (kernel : Kernel arity)
    (before : KernelState arity)
    (actionName : String)
    (after : KernelState arity) : Prop :=
  (actionName, after) ∈ kernel.successors before

theorem Kernel.transitionB_iff
    {kernel : Kernel arity}
    {before after : KernelState arity}
    {actionName : String} :
    kernel.transitionB before actionName after = true ↔
      kernel.Transition before actionName after := by
  simp [Kernel.transitionB, Kernel.Transition]

def Kernel.forbiddenHolds
    (kernel : Kernel arity)
    (state : KernelState arity) : Bool :=
  kernel.forbidden.holds state

def Kernel.Forbidden
    (kernel : Kernel arity)
    (state : KernelState arity) : Prop :=
  kernel.forbiddenHolds state = true

/-- Unbounded reachability under the exact same `Kernel.Transition`. -/
inductive Kernel.Reachable (kernel : Kernel arity) : KernelState arity → Prop
  | initial : kernel.Reachable kernel.initial
  | step {before after : KernelState arity} {actionName : String} :
      kernel.Reachable before →
      kernel.Transition before actionName after →
      kernel.Reachable after

end TrackBReplay

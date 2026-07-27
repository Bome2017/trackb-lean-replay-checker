/-
SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
SPDX-License-Identifier: Apache-2.0

A proof-producing checker for concrete TrackB v0.1 UNSAFE replay witnesses.
The model intentionally covers existence of a valid bounded counterexample.
It does not claim that a search backend is complete or that SAFE_WITHIN_BOUND
is global safety.
-/

import Lean.Data.Json

namespace TrackBReplay

open Lean

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

structure TraceStep where
  step : Nat
  action : Option String
  stateBefore : Option BoolMap
  stateDelta : BoolMap
  stateAfter : BoolMap
  deriving Repr, DecidableEq

structure Violation where
  condition : BoolMap
  firstBadStep : Nat
  deriving Repr, DecidableEq

structure UnsafeResult where
  workflow : String
  schemaVersion : String
  bound : Nat
  status : String
  violation : Violation
  trace : List TraceStep
  claimBoundary : String
  deriving Repr, DecidableEq

def unsafeClaimBoundary : String :=
  "UNSAFE means a bad replay exists within the configured bound and model assumptions. " ++
  "SAFE_WITHIN_BOUND does not prove global safety."

def BoolMap.keys (m : BoolMap) : List String :=
  m.map Prod.fst

def BoolMap.lookup (m : BoolMap) (key : String) : Option Bool :=
  match m.find? (fun entry => entry.1 == key) with
  | some entry => some entry.2
  | none => none

def BoolMap.keysWithin (variables : List String) (m : BoolMap) : Bool :=
  m.all (fun entry => variables.contains entry.1)

def BoolMap.holds (state condition : BoolMap) : Bool :=
  condition.all (fun entry => state.lookup entry.1 == some entry.2)

def BoolMap.applyEffects (state effects : BoolMap) : BoolMap :=
  state.map fun entry =>
    match effects.lookup entry.1 with
    | some value => (entry.1, value)
    | none => entry

def BoolMap.delta (before after : BoolMap) : BoolMap :=
  before.filterMap fun entry =>
    match after.lookup entry.1 with
    | some value => if value == entry.2 then none else some (entry.1, value)
    | none => none

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

def Transition
    (workflow : Workflow)
    (before : BoolMap)
    (actionName : String)
    (after : BoolMap) : Bool :=
  workflow.actions.any fun action =>
    action.name == actionName &&
    before.holds action.pre &&
    after == before.applyEffects action.effects

def TraceStep.IsInitial (workflow : Workflow) (traceStep : TraceStep) : Bool :=
  traceStep.step == 0 &&
  traceStep.action == none &&
  traceStep.stateBefore == none &&
  traceStep.stateDelta == [] &&
  traceStep.stateAfter == workflow.initialState

def TraceStep.IsTransition
    (workflow : Workflow)
    (expectedStep : Nat)
    (before : BoolMap)
    (traceStep : TraceStep) : Bool :=
  traceStep.step == expectedStep &&
  traceStep.stateBefore == some before &&
  State.WellFormed workflow traceStep.stateAfter &&
  traceStep.stateDelta == before.delta traceStep.stateAfter &&
  match traceStep.action with
  | none => false
  | some actionName => Transition workflow before actionName traceStep.stateAfter

def TraceTail.Valid
    (workflow : Workflow) : Nat → BoolMap → List TraceStep → Bool
  | _, _, [] => true
  | expectedStep, before, traceStep :: rest =>
      traceStep.IsTransition workflow expectedStep before &&
      TraceTail.Valid workflow (expectedStep + 1) traceStep.stateAfter rest

def Trace.finalState? (trace : List TraceStep) : Option BoolMap :=
  trace.getLast?.map TraceStep.stateAfter

def Trace.priorStatesSafe (workflow : Workflow) (trace : List TraceStep) : Bool :=
  trace.dropLast.all fun traceStep =>
    !BoolMap.holds traceStep.stateAfter workflow.forbidden

/-- Executable Boolean validation of the bounded replay obligations. -/
def check (workflow : Workflow) (result : UnsafeResult) : Bool :=
  workflow.WellFormed &&
  result.workflow == workflow.name &&
  result.schemaVersion == workflow.schemaVersion &&
  result.bound == workflow.bound &&
  result.status == "UNSAFE" &&
  result.claimBoundary == unsafeClaimBoundary &&
  result.violation.condition == workflow.forbidden &&
  result.violation.firstBadStep + 1 == result.trace.length &&
  decide (result.trace.length > 0) &&
  decide (result.trace.length - 1 ≤ workflow.bound) &&
  match result.trace with
  | [] => false
  | initial :: rest =>
      initial.IsInitial workflow &&
      State.WellFormed workflow initial.stateAfter &&
      TraceTail.Valid workflow 1 initial.stateAfter rest &&
      Trace.priorStatesSafe workflow result.trace &&
      match Trace.finalState? result.trace with
      | none => false
      | some finalState => BoolMap.holds finalState workflow.forbidden

/--
The proposition checked by the executable.

It states that a native TrackB v0.1 result contains a well-formed, digest-bindable
counterexample trace whose transitions replay under the supplied workflow,
whose earlier states are not forbidden, and whose final state is forbidden.
The trace may contain at most `workflow.bound` actions.
-/
def ValidCounterexample (workflow : Workflow) (result : UnsafeResult) : Prop :=
  workflow.WellFormed = true ∧
  result.workflow = workflow.name ∧
  result.schemaVersion = workflow.schemaVersion ∧
  result.bound = workflow.bound ∧
  result.status = "UNSAFE" ∧
  result.claimBoundary = unsafeClaimBoundary ∧
  result.violation.condition = workflow.forbidden ∧
  result.violation.firstBadStep + 1 = result.trace.length ∧
  result.trace.length > 0 ∧
  result.trace.length - 1 ≤ workflow.bound ∧
  match result.trace with
  | [] => False
  | initial :: rest =>
      initial.IsInitial workflow = true ∧
      State.WellFormed workflow initial.stateAfter = true ∧
      TraceTail.Valid workflow 1 initial.stateAfter rest = true ∧
      Trace.priorStatesSafe workflow result.trace = true ∧
      match Trace.finalState? result.trace with
      | none => False
      | some finalState => BoolMap.holds finalState workflow.forbidden = true

theorem check_iff {workflow : Workflow} {result : UnsafeResult} :
    check workflow result = true ↔ ValidCounterexample workflow result := by
  unfold check ValidCounterexample
  split
  · simp
  · split <;> simp [and_assoc]

/-- A passing executable check entails the full replay proposition. -/
theorem check_sound {workflow : Workflow} {result : UnsafeResult}
    (h : check workflow result = true) :
    ValidCounterexample workflow result :=
  check_iff.mp h

/-- The executable checker is complete for its explicitly bounded proposition. -/
theorem check_complete {workflow : Workflow} {result : UnsafeResult}
    (h : ValidCounterexample workflow result) :
    check workflow result = true :=
  check_iff.mpr h

private def parseBoolMap (label : String) (json : Json) : Except String BoolMap := do
  let object ← json.getObj?
  object.foldlM (init := []) fun entries key value => do
    let boolValue ← value.getBool?
      |>.mapError (fun error => s!"{label}.{key}: {error}")
    return entries ++ [(key, boolValue)]

private def parseVariables (json : Json) : Except String (List String) := do
  let object ← json.getObj?
  object.foldlM (init := []) fun variables key value => do
    let variableType ← value.getStr?
      |>.mapError (fun error => s!"state_variables.{key}: {error}")
    if variableType != "bool" then
      throw s!"state_variables.{key}: expected \"bool\""
    return variables ++ [key]

private def parseAction (json : Json) : Except String Action := do
  return {
    name := ← (json.getObjVal? "name" >>= Json.getStr?)
    pre := ← parseBoolMap "action.pre" (← json.getObjVal? "pre")
    effects := ← parseBoolMap "action.effects" (← json.getObjVal? "effects")
  }

private def parseTraceStep (json : Json) : Except String TraceStep := do
  let actionJson ← json.getObjVal? "action"
  let action ←
    if actionJson.isNull then
      pure none
    else
      some <$> actionJson.getStr?
  let beforeJson ← json.getObjVal? "state_before"
  let stateBefore ←
    if beforeJson.isNull then
      pure none
    else
      some <$> parseBoolMap "trace.state_before" beforeJson
  return {
    step := ← (json.getObjVal? "step" >>= Json.getNat?)
    action
    stateBefore
    stateDelta := ← parseBoolMap "trace.state_delta" (← json.getObjVal? "state_delta")
    stateAfter := ← parseBoolMap "trace.state_after" (← json.getObjVal? "state_after")
  }

def parseWorkflow (json : Json) : Except String Workflow := do
  let actionJson ← json.getObjVal? "actions" >>= Json.getArr?
  return {
    schemaVersion := ← (json.getObjVal? "schema_version" >>= Json.getStr?)
    name := ← (json.getObjVal? "name" >>= Json.getStr?)
    bound := ← (json.getObjVal? "bound" >>= Json.getNat?)
    variables := ← parseVariables (← json.getObjVal? "state_variables")
    initialState := ← parseBoolMap "initial_state" (← json.getObjVal? "initial_state")
    actions := ← actionJson.toList.mapM parseAction
    forbidden := ← parseBoolMap "forbidden.all"
      (← json.getObjVal? "forbidden" >>= (·.getObjVal? "all"))
  }

def parseUnsafeResult (json : Json) : Except String UnsafeResult := do
  let violationJson ← json.getObjVal? "violation"
  if violationJson.isNull then
    throw "violation must be an object; SAFE_WITHIN_BOUND is outside this checker"
  let traceJson ← json.getObjVal? "trace"
  if traceJson.isNull then
    throw "trace must be an array; SAFE_WITHIN_BOUND is outside this checker"
  let traceArray ← traceJson.getArr?
  return {
    workflow := ← (json.getObjVal? "workflow" >>= Json.getStr?)
    schemaVersion := ← (json.getObjVal? "schema_version" >>= Json.getStr?)
    bound := ← (json.getObjVal? "bound" >>= Json.getNat?)
    status := ← (json.getObjVal? "status" >>= Json.getStr?)
    violation := {
      condition := ← parseBoolMap "violation.condition"
        (← violationJson.getObjVal? "condition")
      firstBadStep := ← (violationJson.getObjVal? "first_bad_step" >>= Json.getNat?)
    }
    trace := ← traceArray.toList.mapM parseTraceStep
    claimBoundary := ← (json.getObjVal? "claim_boundary" >>= Json.getStr?)
  }

def parseWorkflowText (text : String) : Except String Workflow :=
  Json.parse text >>= parseWorkflow

def parseUnsafeResultText (text : String) : Except String UnsafeResult :=
  Json.parse text >>= parseUnsafeResult

end TrackBReplay

/-
SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
SPDX-License-Identifier: Apache-2.0

Authoritative TrackB reachability entry point.
-/

import TrackBResults

open TrackBReplay
open Lean

private def readAndParseWorkflow (path : System.FilePath) : IO Workflow := do
  let text ← IO.FS.readFile path
  IO.ofExcept (parseWorkflowText text)

private def emitJson (json : Json) : IO Unit :=
  IO.println json.pretty

private def runSearch (workflow : Workflow) : IO UInt32 := do
  let compiled ← IO.ofExcept workflow.compileChecked
  match runCheckedReachability workflow compiled with
  | .error message =>
      IO.eprintln s!"ERROR: {message}"
      return 2
  | .ok outcome =>
      match outcome with
      | .counterexample _ _ generated =>
          emitJson (unsafeResultToJson generated.result)
          return 0
      | .safeWithinBound generated =>
          emitJson <| boundedSafetyResultToJson generated.result
          return 0
      | .globallySafe _ _ generated =>
          emitJson (globalSafetyResultToJson generated.result)
          return 0

def main (args : List String) : IO UInt32 := do
  match args with
  | [workflowPath] =>
      try
        runSearch (← readAndParseWorkflow workflowPath)
      catch error =>
        IO.eprintln s!"ERROR: {error}"
        return 2
  | _ =>
      IO.eprintln "usage: trackb-reachability WORKFLOW.json"
      return 2

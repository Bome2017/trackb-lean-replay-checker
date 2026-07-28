/-
SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
SPDX-License-Identifier: Apache-2.0

Lean-side correspondence check between a guarded JSON fixture and the exact
typed workflow used by its concrete safety theorem.
-/

import GuardedExamples

open TrackBReplay
open TrackBReplay.GuardedExamples

private def readAndParseWorkflow (path : System.FilePath) : IO Workflow := do
  let text ← IO.FS.readFile path
  IO.ofExcept (parseWorkflowText text)

def main (args : List String) : IO UInt32 := do
  match args with
  | [workflowPath] =>
      try
        let workflow ← readAndParseWorkflow workflowPath
        match expectedWorkflow? workflow.name with
        | none =>
            IO.eprintln
              s!"FAIL: {workflow.name} has no frozen guarded-workflow model"
            return 1
        | some expected =>
            if workflow = expected then
              IO.println s!"PASS workflow={workflow.name} model=exact"
              return 0
            else
              IO.eprintln
                "FAIL: parsed JSON differs from the frozen theorem model"
              return 1
      catch error =>
        IO.eprintln s!"ERROR: {error}"
        return 2
  | _ =>
      IO.eprintln "usage: trackb-guarded-fixture-check WORKFLOW.json"
      return 2

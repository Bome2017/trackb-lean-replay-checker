/-
SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
SPDX-License-Identifier: Apache-2.0
-/

import TrackBReplay

open TrackBReplay

private def readAndParseWorkflow (path : System.FilePath) : IO Workflow := do
  let text ← IO.FS.readFile path
  IO.ofExcept (parseWorkflowText text)

private def readAndParseResult (path : System.FilePath) : IO UnsafeResult := do
  let text ← IO.FS.readFile path
  IO.ofExcept (parseUnsafeResultText text)

def main (args : List String) : IO UInt32 := do
  match args with
  | [workflowPath, resultPath] =>
      try
        let workflow ← readAndParseWorkflow workflowPath
        let result ← readAndParseResult resultPath
        if check workflow result then
          IO.println s!"PASS workflow={workflow.name} actions={result.trace.length - 1} bound={workflow.bound}"
          return 0
        else
          IO.eprintln "FAIL: result is not a valid bounded counterexample for this workflow"
          return 1
      catch error =>
        IO.eprintln s!"ERROR: {error}"
        return 2
  | _ =>
      IO.eprintln "usage: trackb-replay-check WORKFLOW.json RESULT.json"
      return 2

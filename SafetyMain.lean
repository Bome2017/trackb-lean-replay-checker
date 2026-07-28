/-
SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
SPDX-License-Identifier: Apache-2.0

Independent checker for TrackB native global-safety certificates.
-/

import TrackBResults

open TrackBReplay

private def readAndParseWorkflow (path : System.FilePath) : IO Workflow := do
  let text ← IO.FS.readFile path
  IO.ofExcept (parseWorkflowText text)

private def readAndParseResult
    (path : System.FilePath) : IO GlobalSafetyResult := do
  let text ← IO.FS.readFile path
  IO.ofExcept (parseGlobalSafetyResultText text)

def main (args : List String) : IO UInt32 := do
  match args with
  | [workflowPath, resultPath] =>
      try
        let workflow ← readAndParseWorkflow workflowPath
        let result ← readAndParseResult resultPath
        if result.check workflow then
          IO.println s!"PASS workflow={workflow.name} closure={result.closure.length}"
          return 0
        else
          IO.eprintln
            "FAIL: result is not a valid closed-state global-safety certificate"
          return 1
      catch error =>
        IO.eprintln s!"ERROR: {error}"
        return 2
  | _ =>
      IO.eprintln
        "usage: trackb-global-safety-check WORKFLOW.json GLOBAL_RESULT.json"
      return 2

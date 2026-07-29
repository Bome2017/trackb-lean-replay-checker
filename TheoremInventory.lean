/-
SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
SPDX-License-Identifier: Apache-2.0

Authoritative theorem and axiom inventory for the TrackB release surface.

This program imports compiled Lean modules, enumerates `thmInfo` declarations
from the resulting kernel environment, and obtains transitive axioms through
Lean's `collectAxioms`.  It does not inspect Lean source text.
-/

import Lean

open Lean

namespace TrackBTheoremInventory

def inventorySchema : String := "trackb-theorem-inventory-v1"

def classificationSchema : String :=
  "trackb-theorem-classification-v1"

def defaultImports : Array Name := #[
  `AxiomCheck,
  `Main,
  `SearchMain,
  `SafetyMain,
  `FixtureMain
]

def defaultOwnedModules : Array Name := #[
  `TrackBSemantics,
  `TrackBSafety,
  `TrackBSearch,
  `TrackBReplay,
  `TrackBResults,
  `GuardedExamples,
  `AxiomCheck,
  `Main,
  `SearchMain,
  `SafetyMain,
  `FixtureMain
]

def defaultAllowedAxioms : Array String := #[
  "Classical.choice",
  "Quot.sound",
  "propext"
]

structure ClassificationManifest where
  schemaVersion : String
  externallyCited : Array String
  internalHelpers : Array String
  exampleModules : Array String
  deriving FromJson

def emptyClassificationManifest : ClassificationManifest where
  schemaVersion := classificationSchema
  externallyCited := #[]
  internalHelpers := #[]
  exampleModules := #[]

structure Config where
  imports : Array Name := #[]
  ownedModules : Array Name := #[]
  allowedAxioms : Array String := #[]
  classificationPath? : Option System.FilePath := none
  outputPath? : Option System.FilePath := none

def usage : String :=
  "usage: theorem-inventory [--import MODULE] [--owned-module MODULE] " ++
  "[--allowed-axiom NAME] [--classification FILE] [--output FILE]\n" ++
  "\n" ++
  "With no --import/--owned-module flags, the complete TrackB release " ++
  "surface is loaded and treated as owned. Each repeated --import root is " ++
  "loaded into an independent environment so executable roots may all be " ++
  "audited even though they each define `main`."

partial def parseArgs (args : List String) (config : Config := {}) :
    Except String Config :=
  match args with
  | [] => .ok config
  | "--import" :: moduleName :: rest =>
      parseArgs rest {
        config with imports := config.imports.push moduleName.toName
      }
  | "--owned-module" :: moduleName :: rest =>
      parseArgs rest {
        config with ownedModules := config.ownedModules.push moduleName.toName
      }
  | "--allowed-axiom" :: axiomName :: rest =>
      parseArgs rest {
        config with allowedAxioms := config.allowedAxioms.push axiomName
      }
  | "--classification" :: path :: rest =>
      parseArgs rest {
        config with classificationPath? := some path
      }
  | "--output" :: path :: rest =>
      parseArgs rest {
        config with outputPath? := some path
      }
  | "--help" :: _ => .error usage
  | "-h" :: _ => .error usage
  | value :: _ =>
      if value.startsWith "-" then
        .error s!"unknown or incomplete option: {value}\n{usage}"
      else
        .error s!"unexpected positional argument: {value}\n{usage}"

def normalizeConfig (config : Config) : Config :=
  {
    config with
    imports := if config.imports.isEmpty then defaultImports else config.imports
    ownedModules :=
      if config.ownedModules.isEmpty then
        if config.imports.isEmpty then defaultOwnedModules else config.imports
      else config.ownedModules
    allowedAxioms :=
      if config.allowedAxioms.isEmpty then
        defaultAllowedAxioms
      else config.allowedAxioms
  }

def sortedUniqueStrings (values : Array String) : Array String :=
  let sorted := values.qsort (· < ·)
  sorted.foldl
    (init := #[])
    fun result value =>
      if result.back? == some value then result else result.push value

def duplicateStrings (values : Array String) : Array String :=
  let sorted := values.qsort (· < ·)
  let rec loop (remaining : List String) (duplicates : Array String) :
      Array String :=
    match remaining with
    | first :: second :: rest =>
        if first = second then
          let duplicates :=
            if duplicates.back? == some first then
              duplicates
            else
              duplicates.push first
          loop (second :: rest) duplicates
        else
          loop (second :: rest) duplicates
    | _ => duplicates
  loop sorted.toList #[]

def nameLeaf : Name → String
  | .anonymous => "[anonymous]"
  | .str _ value => value
  | .num _ value => toString value

def originModule? (env : Environment) (declarationName : Name) : Option Name := do
  let moduleIndex ← env.getModuleIdxFor? declarationName
  env.header.moduleNames[moduleIndex.toNat]?

structure OwnedTheorem where
  name : Name
  originModule : Name
  type : Expr

structure LocatedTheorem where
  declaration : OwnedTheorem
  env : Environment

structure AuditedTheorem where
  located : LocatedTheorem
  hasExactDeclarationRange : Bool
  generatedProjection : Bool
  authoredDeclaration : Bool

def collectOwnedTheorems
    (env : Environment)
    (ownedModules : Array Name) : Array OwnedTheorem :=
  env.constants.fold
    (init := #[])
    fun result name info =>
      match info, originModule? env name with
      | .thmInfo theoremValue, some originModule =>
          if ownedModules.contains originModule then
            result.push {
              name
              originModule
              type := theoremValue.type
            }
          else result
      | _, _ => result
  |>.qsort fun left right => Name.lt left.name right.name

def collectLocatedTheorems
    (environments : Array Environment)
    (ownedModules : Array Name) : Array LocatedTheorem :=
  let entries := environments.foldl
    (init := #[])
    fun result env =>
      (collectOwnedTheorems env ownedModules).foldl
        (init := result)
        fun result declaration =>
          if result.any fun entry =>
              entry.declaration.name = declaration.name &&
                entry.declaration.originModule = declaration.originModule then
            result
          else
            result.push { declaration, env }
  entries.qsort fun left right =>
    if left.declaration.name = right.declaration.name then
      Name.lt left.declaration.originModule
        right.declaration.originModule
    else
      Name.lt left.declaration.name right.declaration.name

def inconsistentTheoremDuplicates
    (environments : Array Environment)
    (ownedModules : Array Name) : Array String :=
  let rawEntries := environments.foldl
    (init := #[])
    fun result env => result ++ collectOwnedTheorems env ownedModules
  sortedUniqueStrings <| rawEntries.filterMap fun entry =>
    let inconsistent := rawEntries.any fun other =>
      other.name = entry.name &&
      other.originModule = entry.originModule &&
      other.type != entry.type
    if inconsistent then
      some s!"{entry.originModule.toString}::{entry.name.toString}"
    else
      none

def readClassificationManifest
    (path? : Option System.FilePath) : IO ClassificationManifest := do
  match path? with
  | none => return emptyClassificationManifest
  | some path =>
      let text ← IO.FS.readFile path
      let json ← IO.ofExcept <| Json.parse text
      let manifest : ClassificationManifest ← IO.ofExcept <| fromJson? json
      if manifest.schemaVersion != classificationSchema then
        throw <| IO.userError
          s!"unsupported classification schema: {manifest.schemaVersion}"
      return manifest

def classificationJson
    (manifest : ClassificationManifest)
    (theoremName originModule : String)
    (authoredDeclaration : Bool) : Json :=
  let internalHelper :=
    authoredDeclaration && manifest.internalHelpers.contains theoremName
  let exampleTheorem :=
    authoredDeclaration && !internalHelper &&
      manifest.exampleModules.contains originModule
  let publicApi :=
    authoredDeclaration && !internalHelper && !exampleTheorem
  let externallyCited :=
    authoredDeclaration && manifest.externallyCited.contains theoremName
  let category :=
    if !authoredDeclaration then "generated"
    else if internalHelper then "internal_helper"
    else if exampleTheorem then "example_theorem"
    else "public_api"
  Json.mkObj [
    ("category", category),
    ("exampleTheorem", exampleTheorem),
    ("externallyCited", externallyCited),
    ("internalHelper", internalHelper),
    ("publicApi", publicApi)
  ]

structure ManifestValidation where
  duplicateEntries : Array String
  unknownTheorems : Array String
  unknownExampleModules : Array String
  contradictoryClassifications : Array String

def validateManifest
    (manifest : ClassificationManifest)
    (theorems : Array AuditedTheorem)
    (ownedModules : Array Name) : ManifestValidation :=
  let authoredTheoremNames :=
    (theorems.filter (·.authoredDeclaration)).map fun entry =>
      entry.located.declaration.name.toString
  let ownedModuleNames := ownedModules.map Name.toString
  let duplicateEntries := sortedUniqueStrings <|
    duplicateStrings manifest.externallyCited ++
    duplicateStrings manifest.internalHelpers ++
    duplicateStrings manifest.exampleModules
  let unknownTheorems := sortedUniqueStrings <|
    (manifest.externallyCited ++ manifest.internalHelpers).filter
      fun name => !authoredTheoremNames.contains name
  let unknownExampleModules := sortedUniqueStrings <|
    manifest.exampleModules.filter fun name => !ownedModuleNames.contains name
  let contradictoryClassifications := sortedUniqueStrings <|
    manifest.internalHelpers.filter fun name =>
      manifest.externallyCited.contains name
  {
    duplicateEntries
    unknownTheorems
    unknownExampleModules
    contradictoryClassifications
  }

def duplicateLeafGroups
    (theorems : Array LocatedTheorem) : Array (String × Array String) :=
  let leaves := sortedUniqueStrings <|
    theorems.map fun entry => nameLeaf entry.declaration.name
  leaves.filterMap fun leaf =>
    let fullNames := sortedUniqueStrings <|
      (theorems.filter fun entry =>
        nameLeaf entry.declaration.name = leaf).map
        fun entry => entry.declaration.name.toString
    if fullNames.size > 1 then some (leaf, fullNames) else none

def runCollectAxioms
    (env : Environment)
    (theoremName : Name) : IO (Array Name) :=
  (collectAxioms theoremName : CoreM (Array Name)).toIO'
    { fileName := "<TrackBTheoremInventory>", fileMap := default }
    { env }

def runHasExactDeclarationRange
    (env : Environment)
    (declarationName : Name) : IO Bool := do
  let range? ←
    (findDeclarationRangesCore? declarationName :
      CoreM (Option DeclarationRanges)).toIO'
      { fileName := "<TrackBTheoremInventory>", fileMap := default }
      { env }
  return range?.isSome

structure OwnedAxiom where
  name : Name
  originModule : Name
  type : Expr
  isUnsafe : Bool

def collectOwnedAxioms
    (env : Environment)
    (ownedModules : Array Name) : Array OwnedAxiom :=
  env.constants.fold
    (init := #[])
    fun result name info =>
      match info, originModule? env name with
      | .axiomInfo axiomValue, some originModule =>
          if ownedModules.contains originModule then
            result.push {
              name
              originModule
              type := axiomValue.type
              isUnsafe := axiomValue.isUnsafe
            }
          else result
      | _, _ => result
  |>.qsort fun left right => Name.lt left.name right.name

def collectOwnedAxiomsFromEnvironments
    (environments : Array Environment)
    (ownedModules : Array Name) : Array OwnedAxiom :=
  let entries := environments.foldl
    (init := #[])
    fun result env =>
      (collectOwnedAxioms env ownedModules).foldl
        (init := result)
        fun result entry =>
          if result.any fun existing =>
              existing.name = entry.name &&
                existing.originModule = entry.originModule then
            result
          else
            result.push entry
  entries.qsort fun left right => Name.lt left.name right.name

structure UnsafeDeclaration where
  name : Name
  originModule : Name
  declarationKind : String

def constantKind : ConstantInfo → String
  | .axiomInfo _ => "axiom"
  | .defnInfo _ => "definition"
  | .thmInfo _ => "theorem"
  | .opaqueInfo _ => "opaque"
  | .quotInfo _ => "quotient"
  | .inductInfo _ => "inductive"
  | .ctorInfo _ => "constructor"
  | .recInfo _ => "recursor"

structure LocatedOwnedConstant where
  name : Name
  originModule : Name
  declarationKind : String
  env : Environment

def collectLocatedOwnedConstants
    (environments : Array Environment)
    (ownedModules : Array Name) : Array LocatedOwnedConstant :=
  let entries := environments.foldl
    (init := #[])
    fun result env =>
      env.constants.fold
        (init := result)
        fun result name info =>
          match originModule? env name with
          | some originModule =>
              if !ownedModules.contains originModule then
                result
              else if result.any fun entry =>
                  entry.name = name &&
                    entry.originModule = originModule then
                result
              else
                result.push {
                  name
                  originModule
                  declarationKind := constantKind info
                  env
                }
          | none => result
  entries.qsort fun left right =>
    if left.name = right.name then
      Name.lt left.originModule right.originModule
    else
      Name.lt left.name right.name

def collectOwnedUnsafeDeclarations
    (env : Environment)
    (ownedModules : Array Name) : Array UnsafeDeclaration :=
  env.constants.fold
    (init := #[])
    fun result name info =>
      match originModule? env name with
      | some originModule =>
          if ownedModules.contains originModule && info.isUnsafe then
            result.push {
              name
              originModule
              declarationKind := constantKind info
            }
          else result
      | none => result
  |>.qsort fun left right => Name.lt left.name right.name

def collectOwnedUnsafeDeclarationsFromEnvironments
    (environments : Array Environment)
    (ownedModules : Array Name) : Array UnsafeDeclaration :=
  let entries := environments.foldl
    (init := #[])
    fun result env =>
      (collectOwnedUnsafeDeclarations env ownedModules).foldl
        (init := result)
        fun result entry =>
          if result.any fun existing =>
              existing.name = entry.name &&
                existing.originModule = entry.originModule then
            result
          else
            result.push entry
  entries.qsort fun left right => Name.lt left.name right.name

def unloadedOwnedModules
    (environments : Array Environment)
    (ownedModules : Array Name) : Array String :=
  sortedUniqueStrings <| (ownedModules.filter fun ownedModule =>
    !environments.any fun env =>
      env.header.moduleNames.contains ownedModule).map Name.toString

def ownedAxiomsJson (axioms : Array OwnedAxiom) : Json :=
  toJson <| axioms.map fun entry =>
    Json.mkObj [
      ("isUnsafe", entry.isUnsafe),
      ("name", entry.name.toString),
      ("originModule", entry.originModule.toString),
      ("typeRepresentation", reprStr entry.type),
      ("typeRepresentationFormat", "Lean.Expr.repr-v1")
    ]

def unsafeDeclarationsJson
    (declarations : Array UnsafeDeclaration) : Json :=
  toJson <| declarations.map fun entry =>
    Json.mkObj [
      ("declarationKind", entry.declarationKind),
      ("name", entry.name.toString),
      ("originModule", entry.originModule.toString)
    ]

def manifestValidationJson (validation : ManifestValidation) : Json :=
  Json.mkObj [
    ("contradictoryClassifications",
      toJson validation.contradictoryClassifications),
    ("duplicateEntries", toJson validation.duplicateEntries),
    ("unknownExampleModules", toJson validation.unknownExampleModules),
    ("unknownTheorems", toJson validation.unknownTheorems)
  ]

def duplicateLeafGroupsJson
    (groups : Array (String × Array String)) : Json :=
  toJson <| groups.map fun (leaf, names) =>
    Json.mkObj [
      ("fullNames", toJson names),
      ("leafName", leaf)
    ]

unsafe def buildInventory
    (config : Config)
    (manifest : ClassificationManifest) : IO (Json × Bool) := do
  let mut environments : Array Environment := #[]
  for moduleName in config.imports do
    enableInitializersExecution
    let env ← importModules
      (loadExts := true)
      (level := .private)
      #[{ module := moduleName }]
      {}
    environments := environments.push env
  let locatedTheorems :=
    collectLocatedTheorems environments config.ownedModules
  let inconsistentTheoremDuplicates :=
    inconsistentTheoremDuplicates environments config.ownedModules
  let mut theorems : Array AuditedTheorem := #[]
  for located in locatedTheorems do
    let hasExactDeclarationRange ←
      runHasExactDeclarationRange located.env located.declaration.name
    let generatedProjection :=
      located.env.isProjectionFn located.declaration.name
    let authoredDeclaration :=
      hasExactDeclarationRange && !generatedProjection
    theorems := theorems.push {
      located
      hasExactDeclarationRange
      generatedProjection
      authoredDeclaration
    }
  let ownedConstants :=
    collectLocatedOwnedConstants environments config.ownedModules
  let ownedAxioms :=
    collectOwnedAxiomsFromEnvironments environments config.ownedModules
  let unsafeDeclarations :=
    collectOwnedUnsafeDeclarationsFromEnvironments
      environments config.ownedModules
  let unloadedOwnedModules :=
    unloadedOwnedModules environments config.ownedModules
  let manifestValidation :=
    validateManifest manifest theorems config.ownedModules
  let allowedAxioms := sortedUniqueStrings config.allowedAxioms
  let mut axiomOffendingConstants : Array Json := #[]
  let mut allConstantForbiddenAxioms : Array String := #[]
  for entry in ownedConstants do
    let transitiveAxioms ← runCollectAxioms entry.env entry.name
    let forbidden := sortedUniqueStrings <|
      (transitiveAxioms.map Name.toString).filter fun axiomName =>
        !allowedAxioms.contains axiomName
    if !forbidden.isEmpty then
      allConstantForbiddenAxioms :=
        allConstantForbiddenAxioms ++ forbidden
      axiomOffendingConstants := axiomOffendingConstants.push <|
        Json.mkObj [
          ("declarationKind", entry.declarationKind),
          ("forbiddenAxioms", toJson forbidden),
          ("name", entry.name.toString),
          ("originModule", entry.originModule.toString)
        ]
  let allConstantForbiddenAxiomNames :=
    sortedUniqueStrings allConstantForbiddenAxioms
  let mut theoremJson : Array Json := #[]
  let mut theoremForbiddenAxioms : Array String := #[]
  let mut authoredTheoremCount : Nat := 0
  for audited in theorems do
    let located := audited.located
    let entry := located.declaration
    if audited.authoredDeclaration then
      authoredTheoremCount := authoredTheoremCount + 1
    let axioms ← runCollectAxioms located.env entry.name
    let axiomStrings := sortedUniqueStrings <|
      axioms.map Name.toString
    theoremForbiddenAxioms := theoremForbiddenAxioms ++
      axiomStrings.filter fun axiomName =>
        !allowedAxioms.contains axiomName
    let theoremName := entry.name.toString
    let originModule := entry.originModule.toString
    theoremJson := theoremJson.push <| Json.mkObj [
      ("authored", audited.authoredDeclaration),
      ("authoredDeclaration", audited.authoredDeclaration),
      ("classification",
        classificationJson manifest theoremName originModule
          audited.authoredDeclaration),
      ("declarationKind", "theorem"),
      ("environmentProvenance", Json.mkObj [
        ("exactDeclarationRange", audited.hasExactDeclarationRange),
        ("generatedProjection", audited.generatedProjection),
        ("kind",
          if audited.authoredDeclaration then "authored" else "generated")
      ]),
      ("leafName", nameLeaf entry.name),
      ("name", theoremName),
      ("originModule", originModule),
      ("transitiveAxioms", toJson axiomStrings),
      ("typeRepresentation", reprStr entry.type),
      ("typeRepresentationFormat", "Lean.Expr.repr-v1")
    ]
  let theoremForbiddenAxiomNames :=
    sortedUniqueStrings theoremForbiddenAxioms
  let duplicateFullNames := duplicateStrings <|
    theorems.map fun entry =>
      entry.located.declaration.name.toString
  let duplicateLeaves := duplicateLeafGroups locatedTheorems
  let manifestPassed :=
    manifestValidation.duplicateEntries.isEmpty &&
    manifestValidation.unknownTheorems.isEmpty &&
    manifestValidation.unknownExampleModules.isEmpty &&
    manifestValidation.contradictoryClassifications.isEmpty
  let passed := allConstantForbiddenAxiomNames.isEmpty &&
    theoremForbiddenAxiomNames.isEmpty &&
    duplicateFullNames.isEmpty &&
    inconsistentTheoremDuplicates.isEmpty &&
    manifestPassed &&
    ownedAxioms.isEmpty &&
    unsafeDeclarations.isEmpty &&
    unloadedOwnedModules.isEmpty
  let json := Json.mkObj [
    ("allowedAxioms", toJson allowedAxioms),
    ("authoredTheoremCount", authoredTheoremCount),
    ("axiomOffendingConstants", toJson axiomOffendingConstants),
    ("checks", Json.mkObj [
      ("allOwnedConstantAxiomGatePassed",
        allConstantForbiddenAxiomNames.isEmpty),
      ("authoredAxiomGatePassed", ownedAxioms.isEmpty),
      ("axiomGatePassed", allConstantForbiddenAxiomNames.isEmpty),
      ("forbiddenAxioms", toJson allConstantForbiddenAxiomNames),
      ("fullNamesDistinct", duplicateFullNames.isEmpty),
      ("inconsistentDuplicateTheorems",
        toJson inconsistentTheoremDuplicates),
      ("manifestPassed", manifestPassed),
      ("manifestValidation", manifestValidationJson manifestValidation),
      ("ownedModulesLoaded", unloadedOwnedModules.isEmpty),
      ("result", if passed then "PASS" else "FAIL"),
      ("theoremAxiomGatePassed", theoremForbiddenAxiomNames.isEmpty),
      ("unsafeDeclarationGatePassed", unsafeDeclarations.isEmpty)
    ]),
    ("classificationSchema", manifest.schemaVersion),
    ("duplicateLeafNames", duplicateLeafGroupsJson duplicateLeaves),
    ("generator", "TheoremInventory.lean"),
    ("generatedTheoremCount", theoremJson.size - authoredTheoremCount),
    ("importedModules",
      toJson <| sortedUniqueStrings <| config.imports.map Name.toString),
    ("ownedModules",
      toJson <| sortedUniqueStrings <| config.ownedModules.map Name.toString),
    ("ownedAxioms", ownedAxiomsJson ownedAxioms),
    ("ownedConstantCount", ownedConstants.size),
    ("schemaVersion", inventorySchema),
    ("theoremCount", theoremJson.size),
    ("theorems", toJson theoremJson),
    ("unloadedOwnedModules", toJson unloadedOwnedModules),
    ("unsafeDeclarations", unsafeDeclarationsJson unsafeDeclarations)
  ]
  return (json, passed)

def writeOutput (path? : Option System.FilePath) (json : Json) : IO Unit := do
  let text := json.pretty ++ "\n"
  match path? with
  | none => IO.print text
  | some path => IO.FS.writeFile path text

unsafe def run (args : List String) : IO UInt32 := do
  let config ←
    match parseArgs args with
    | .ok config => pure <| normalizeConfig config
    | .error message =>
        IO.eprintln message
        return 2
  try
    let manifest ← readClassificationManifest config.classificationPath?
    let (json, passed) ← buildInventory config manifest
    writeOutput config.outputPath? json
    return if passed then 0 else 1
  catch error =>
    IO.eprintln s!"theorem inventory failed: {error}"
    return 2

end TrackBTheoremInventory

unsafe def main (args : List String) : IO UInt32 :=
  TrackBTheoremInventory.run args

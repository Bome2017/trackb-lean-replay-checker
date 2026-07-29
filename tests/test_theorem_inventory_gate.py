# SPDX-FileCopyrightText: 2026 Sanjit Singh Mehat
# SPDX-License-Identifier: Apache-2.0
"""Hostile syntax tests for environment-derived theorem inventory."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "TheoremInventory.lean"
REPORT = ROOT / "validation" / "hostile_theorem_inventory_report.json"

EXTERNAL_MODULE = "InventoryExternalFixture"
SYNTAX_MODULE = "InventoryHostileSyntax"
UNSAFE_MODULE = "InventoryHostileUnsafe"

EXTERNAL_SOURCE = r"""
namespace InventoryExternalDependency

theorem importedExternalTheorem : True := by
  trivial

end InventoryExternalDependency
"""

SYNTAX_SOURCE = r"""
import InventoryExternalFixture

namespace InventoryHostileSyntax

/-
theorem commentOnlyPhantom : False := by
  contradiction
-/

def sourceContainsTheoremWord : String :=
  "theorem stringOnlyPhantom : False := by contradiction"

theorem
  multilineTheorem
    :
      True
    := by
      trivial

theorem θεώρημα : True := by
  trivial

theorem «quoted theorem» : True := by
  trivial

namespace Nested

theorem deepTheorem : True := by
  trivial

end Nested

namespace DuplicateLeft

theorem sameLeaf : True := by
  trivial

end DuplicateLeft

namespace DuplicateRight

theorem sameLeaf : True := by
  trivial

end DuplicateRight

theorem localOwnedTheorem : True := by
  trivial

@[
  simp
]
theorem attributedTheorem
    : True ∧ True := by
  simp

theorem        unusualWhitespaceTheorem
               :
                 True
               := by
                    trivial

structure GeneratedProofBundle where
  witness : True

end InventoryHostileSyntax
"""

UNSAFE_SOURCE = r"""
import InventoryHostileSyntax

namespace InventoryHostileUnsafe

theorem sorryAxDependent : True := by
  sorry

end InventoryHostileUnsafe
"""

PHANTOM_NAMES = {
    "InventoryHostileSyntax.commentOnlyPhantom",
    "InventoryHostileSyntax.stringOnlyPhantom",
    "InventoryHostileSyntax.sourceContainsTheoremWord",
}

CASE_IDS = (
    "multiline_theorem",
    "unicode_theorem",
    "quoted_identifier",
    "nested_namespace",
    "duplicate_leaf_names",
    "sorry_ax_dependency",
    "comment_text_ignored",
    "string_text_ignored",
    "definition_with_theorem_word_ignored",
    "generated_projection_or_recursor_not_authored",
    "imported_external_theorem_excluded",
    "local_owned_theorem_included",
    "multiline_attributes",
    "unusual_whitespace",
)


def normalized_source(source: str) -> str:
    return textwrap.dedent(source).lstrip()


def source_sha256(source: str) -> str:
    return hashlib.sha256(normalized_source(source).encode("utf-8")).hexdigest()


def run(
    *args: Path | str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def expected_report() -> dict:
    return {
        "schema_version": "trackb.hostile-theorem-inventory-report.v1",
        "result": "PASS",
        "release_version": "0.2.1",
        "test": "tests/test_theorem_inventory_gate.py",
        "generator": "TheoremInventory.lean",
        "fixture_sources": {
            EXTERNAL_MODULE: source_sha256(EXTERNAL_SOURCE),
            SYNTAX_MODULE: source_sha256(SYNTAX_SOURCE),
            UNSAFE_MODULE: source_sha256(UNSAFE_SOURCE),
        },
        "isolation": {
            "generated_under_system_temporary_directory": True,
            "hostile_lean_files_in_repository": 0,
            "hostile_olean_files_in_repository": 0,
        },
        "cases": {
            "multiline_theorem": "DISCOVERED",
            "unicode_theorem": "DISCOVERED_WITH_FULL_NAME",
            "quoted_identifier": "DISCOVERED_WITH_FULL_NAME",
            "nested_namespace": "DISCOVERED_WITH_FULL_NAME",
            "duplicate_leaf_names": "PRESERVED_AS_DISTINCT_FULL_NAMES",
            "sorry_ax_dependency": "DISCOVERED_AND_GATE_FAILED",
            "comment_text_ignored": "NOT_DISCOVERED",
            "string_text_ignored": "NOT_DISCOVERED",
            "definition_with_theorem_word_ignored": "NOT_DISCOVERED",
            "generated_projection_or_recursor_not_authored": "PASS",
            "imported_external_theorem_excluded": "PASS",
            "local_owned_theorem_included": "PASS",
            "multiline_attributes": "DISCOVERED",
            "unusual_whitespace": "DISCOVERED",
        },
        "safe_fixture_gate": {
            "exit_code": 0,
            "result": "PASS",
            "all_owned_constant_axiom_gate": "PASS",
            "theorem_axiom_gate": "PASS",
        },
        "sorry_fixture_gate": {
            "exit_code": 1,
            "result": "FAIL",
            "all_owned_constant_axiom_gate": "FAIL",
            "theorem_axiom_gate": "FAIL",
            "forbidden_axiom": "sorryAx",
            "offending_theorem": (
                "InventoryHostileUnsafe.sorryAxDependent"
            ),
        },
        "nonclaims": [
            (
                "The hostile modules are generated and compiled only under a "
                "system temporary directory."
            ),
            (
                "The source-tracked test generator is not a TrackB release "
                "theorem module."
            ),
            (
                "Generated projections and recursors remain environment "
                "constants but are not counted as authored theorems."
            ),
        ],
    }


class TheoremInventoryHostileGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not INVENTORY.is_file():
            raise AssertionError("TheoremInventory.lean is missing")

        cls.temporary = tempfile.TemporaryDirectory(
            prefix="trackb-theorem-inventory-"
        )
        cls.temporary_root = Path(cls.temporary.name).resolve()
        if (
            cls.temporary_root == ROOT.resolve()
            or ROOT.resolve() in cls.temporary_root.parents
        ):
            raise AssertionError("hostile fixtures must be outside the repository")

        cls.external_path = cls.write_module(
            EXTERNAL_MODULE,
            EXTERNAL_SOURCE,
        )
        cls.syntax_path = cls.write_module(SYNTAX_MODULE, SYNTAX_SOURCE)
        cls.unsafe_path = cls.write_module(UNSAFE_MODULE, UNSAFE_SOURCE)

        cls.lean_env = dict(os.environ)
        cls.lean_env["LEAN_PATH"] = str(cls.temporary_root)

        cls.compile_module(cls.external_path)
        cls.compile_module(cls.syntax_path)
        cls.compile_module(cls.unsafe_path)

        cls.safe_exit, cls.safe_inventory = cls.run_inventory(
            import_module=SYNTAX_MODULE,
            owned_modules=[SYNTAX_MODULE],
            output_name="safe-inventory.json",
        )
        cls.unsafe_exit, cls.unsafe_inventory = cls.run_inventory(
            import_module=UNSAFE_MODULE,
            owned_modules=[SYNTAX_MODULE, UNSAFE_MODULE],
            output_name="unsafe-inventory.json",
        )

        cls.safe_by_name = {
            theorem["name"]: theorem
            for theorem in cls.safe_inventory["theorems"]
        }
        cls.unsafe_by_name = {
            theorem["name"]: theorem
            for theorem in cls.unsafe_inventory["theorems"]
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    @classmethod
    def write_module(cls, module: str, source: str) -> Path:
        path = cls.temporary_root / f"{module}.lean"
        path.write_text(normalized_source(source), encoding="utf-8")
        return path

    @classmethod
    def compile_module(cls, source_path: Path) -> None:
        output_path = source_path.with_suffix(".olean")
        completed = run(
            "lake",
            "env",
            "lean",
            "-R",
            cls.temporary_root,
            "-o",
            output_path,
            source_path,
            env=cls.lean_env,
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stdout + completed.stderr)
        if not output_path.is_file():
            raise AssertionError(f"missing compiled fixture: {output_path}")

    @classmethod
    def run_inventory(
        cls,
        *,
        import_module: str,
        owned_modules: list[str],
        output_name: str,
    ) -> tuple[int, dict]:
        output_path = cls.temporary_root / output_name
        command: list[Path | str] = [
            "lake",
            "env",
            "lean",
            "--run",
            INVENTORY,
            "--import",
            import_module,
        ]
        for module in owned_modules:
            command.extend(["--owned-module", module])
        command.extend(["--output", output_path])
        completed = run(*command, env=cls.lean_env)
        if completed.returncode not in {0, 1}:
            raise AssertionError(completed.stdout + completed.stderr)
        if not output_path.is_file():
            raise AssertionError(completed.stdout + completed.stderr)
        return completed.returncode, json.loads(
            output_path.read_text(encoding="utf-8")
        )

    def authored_entries_with_leaf(self, leaf: str) -> list[dict]:
        return [
            theorem
            for theorem in self.safe_inventory["theorems"]
            if theorem["authoredDeclaration"]
            and theorem["leafName"] == leaf
        ]

    def assert_authored(
        self,
        full_name: str,
        *,
        origin: str = SYNTAX_MODULE,
    ) -> dict:
        theorem = self.safe_by_name[full_name]
        self.assertTrue(theorem["authoredDeclaration"])
        self.assertEqual(theorem["originModule"], origin)
        self.assertTrue(
            theorem["environmentProvenance"]["exactDeclarationRange"]
        )
        self.assertEqual(
            theorem["environmentProvenance"]["kind"],
            "authored",
        )
        return theorem

    def test_safe_hostile_syntax_fixture_passes_axiom_gates(self) -> None:
        self.assertEqual(self.safe_exit, 0)
        checks = self.safe_inventory["checks"]
        self.assertEqual(checks["result"], "PASS")
        self.assertTrue(checks["allOwnedConstantAxiomGatePassed"])
        self.assertTrue(checks["theoremAxiomGatePassed"])
        self.assertTrue(checks["authoredAxiomGatePassed"])
        self.assertTrue(checks["unsafeDeclarationGatePassed"])
        self.assertTrue(checks["ownedModulesLoaded"])
        self.assertEqual(self.safe_inventory["axiomOffendingConstants"], [])
        self.assertEqual(self.safe_inventory["ownedAxioms"], [])

    def test_multiline_unicode_and_quoted_theorems_are_discovered(self) -> None:
        self.assert_authored(
            "InventoryHostileSyntax.multilineTheorem"
        )
        self.assert_authored("InventoryHostileSyntax.θεώρημα")

        quoted = self.authored_entries_with_leaf("quoted theorem")
        self.assertEqual(len(quoted), 1)
        self.assertEqual(quoted[0]["originModule"], SYNTAX_MODULE)
        self.assertEqual(
            quoted[0]["name"],
            "InventoryHostileSyntax.«quoted theorem»",
        )

    def test_nested_and_duplicate_leaf_full_names_are_preserved(self) -> None:
        self.assert_authored(
            "InventoryHostileSyntax.Nested.deepTheorem"
        )
        left = "InventoryHostileSyntax.DuplicateLeft.sameLeaf"
        right = "InventoryHostileSyntax.DuplicateRight.sameLeaf"
        self.assert_authored(left)
        self.assert_authored(right)
        self.assertNotEqual(left, right)

        groups = {
            group["leafName"]: group["fullNames"]
            for group in self.safe_inventory["duplicateLeafNames"]
        }
        self.assertEqual(groups["sameLeaf"], [left, right])
        self.assertTrue(self.safe_inventory["checks"]["fullNamesDistinct"])

    def test_sorry_ax_theorem_is_discovered_and_fails_closed(self) -> None:
        self.assertEqual(self.unsafe_exit, 1)
        checks = self.unsafe_inventory["checks"]
        self.assertEqual(checks["result"], "FAIL")
        self.assertFalse(checks["allOwnedConstantAxiomGatePassed"])
        self.assertFalse(checks["theoremAxiomGatePassed"])
        self.assertTrue(checks["authoredAxiomGatePassed"])
        self.assertTrue(checks["unsafeDeclarationGatePassed"])
        self.assertTrue(checks["ownedModulesLoaded"])
        self.assertIn("sorryAx", checks["forbiddenAxioms"])

        name = "InventoryHostileUnsafe.sorryAxDependent"
        theorem = self.unsafe_by_name[name]
        self.assertTrue(theorem["authoredDeclaration"])
        self.assertIn("sorryAx", theorem["transitiveAxioms"])
        offending_names = {
            entry["name"]
            for entry in self.unsafe_inventory["axiomOffendingConstants"]
        }
        self.assertIn(name, offending_names)
        self.assertEqual(self.unsafe_inventory["ownedAxioms"], [])

    def test_comments_strings_and_definitions_are_not_theorems(self) -> None:
        observed_names = set(self.safe_by_name)
        self.assertTrue(PHANTOM_NAMES.isdisjoint(observed_names))
        observed_leaves = {
            theorem["leafName"]
            for theorem in self.safe_inventory["theorems"]
        }
        self.assertNotIn("commentOnlyPhantom", observed_leaves)
        self.assertNotIn("stringOnlyPhantom", observed_leaves)
        self.assertNotIn("sourceContainsTheoremWord", observed_leaves)

    def test_external_is_excluded_and_local_owned_theorem_is_included(
        self,
    ) -> None:
        external = (
            "InventoryExternalDependency.importedExternalTheorem"
        )
        self.assertNotIn(external, self.safe_by_name)
        self.assertEqual(
            self.safe_inventory["ownedModules"],
            [SYNTAX_MODULE],
        )
        self.assert_authored(
            "InventoryHostileSyntax.localOwnedTheorem"
        )

    def test_generated_projection_and_recursor_are_not_authored(self) -> None:
        projection_name = (
            "InventoryHostileSyntax.GeneratedProofBundle.witness"
        )
        projection = self.safe_by_name[projection_name]
        self.assertFalse(projection["authoredDeclaration"])
        self.assertTrue(
            projection["environmentProvenance"]["generatedProjection"]
        )
        self.assertEqual(
            projection["environmentProvenance"]["kind"],
            "generated",
        )
        self.assertEqual(
            projection["classification"]["category"],
            "generated",
        )

        authored_names = {
            theorem["name"]
            for theorem in self.safe_inventory["theorems"]
            if theorem["authoredDeclaration"]
        }
        self.assertNotIn(projection_name, authored_names)
        self.assertNotIn(
            "InventoryHostileSyntax.GeneratedProofBundle.rec",
            authored_names,
        )

    def test_multiline_attributes_and_unusual_whitespace_are_discovered(
        self,
    ) -> None:
        self.assert_authored(
            "InventoryHostileSyntax.attributedTheorem"
        )
        self.assert_authored(
            "InventoryHostileSyntax.unusualWhitespaceTheorem"
        )

    def test_all_fourteen_required_cases_are_reported(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(set(report["cases"]), set(CASE_IDS))
        self.assertEqual(report, expected_report())

    def test_hostile_modules_and_outputs_remain_outside_repository(
        self,
    ) -> None:
        for path in (
            self.external_path,
            self.syntax_path,
            self.unsafe_path,
        ):
            self.assertTrue(path.is_file())
            self.assertNotEqual(path.parent, ROOT)
            self.assertNotIn(ROOT.resolve(), path.resolve().parents)

        hostile_stems = {
            EXTERNAL_MODULE,
            SYNTAX_MODULE,
            UNSAFE_MODULE,
        }
        repository_hostile_files = [
            path
            for path in ROOT.rglob("*")
            if ".lake" not in path.parts
            and path.is_file()
            and path.stem in hostile_stems
            and path.suffix in {".lean", ".olean"}
        ]
        self.assertEqual(repository_hostile_files, [])


if __name__ == "__main__":
    unittest.main()

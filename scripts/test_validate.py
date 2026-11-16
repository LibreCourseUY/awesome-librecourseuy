"""Self-check for catalog validation. Run: uv run python scripts/test_validate.py"""

from __future__ import annotations

import io
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate  # noqa: E402
from models import ORGS_DIR, load_entry_files, load_org_files  # noqa: E402


class CatalogSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entries = load_entry_files()
        self.orgs = load_org_files()
        self.files = {**self.entries, **self.orgs}
        self.entry_path = next(iter(self.entries))
        self.org_path = next(iter(self.orgs))

    def test_unrestricted_selection_includes_projects_and_orgs(self) -> None:
        self.assertEqual(validate.select_network_files(self.files, None), self.files)

    def test_empty_selection_skips_all_network_checks(self) -> None:
        self.assertEqual(validate.select_network_files(self.files, []), {})

    def test_relative_and_absolute_paths_for_both_types(self) -> None:
        for path in (self.entry_path, self.org_path):
            relative = os.path.relpath(path)
            for spelling in (str(path), relative, os.path.join(".", relative)):
                with self.subTest(path=spelling):
                    selected = validate.select_network_files(self.files, [spelling])
                    self.assertEqual(list(selected), [path])

    def test_mixed_selection(self) -> None:
        selected = validate.select_network_files(
            self.files, [str(self.entry_path), str(self.org_path)]
        )
        self.assertEqual(list(selected), [self.entry_path, self.org_path])

    def test_unrelated_and_missing_files_are_rejected(self) -> None:
        for path in (ORGS_DIR / "missing.json", ORGS_DIR.parent / "categories.json"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, path.name):
                validate.select_network_files(self.files, [str(path)])


class NetworkValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entries = dict(list(load_entry_files().items())[:2])
        self.orgs = dict(list(load_org_files().items())[:2])
        self.entry_path = next(iter(self.entries))
        self.org_path = next(iter(self.orgs))

    def run_validation(self, arguments: list[str], org_errors: list[str] | None = None):
        output = io.StringIO()
        errors = io.StringIO()
        with (
            patch.object(sys, "argv", ["validate.py", *arguments]),
            patch.object(validate, "load_entry_files", return_value=self.entries),
            patch.object(validate, "load_org_files", return_value=self.orgs),
            patch.object(validate, "check_network", return_value=[]) as entry_check,
            patch.object(validate, "check_org_network", return_value=org_errors or []) as org_check,
            redirect_stdout(output),
            redirect_stderr(errors),
        ):
            status = validate.main()
        return (
            status,
            [call.args[0] for call in entry_check.call_args_list],
            [call.args[0] for call in org_check.call_args_list],
            output.getvalue(),
            errors.getvalue(),
        )

    def test_only_checks_the_selected_catalog_files(self) -> None:
        cases = [
            (["--only", str(self.entry_path)], [self.entries[self.entry_path]], []),
            (["--only", str(self.org_path)], [], [self.orgs[self.org_path]]),
            (
                ["--only", str(self.entry_path), str(self.org_path)],
                [self.entries[self.entry_path]],
                [self.orgs[self.org_path]],
            ),
            (["--only"], [], []),
            (["--offline"], [], []),
            ([], list(self.entries.values()), list(self.orgs.values())),
        ]
        for arguments, expected_entries, expected_orgs in cases:
            with self.subTest(arguments=arguments):
                status, entries, orgs, _, errors = self.run_validation(arguments)
                self.assertEqual(status, 0, errors)
                self.assertCountEqual(entries, expected_entries)
                self.assertCountEqual(orgs, expected_orgs)

    def test_org_network_failure_fails_validation(self) -> None:
        status, _, _, _, errors = self.run_validation(
            ["--only", str(self.org_path)], ["organization not found or private"]
        )
        self.assertEqual(status, 1)
        self.assertIn("organization not found or private", errors)

    def test_invalid_file_selection_fails_before_network_checks(self) -> None:
        status, entries, orgs, _, errors = self.run_validation(
            ["--only", str(ORGS_DIR / "missing.json")]
        )
        self.assertEqual(status, 2)
        self.assertEqual(entries, [])
        self.assertEqual(orgs, [])
        self.assertIn("missing.json", errors)

    def test_schema_checks_still_cover_unselected_organizations(self) -> None:
        errors = io.StringIO()
        with (
            patch.object(sys, "argv", ["validate.py", "--only", str(self.entry_path)]),
            patch.object(validate, "load_entry_files", return_value=self.entries),
            patch.object(validate, "load_org_files", side_effect=ValueError("invalid org schema")),
            patch.object(validate, "check_network") as entry_check,
            patch.object(validate, "check_org_network") as org_check,
            redirect_stderr(errors),
        ):
            self.assertEqual(validate.main(), 1)
        entry_check.assert_not_called()
        org_check.assert_not_called()
        self.assertIn("invalid org schema", errors.getvalue())


if __name__ == "__main__":
    unittest.main()

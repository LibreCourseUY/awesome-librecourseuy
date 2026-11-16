"""Self-check for Gitsion synchronization; all API calls are mocked."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import call, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sync_gitsion  # noqa: E402


class GitsionSyncTests(unittest.TestCase):
    def run_sync(self, responses: list, token: str = "test-token"):
        output = io.StringIO()
        errors = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for index, repository in enumerate(("owner/existing", "owner/new")):
                path = Path(directory) / f"{index}.json"
                path.write_text(json.dumps({"repository": f"https://github.com/{repository}"}))
                paths.append(str(path))
            with (
                patch.object(sync_gitsion, "TOKEN", token),
                patch.object(sync_gitsion.glob, "glob", return_value=paths),
                patch.object(sync_gitsion, "request", side_effect=responses) as request,
                redirect_stdout(output),
                redirect_stderr(errors),
            ):
                status = sync_gitsion.main()
        return status, request.call_args_list, output.getvalue(), errors.getvalue()

    @staticmethod
    def tracked_repositories():
        return 200, {
            "repositories": [
                {"fullName": "OWNER/Existing"},
                {"fullName": "history/retired"},
            ]
        }

    def test_adds_new_repositories_and_reports_retained_history(self) -> None:
        status, requests, output, errors = self.run_sync(
            [self.tracked_repositories(), (201, None)]
        )
        self.assertEqual(status, 0, errors)
        self.assertEqual(
            requests,
            [call("/api/v1/repos"), call("/api/v1/repos", "POST", {"repository": "owner/new"})],
        )
        self.assertIn("retained outside catalog: history/retired", output)
        self.assertIn("added=1 skipped=1 retained=1 failed=0", output)

    def test_concurrent_addition_is_already_tracked(self) -> None:
        status, _, output, errors = self.run_sync(
            [self.tracked_repositories(), (409, None)]
        )
        self.assertEqual(status, 0, errors)
        self.assertIn("added=0 skipped=2 retained=1 failed=0", output)

    def test_failed_addition_fails_the_sync(self) -> None:
        status, _, output, errors = self.run_sync(
            [self.tracked_repositories(), (500, {"error": "unavailable"})]
        )
        self.assertEqual(status, 1)
        self.assertIn("retained=1 failed=1", output)
        self.assertIn("FAILED owner/new", errors)

    def test_listing_failure_does_not_add_repositories(self) -> None:
        status, requests, _, errors = self.run_sync([(500, None)])
        self.assertEqual(status, 1)
        self.assertEqual(requests, [call("/api/v1/repos")])
        self.assertIn("could not list tracked repositories", errors)

    def test_missing_token_does_not_call_the_api(self) -> None:
        status, requests, _, errors = self.run_sync([], token="")
        self.assertEqual(status, 1)
        self.assertEqual(requests, [])
        self.assertIn("GITSION_ADMIN_TOKEN is not set", errors)


if __name__ == "__main__":
    unittest.main()

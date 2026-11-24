"""Self-check for Gitsion synchronization; all API calls are mocked."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import call, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sync_gitsion  # noqa: E402

LIST = call("/api/v1/repos")
ADD_NEW = call("/api/v1/repos", "POST", {"repository": "owner/new"})
REMOVE_RETIRED = call("/api/v1/repos/history/retired", "DELETE")


class GitsionSyncTests(unittest.TestCase):
    def run_sync(
        self,
        responses: list,
        token: str = "test-token",
        entries: tuple[str, ...] = ("owner/existing", "owner/new"),
        names: dict[str, str | None] | None = None,
        argv: tuple[str, ...] = (),
    ):
        """Run a sync over entries; GitHub confirms every name unless names says otherwise."""
        output = io.StringIO()
        errors = io.StringIO()
        names = names or {}
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for index, repository in enumerate(entries):
                path = Path(directory) / f"{index}.json"
                url = repository if "://" in repository else f"https://github.com/{repository}"
                path.write_text(json.dumps({"repository": url}))
                paths.append(str(path))
            with (
                patch.object(sync_gitsion, "TOKEN", token),
                patch.object(sync_gitsion.glob, "glob", return_value=paths),
                patch.object(sync_gitsion, "request", side_effect=responses) as request,
                patch.object(sync_gitsion, "current_name", side_effect=lambda r: names.get(r, r)),
                redirect_stdout(output),
                redirect_stderr(errors),
            ):
                status = sync_gitsion.main(list(argv))
        return status, request.call_args_list, output.getvalue(), errors.getvalue()

    @staticmethod
    def tracked_repositories(*extra: str):
        names = ("OWNER/Existing", "history/retired", *extra)
        return 200, {"repositories": [{"fullName": name} for name in names]}

    def test_adds_new_repositories_and_removes_unlisted_ones(self) -> None:
        status, requests, output, errors = self.run_sync(
            [self.tracked_repositories(), (201, None), (204, None)]
        )
        self.assertEqual(status, 0, errors)
        self.assertEqual(requests, [LIST, ADD_NEW, REMOVE_RETIRED])
        self.assertIn("added owner/new", output)
        self.assertIn("removed history/retired", output)
        self.assertIn("added=1 skipped=1 removed=1 kept=0 failed=0", output)

    def test_renamed_repository_stays_tracked_under_its_new_name(self) -> None:
        status, requests, output, errors = self.run_sync(
            [self.tracked_repositories("Owner/Renamed"), (204, None)],
            entries=("owner/existing", "owner/old"),
            names={"owner/old": "owner/renamed"},
        )
        self.assertEqual(status, 0, errors)
        self.assertEqual(requests, [LIST, REMOVE_RETIRED])
        self.assertIn("renamed owner/old is tracked as owner/renamed: update", output)
        self.assertIn("added=0 skipped=2 removed=1 kept=0 failed=0", output)

    def test_concurrent_addition_is_already_tracked(self) -> None:
        status, requests, output, errors = self.run_sync(
            [self.tracked_repositories(), (409, None), (204, None)]
        )
        self.assertEqual(status, 0, errors)
        self.assertEqual(requests, [LIST, ADD_NEW, REMOVE_RETIRED])
        self.assertIn("added=0 skipped=2 removed=1 kept=0 failed=0", output)

    def test_failed_addition_removes_nothing(self) -> None:
        status, requests, output, errors = self.run_sync(
            [self.tracked_repositories(), (500, {"error": "unavailable"})]
        )
        self.assertEqual(status, 1)
        self.assertEqual(requests, [LIST, ADD_NEW])
        self.assertIn("kept history/retired", output)
        self.assertIn("removed=0 kept=1 failed=1", output)
        self.assertIn("FAILED owner/new", errors)

    def test_repository_tracked_under_an_unconfirmed_name_removes_nothing(self) -> None:
        # history/retired may be what owner/new is called now: GitHub could not say.
        status, requests, output, errors = self.run_sync(
            [self.tracked_repositories(), (409, None)], names={"owner/new": None}
        )
        self.assertEqual(status, 1)
        self.assertEqual(requests, [LIST, ADD_NEW])
        self.assertIn("kept history/retired", output)
        self.assertIn("FAILED owner/new: tracked under a name GitHub could not confirm", errors)

    def test_new_repository_does_not_need_a_confirmed_name(self) -> None:
        status, requests, output, errors = self.run_sync(
            [self.tracked_repositories(), (201, None), (204, None)], names={"owner/new": None}
        )
        self.assertEqual(status, 0, errors)
        self.assertEqual(requests, [LIST, ADD_NEW, REMOVE_RETIRED])

    def test_failed_removal_fails_the_sync_and_tries_the_rest(self) -> None:
        status, requests, output, errors = self.run_sync(
            [self.tracked_repositories("history/second"), (201, None), (500, None), (204, None)]
        )
        self.assertEqual(status, 1)
        self.assertEqual(
            requests,
            [LIST, ADD_NEW, REMOVE_RETIRED, call("/api/v1/repos/history/second", "DELETE")],
        )
        self.assertIn("FAILED to remove history/retired", errors)
        self.assertIn("removed=1 kept=0 failed=1", output)

    def test_catalog_without_github_repositories_removes_nothing(self) -> None:
        for entries in ((), ("https://gitlab.com/owner/existing",)):
            with self.subTest(entries=entries):
                status, requests, _, errors = self.run_sync(
                    [self.tracked_repositories()], entries=entries
                )
                self.assertEqual(status, 1)
                self.assertEqual(requests, [LIST])
                self.assertIn("refusing to untrack everything", errors)

    def test_entry_hosted_elsewhere_is_left_out(self) -> None:
        status, requests, output, errors = self.run_sync(
            [self.tracked_repositories(), (204, None)],
            entries=("owner/existing", "https://gitlab.com/history/retired"),
        )
        self.assertEqual(status, 0, errors)
        self.assertEqual(requests, [LIST, REMOVE_RETIRED])
        self.assertIn("not a GitHub repository", output)

    def test_dry_run_reports_without_changing_anything(self) -> None:
        status, requests, output, errors = self.run_sync(
            [self.tracked_repositories()], token="", argv=("--dry-run",)
        )
        self.assertEqual(status, 0, errors)
        self.assertEqual(requests, [LIST])
        self.assertIn("would add owner/new", output)
        self.assertIn("would remove history/retired", output)
        self.assertIn("dry run: added=1 skipped=1 removed=1 kept=0 failed=0", output)

    def test_dry_run_keeps_everything_when_a_name_is_unconfirmed(self) -> None:
        status, requests, output, errors = self.run_sync(
            [self.tracked_repositories()], argv=("--dry-run",), names={"owner/new": None}
        )
        self.assertEqual(status, 1)
        self.assertEqual(requests, [LIST])
        self.assertIn("kept history/retired", output)
        self.assertIn("UNCONFIRMED owner/new", errors)

    def test_listing_failure_changes_nothing(self) -> None:
        status, requests, _, errors = self.run_sync([(500, None)])
        self.assertEqual(status, 1)
        self.assertEqual(requests, [LIST])
        self.assertIn("could not list tracked repositories", errors)

    def test_missing_token_does_not_call_the_api(self) -> None:
        status, requests, _, errors = self.run_sync([], token="")
        self.assertEqual(status, 1)
        self.assertEqual(requests, [])
        self.assertIn("GITSION_ADMIN_TOKEN is not set", errors)


class CurrentNameTests(unittest.TestCase):
    def lookup(self, answer):
        with (
            patch.object(sync_gitsion, "TOKEN", "gitsion-secret"),
            patch.object(sync_gitsion, "GITHUB_TOKEN", "github-token"),
            patch.object(sync_gitsion, "GITHUB_API", "https://api.github.test"),
            patch.object(sync_gitsion.urllib.request, "urlopen", side_effect=answer) as urlopen,
        ):
            return sync_gitsion.current_name("owner/old"), urlopen.call_args.args[0]

    def test_asks_github_with_its_own_token_only(self) -> None:
        name, sent = self.lookup([io.BytesIO(b'{"full_name": "Owner/Renamed"}')])
        self.assertEqual(name, "Owner/Renamed")
        self.assertEqual(sent.full_url, "https://api.github.test/repos/owner/old")
        self.assertEqual(sent.get_header("Authorization"), "Bearer github-token")
        self.assertNotIn("gitsion-secret", str(sent.header_items()))

    def test_unknown_when_github_cannot_tell(self) -> None:
        not_found = urllib.error.HTTPError("https://api.github.test", 404, "Not Found", {}, None)
        self.addCleanup(not_found.close)
        for answer in (not_found, urllib.error.URLError("down"), TimeoutError()):
            with self.subTest(answer=answer):
                self.assertIsNone(self.lookup(answer)[0])
        for body in (b"not json", b"[]", b'{"full_name": null}'):
            with self.subTest(body=body):
                self.assertIsNone(self.lookup([io.BytesIO(body)])[0])


if __name__ == "__main__":
    unittest.main()

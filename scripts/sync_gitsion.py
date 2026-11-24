"""Keep gitsion tracking exactly the listed projects.

Runs on a push that changes entries/*.json. The list is the source of truth:
each entry's GitHub repository is added to the gitsion dashboard, and every
tracked repository that no entry lists is removed from it. Repositories already
tracked are skipped, so updating one entry does not re-fetch the rest from
GitHub.

Nothing is removed unless the whole catalog was reconciled. A repository that
was renamed or transferred stays tracked while its entry still points at the
former name, and a run that could not add an entry, or tell what its repository
is called now, leaves the tracked set as it was and fails.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("GITSION_URL", "https://api.gitsion.librecourse.uy").rstrip("/")
TOKEN = os.environ.get("GITSION_ADMIN_TOKEN", "").strip()
GITHUB_API = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
USER_AGENT = "gitsion-sync/1.0 (+https://github.com/LibreCourseUY/awesome-librecourseuy)"
TIMEOUT = 60


def request(path: str, method: str = "GET", body: dict | None = None) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", USER_AGENT)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            payload = response.read()
            return response.status, json.loads(payload) if payload else None
    except urllib.error.HTTPError as error:
        payload = error.read()
        try:
            parsed = json.loads(payload) if payload else None
        except json.JSONDecodeError:
            parsed = None
        return error.code, parsed


def current_name(ref: str) -> str | None:
    """Return what GitHub calls a repository now, following renames and transfers.

    None means GitHub could not tell: the repository is gone or private, or the
    request failed. The gitsion token is never sent to GitHub.
    """
    req = urllib.request.Request(f"{GITHUB_API}/repos/{urllib.parse.quote(ref)}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", USER_AGENT)
    if GITHUB_TOKEN:
        req.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            data = json.load(response)
    except (OSError, ValueError):
        return None
    name = data.get("full_name") if isinstance(data, dict) else None
    return name if isinstance(name, str) and name else None


def repo_ref(url: str) -> str | None:
    """Return owner/name for a GitHub repository URL, or None for anything else."""
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None
    return f"{parts[0]}/{parts[1].removesuffix('.git')}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be added and removed without changing gitsion",
    )
    dry_run = parser.parse_args(argv).dry_run

    if not TOKEN and not dry_run:
        print("GITSION_ADMIN_TOKEN is not set", file=sys.stderr)
        return 1

    status, payload = request("/api/v1/repos")
    if status != 200:
        print(f"could not list tracked repositories: {status} {payload}", file=sys.stderr)
        return 1
    tracked = {
        repo["fullName"].lower(): repo["fullName"]
        for repo in (payload or {}).get("repositories", [])
    }

    added: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []
    listed: set[str] = set()

    for path in sorted(glob.glob("entries/*.json")):
        with open(path, encoding="utf-8") as handle:
            entry = json.load(handle)
        ref = repo_ref(entry.get("repository") or "")
        if ref is None:
            print(f"skip {path}: not a GitHub repository ({entry.get('repository')})")
            continue
        listed.add(ref.lower())
        if ref.lower() in tracked:
            skipped.append(ref)
            continue

        # Not tracked under the listed name: the repository is either new, or
        # tracked under the name it was renamed to.
        current = current_name(ref)
        if current and current.lower() in tracked:
            listed.add(current.lower())
            skipped.append(ref)
            print(f"renamed {ref} is tracked as {current}: update {path}")
            continue

        if dry_run:
            if current:
                added.append(ref)
                print(f"would add {ref}")
            else:
                failed.append(ref)
                print(f"UNCONFIRMED {ref}: GitHub could not tell its current name", file=sys.stderr)
            continue

        status, payload = request("/api/v1/repos", "POST", {"repository": ref})
        if status == 201:
            added.append(ref)
            print(f"added {ref}")
        elif status == 409 and current:
            # Another sync won the race; the repository is tracked either way.
            skipped.append(ref)
            print(f"already tracked {ref}")
        elif status == 409:
            # Tracked under a name GitHub could not confirm, which may be one of
            # the repositories that look unlisted.
            failed.append(ref)
            print(f"FAILED {ref}: tracked under a name GitHub could not confirm", file=sys.stderr)
        else:
            failed.append(ref)
            print(f"FAILED {ref}: {status} {payload}", file=sys.stderr)

    # A checkout without entries must not read as a catalog that lists nothing.
    if not listed:
        print("no GitHub repository is listed: refusing to untrack everything", file=sys.stderr)
        return 1

    reconciled = not failed
    removed: list[str] = []
    kept: list[str] = []
    for name in (name for key, name in sorted(tracked.items()) if key not in listed):
        if not reconciled:
            kept.append(name)
            print(f"kept {name}: unlisted, but the catalog could not be fully reconciled")
        elif dry_run:
            removed.append(name)
            print(f"would remove {name}")
        else:
            status, payload = request(f"/api/v1/repos/{urllib.parse.quote(name)}", "DELETE")
            if status == 204:
                removed.append(name)
                print(f"removed {name}")
            else:
                failed.append(name)
                print(f"FAILED to remove {name}: {status} {payload}", file=sys.stderr)

    print(
        f"\n{'dry run: ' if dry_run else ''}added={len(added)} skipped={len(skipped)} "
        f"removed={len(removed)} kept={len(kept)} failed={len(failed)}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

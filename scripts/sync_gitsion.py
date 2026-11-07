"""Track every listed project in gitsion.

Runs on a push that changes entries/*.json. The list is the source of truth:
each entry's GitHub repository is added to the gitsion dashboard. The call is
idempotent: repositories already tracked are skipped, so updating one entry
does not re-fetch the rest from GitHub.
"""

from __future__ import annotations

import glob
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("GITSION_URL", "https://api.gitsion.librecourse.uy").rstrip("/")
TOKEN = os.environ.get("GITSION_ADMIN_TOKEN", "").strip()
TIMEOUT = 60


def request(path: str, method: str = "GET", body: dict | None = None) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Accept", "application/json")
    req.add_header(
        "User-Agent",
        "gitsion-sync/1.0 (+https://github.com/LibreCourseUY/awesome-librecourseuy)",
    )
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


def repo_ref(url: str) -> str | None:
    """Return owner/name for a GitHub repository URL, or None for anything else."""
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None
    return f"{parts[0]}/{parts[1].removesuffix('.git')}"


def main() -> int:
    if not TOKEN:
        print("GITSION_ADMIN_TOKEN is not set", file=sys.stderr)
        return 1

    status, payload = request("/api/v1/repos")
    if status != 200:
        print(f"could not list tracked repositories: {status} {payload}", file=sys.stderr)
        return 1
    tracked = {
        repo["fullName"].lower()
        for repo in (payload or {}).get("repositories", [])
    }

    added: list[str] = []
    skipped: list[str] = []
    failed: list[tuple[str, int, object]] = []

    for path in sorted(glob.glob("entries/*.json")):
        with open(path, encoding="utf-8") as handle:
            entry = json.load(handle)
        ref = repo_ref(entry.get("repository") or "")
        if ref is None:
            print(f"skip {path}: not a GitHub repository ({entry.get('repository')})")
            continue
        if ref.lower() in tracked:
            skipped.append(ref)
            continue

        status, payload = request("/api/v1/repos", "POST", {"repository": ref})
        if status == 201:
            added.append(ref)
            print(f"added {ref}")
        elif status == 409:
            # Another sync won the race; the repository is tracked either way.
            skipped.append(ref)
            print(f"already tracked {ref}")
        else:
            failed.append((ref, status, payload))
            print(f"FAILED {ref}: {status} {payload}", file=sys.stderr)

    print(f"\nadded={len(added)} skipped={len(skipped)} failed={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

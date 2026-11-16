"""Validate every entries/*.json and orgs/*.json. Exits non-zero on errors.

Schema and cross-file checks always cover every entry. The network checks (URL
liveness and repository verification) cover every entry too, unless --only
narrows them to the given project and organization files or --offline skips them.
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from models import Entry, Org, load_categories, load_entry_files, load_org_files
from urls import org_ok, repository_ok, url_ok


def select_network_files(
    files: dict[Path, Entry | Org], only: list[str] | None
) -> dict[Path, Entry | Org]:
    """Pick catalog files for network checks: every one, or only the given files.

    Narrowing them to the files a pull request touches keeps a third-party site
    that is down from blocking unrelated changes.
    """
    if only is None:
        return dict(files)
    selected: dict[Path, Entry | Org] = {}
    for raw in only:
        path = Path(raw).resolve()
        if path not in files:
            raise ValueError(f"{raw}: not a catalog file (deleted, or outside entries/ and orgs/)")
        selected[path] = files[path]
    return selected


def check_network(entry: Entry) -> list[str]:
    errors: list[str] = []
    ok, detail = url_ok(str(entry.url))
    if not ok:
        errors.append(f"{entry.name}: url not reachable ({detail})")
    ok, detail = repository_ok(str(entry.repository), entry.license)
    if not ok:
        errors.append(f"{entry.name}: repository check failed ({detail})")
    return errors


def check_org_network(org: Org) -> list[str]:
    errors: list[str] = []
    ok, detail = url_ok(str(org.url))
    if not ok:
        errors.append(f"{org.name}: url not reachable ({detail})")
    ok, detail = org_ok(str(org.repository))
    if not ok:
        errors.append(f"{org.name}: organization check failed ({detail})")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    network = parser.add_mutually_exclusive_group()
    network.add_argument(
        "--offline",
        action="store_true",
        help="skip the network checks (URL liveness and repository verification)",
    )
    network.add_argument(
        "--only",
        nargs="*",
        metavar="FILE",
        help="check the network only for these project or org files; with no files, skip it",
    )
    args = parser.parse_args()

    categories = load_categories()
    try:
        files = load_entry_files()
        org_files = load_org_files()
    except ValueError as exc:
        print(f"invalid entry: {exc}", file=sys.stderr)
        return 1
    try:
        catalog: dict[Path, Entry | Org] = {**files, **org_files}
        selected = {} if args.offline else select_network_files(catalog, args.only)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    entries = list(files.values())
    orgs = list(org_files.values())
    selected_entries = [entry for path, entry in files.items() if path in selected]
    selected_orgs = [org for path, org in org_files.items() if path in selected]
    errors: list[str] = []
    # Orgs and projects are separate namespaces: an org and its flagship
    # project may share a name or a website.
    for group, label in ((orgs, "org"), (entries, "entry")):
        seen_name: dict[str, str] = {}
        seen_url: dict[str, str] = {}
        seen_repo: dict[str, str] = {}
        for item in group:
            if item.name.lower() in seen_name:
                errors.append(f"{item.name}: duplicate {label} name")
            seen_name[item.name.lower()] = item.name
            url = str(item.url)
            if url in seen_url:
                errors.append(f"{item.name}: duplicate {label} url {url}")
            seen_url[url] = item.name
            repo = str(item.repository)
            if repo in seen_repo:
                errors.append(f"{item.name}: duplicate {label} repository {repo}")
            seen_repo[repo] = item.name

    if selected_entries:
        with ThreadPoolExecutor(max_workers=8) as pool:
            for result in pool.map(check_network, selected_entries):
                errors.extend(result)
    if selected_orgs:
        with ThreadPoolExecutor(max_workers=4) as pool:
            for result in pool.map(check_org_network, selected_orgs):
                errors.extend(result)

    if not entries:
        print("warning: no entries yet", file=sys.stderr)

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    if args.offline:
        checked = "skipped"
    elif args.only is None:
        checked = f"all {len(selected_entries)} entries, {len(selected_orgs)} orgs"
    else:
        checked = ", ".join(path.name for path in selected) or "none selected"
    print(
        f"ok: {len(entries)} entries across {len(categories)} categories, "
        f"{len(orgs)} orgs; network checks: {checked}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

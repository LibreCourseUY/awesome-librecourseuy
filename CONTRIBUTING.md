# Contributing to Awesome LibreCourseUY

Thank you for your interest in contributing! Adding a project to this list is
just one file and one pull request; you never edit the README.

Everything you see at the top level is **generated** from the JSON files in
[`entries/`](entries/): [`README.md`](README.md),
[`public/entries.json`](public/entries.json) (the machine-readable feed) and
[`schema.json`](schema.json). This repository is the single source of truth;
the generator is [`scripts/build.py`](scripts/build.py), and
[`README.template.md`](README.template.md) supplies the surrounding boilerplate.

**Do not edit generated files by hand.** CI regenerates them on merge to
`master` and overwrites any manual changes, so a pull request that touches
`README.md`, `public/entries.json` or `schema.json` is always wrong. Add or
change files in `entries/` instead (plus `categories.json`, `tags.json` or
`licenses.json` only when introducing a new category, tag or license).

## What listing means

This repository is a catalog of the ecosystem, not a registry of LibreCourseUY
projects. An entry here means the project meets the inclusion criteria below,
and nothing more: it does **not** make the project an official LibreCourseUY
project, and it does not mean LibreCourseUY maintains, endorses or speaks for
it. The organization's
[TRADEMARK.md](https://github.com/LibrecourseUY/.github/blob/master/TRADEMARK.md)
applies: do not present a listing as an endorsement or as official status.

Three different things can happen to a project, and none of them implies the
next.

| Act | What it means | How it shows |
|-----|---------------|--------------|
| **Listing** | The project meets the inclusion criteria and has an entry here. | A file in `entries/`; the feed carries `relationship: community`. |
| **Collaboration** | The project's maintainers welcome outside contributors. LibreCourseUY members contribute like anyone else, and the project's maintainers keep deciding what gets merged. | `open_to_contributions: true`, declared by the maintainers in the entry. |
| **Adoption** | LibreCourseUY takes responsibility for maintaining and governing the project. | The repository lives under the [LibreCourseUY organization](https://github.com/LibreCourseUY) and the feed derives `relationship: official`. |

Adoption is a transfer of the repository into the organization, agreed with
the project's maintainers and decided by the organization administrators, as
[GOVERNANCE.md](https://github.com/LibrecourseUY/.github/blob/master/GOVERNANCE.md)
describes. Nothing in this repository can grant it: entries cannot set
`relationship`, it is derived from the repository owner.

### Inclusion criteria

A project is listed when all of the following hold:

- It is built by Uruguayan developers: at least one maintainer is from Uruguay
  or based there. CI cannot check this, so say so in the pull request when it
  is not obvious; reviewers may ask.
- Its source is public under a license from [`licenses.json`](licenses.json):
  the licenses GitHub can identify that are OSI-approved or FSF-libre. CI
  verifies this for GitHub repositories; for other hosts, reviewers check the
  license file by hand.
- Its repository is not archived and its URL works. CI verifies both.
- It is a project in its own right: not a fork with no changes, a template, a
  tutorial or exercise repository, or a placeholder.
  [FastAPI Boilerplate](https://github.com/benavlabs/FastAPI-boilerplate) is an
  accepted exception to the template exclusion.
- It does not misrepresent its authorship or its official status.

Reviewers may decline an entry that passes CI but falls outside the list's
scope, as GOVERNANCE.md provides.

### Removal

An entry is removed, through a pull request like any other change, when the
project no longer meets the criteria:

- the repository is archived, made private or deleted, or no longer carries a
  license GitHub can identify as open source;
- the project URL fails the weekly check two weeks in a row;
- the maintainers ask for the entry to be removed;
- the entry turns out to misrepresent the project.

The [weekly workflow](.github/workflows/sweep.yml) re-checks every entry
against GitHub and the project URLs and opens an issue when something fails;
maintainers fix or remove the affected entries from there. Removal is not a
judgment on the project: anyone can propose the entry again once the criteria
hold.

## Before you start

Read and accept our community documents:

| Document | Description |
|----------|-------------|
| [CONTRIBUTING.md](https://github.com/LibrecourseUY/.github/blob/master/CONTRIBUTING.md) | How to contribute to our projects |
| [DCO](https://developercertificate.org/) | Developer Certificate of Origin (sign off with `git commit -s`) |
| [CODE_OF_CONDUCT.md](https://github.com/LibrecourseUY/.github/blob/master/CODE_OF_CONDUCT.md) | Community behavior expectations |

All commits must be **GPG-signed**. See the
[GPG Signature Guide](https://librecourse.uy/docs/gpg-signature/).

## Add a project

1. Fork and clone this repository.
2. Create a branch: `git checkout -b entry/your-project`.
3. Add one JSON file to `entries/`, named after your project slug
   (e.g. `entries/my-project.json`).
4. Validate locally. `--only` limits the network checks to your entry, which
   is also what CI does for a pull request:

   ```bash
   uv run python scripts/validate.py --only entries/my-project.json
   ```

   Without network access, run the schema and cross-file checks only:

   ```bash
   uv run python scripts/validate.py --offline
   ```

5. Optionally preview the generated files (this writes `README.md`,
   `public/entries.json` and `schema.json`, so it is a local preview only):

   ```bash
   uv run python scripts/build.py
   ```

   Do **not** commit its output; CI regenerates those files on merge. Discard
   the preview with `git checkout -- README.md public/entries.json schema.json`.

6. Commit, push and open a Pull Request.

## Entry format

```json
{
  "name": "My Project",
  "url": "https://my-project.example.com",
  "description": "One sentence describing what it does.",
  "category": "Web",
  "tags": ["astro", "open-data"],
  "language": ["Python", "TypeScript"],
  "maintainers": ["@your-handle"],
  "license": "MIT",
  "repository": "https://github.com/LibreCourseUY/my-project",
  "open_to_contributions": true
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `name` | yes | Display name. Must be unique. |
| `url` | no | Project or site URL (`http`/`https`). Defaults to `repository`. Must be unique. |
| `description` | yes | One sentence, no trailing period needed. |
| `category` | yes | One of the categories in [`categories.json`](categories.json). |
| `tags` | no | Free-form keywords. |
| `language` | no | Programming languages, as a list. |
| `maintainers` | no | GitHub handles, each starting with `@`. |
| `license` | yes | One of the SPDX identifiers in [`licenses.json`](licenses.json), exactly as GitHub detects it (e.g. `MIT`, or `GPL-3.0` rather than `GPL-3.0-or-later`). |
| `commercial` | no | `true` or `false`: whether the project is sold or otherwise monetized (paid product, ads, subscription...). Defaults to `false` (non-commercial). |
| `repository` | yes | Source repository URL (`http`/`https`). Must be unique. Only open source projects are listed. |
| `open_to_contributions` | no | `true` or `false`. Whether the project accepts outside contributions. If omitted it is unknown, never assumed, and left out of the feed. |

The feed also carries `relationship`, derived from `repository`: `official` for
repositories owned by the LibreCourseUY organization on GitHub, `community` for
everything else. Entries cannot set it, so listing a project never presents it
as an official LibreCourseUY project.

Editors get autocomplete and inline errors from the generated
[`schema.json`](schema.json): add this to the top of your entry if your editor
does not pick it up automatically:

```json
{ "$schema": "../schema.json", "name": "..." }
```

> `$schema` is not part of the entry schema and will be rejected by validation.
> Only include it while editing locally, or rely on your editor's JSON Schema
> mapping configured to `schema.json`.

## Org format

Open source organizations from the LCUY ecosystem live in [`orgs/`](orgs/) as their
own JSON files. They are listed above the projects in the README and feed.

```json
{
  "name": "My Org",
  "url": "https://my-org.example.com",
  "description": "One sentence about the org.",
  "tags": ["python"],
  "color": { "light": "#4f46e5", "dark": "#818cf8" },
  "repository": "https://github.com/my-org"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `name` | yes | Display name. Must be unique. |
| `url` | no | Website URL (`http`/`https`). Defaults to `repository`. Must be unique. |
| `description` | yes | One sentence. |
| `tags` | no | Free-form keywords from [`tags.json`](tags.json). |
| `color` | no | Card highlight colors for the site, taken from the org's own branding: `{"light": "#rrggbb", "dark": "#rrggbb"}`. |
| `repository` | yes | GitHub organization URL (e.g. `https://github.com/my-org`). Must be unique. |

The `relationship` rule from entries applies here too: the LibreCourseUY
organization is `official`, everything else is `community`, and orgs cannot
set it themselves. CI checks that the organization exists and is public.

## What CI checks

`scripts/validate.py` runs on every pull request and fails if, for any entry:

- a field is missing, empty, or of the wrong type;
- an unknown field is present (typos are caught, not ignored);
- a URL is not a valid `http`/`https` URL;
- the category is not listed in `categories.json`;
- a tag is not listed in `tags.json`;
- the license is not listed in `licenses.json`;
- the name, URL or repository duplicates another entry;
- a maintainer handle does not start with `@`.

Orgs are checked the same way, minus the entry-only fields: name, URL and
repository must be unique, tags must be known, and CI verifies the GitHub
organization exists and is public.

For the entries the pull request adds or changes, it also fails if:

- the project URL is not reachable (HTTP error, dead host, timeout);
- the repository is private, archived or does not exist, or GitHub cannot
  identify its license or detects a different one than declared (GitHub
  repositories are verified through the API).

These network checks are limited to the changed entries on purpose: a
third-party site that is down for a day must not block an unrelated pull
request. Every entry is re-checked by the
[weekly workflow](.github/workflows/sweep.yml) instead, which opens an issue
when something fails.

The network checks run against GitHub with the Actions `GITHUB_TOKEN`, so
public repositories are verified reliably. Locally, set `GITHUB_TOKEN` in your
environment for the same behaviour.

CI also renders the generated files from your entries and runs the generator
and validator self-checks (`scripts/test_build.py`, `scripts/test_validate.py`),
but never asks you to commit them: they are regenerated on merge to `master`,
so you never need to do it yourself.

## Adding a category, tag or license

Categories are defined in [`categories.json`](categories.json), in display
order, tags in [`tags.json`](tags.json) and licenses in
[`licenses.json`](licenses.json), alphabetically. All three are closed sets: an
unknown category, tag or license fails CI.

To add a category or license, edit the relevant file in the same pull request
and explain why the existing values do not fit. Tags are not extended for a
single project: pick from the existing [`tags.json`](tags.json), and request a
new tag only when several unrelated projects need it.

`licenses.json` lists every license GitHub can identify that the
[SPDX License List](https://spdx.org/licenses/) marks as OSI-approved or
FSF-libre. Only add a license that meets both conditions: projects under
licenses GitHub cannot identify, including source-available ones, are not
listed.

## Questions?

Open an Issue. All contributors were where you are now.

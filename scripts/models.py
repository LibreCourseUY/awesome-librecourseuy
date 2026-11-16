"""Pydantic models for awesome-librecourseuy entries. Single source of truth."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, HttpUrl, field_validator, model_validator

ROOT = Path(__file__).resolve().parent.parent
ENTRIES_DIR = ROOT / "entries"
ORGS_DIR = ROOT / "orgs"
CATEGORIES_FILE = ROOT / "categories.json"
TAGS_FILE = ROOT / "tags.json"
LICENSES_FILE = ROOT / "licenses.json"
ORG = "LibreCourseUY"

# Canonical spellings already used by the catalog. New language names remain
# allowed; this is normalization rather than a closed list of languages.
LANGUAGE_NAMES = {
    name.casefold(): name
    for name in (
        "Astro",
        "Batchfile",
        "C",
        "C#",
        "C++",
        "CSS",
        "GDScript",
        "Go",
        "HTML",
        "Java",
        "JavaScript",
        "Jupyter Notebook",
        "Kotlin",
        "Luau",
        "Makefile",
        "Pawn",
        "PHP",
        "Python",
        "React",
        "Rust",
        "Shell",
        "TypeScript",
        "Vue",
    )
}


def load_categories() -> list[str]:
    data = json.loads(CATEGORIES_FILE.read_text(encoding="utf-8"))
    return [c["name"] for c in data["categories"]]


def load_tags() -> set[str]:
    return set(json.loads(TAGS_FILE.read_text(encoding="utf-8"))["tags"])


def load_licenses() -> set[str]:
    return set(json.loads(LICENSES_FILE.read_text(encoding="utf-8"))["licenses"])


CATEGORIES = load_categories()
TAGS = load_tags()
LICENSES = load_licenses()


class Entry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    url: HttpUrl | None = None
    description: str
    category: str
    tags: list[str] = []
    language: list[str] = []
    maintainers: list[str] = []
    license: str
    commercial: bool = False
    repository: HttpUrl
    open_to_contributions: bool | None = None

    @field_validator("name", "description", "category")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty")
        return v.strip()

    @field_validator("category")
    @classmethod
    def _known_category(cls, v: str) -> str:
        if v not in CATEGORIES:
            raise ValueError(f"unknown category {v!r}; allowed: {', '.join(CATEGORIES)}")
        return v

    @field_validator("tags")
    @classmethod
    def _known_tags(cls, v: list[str]) -> list[str]:
        unknown = sorted({tag for tag in v if tag not in TAGS})
        if unknown:
            raise ValueError(
                f"unknown tags {', '.join(unknown)}; add them to tags.json"
            )
        return v

    @field_validator("language")
    @classmethod
    def _canonical_languages(cls, values: list[str]) -> list[str]:
        languages: list[str] = []
        for value in values:
            name = value.strip()
            if not name:
                raise ValueError("language must not be empty")
            canonical = LANGUAGE_NAMES.get(name.casefold(), name)
            if canonical not in languages:
                languages.append(canonical)
        return languages

    @field_validator("license")
    @classmethod
    def _known_license(cls, v: str) -> str:
        if v not in LICENSES:
            raise ValueError(f"unknown license {v!r}; use an identifier from licenses.json")
        return v

    @field_validator("maintainers")
    @classmethod
    def _at_handles(cls, v: list[str]) -> list[str]:
        for handle in v:
            if not handle.startswith("@"):
                raise ValueError(f"maintainer {handle!r} must start with '@'")
        return v

    @model_validator(mode="after")
    def _url_defaults_to_repository(self) -> Entry:
        if self.url is None:
            self.url = self.repository
        return self

    @property
    def relationship(self) -> Literal["official", "community"]:
        """Derived from the repository owner, never declared, so no entry can claim it."""
        owner = (self.repository.path or "/").split("/")[1]
        if self.repository.host == "github.com" and owner.lower() == ORG.lower():
            return "official"
        return "community"


def load_entry_files() -> dict[Path, Entry]:
    """Every entry keyed by its file, in file-name order."""
    entries: dict[Path, Entry] = {}
    for path in sorted(ENTRIES_DIR.glob("*.json")):
        try:
            entries[path] = Entry.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - surface file name in the error
            raise ValueError(f"{path.name}: {exc}") from exc
    return entries


def load_entries() -> list[Entry]:
    return list(load_entry_files().values())


class OrgColor(BaseModel):
    """Brand colors for the org card highlight, one per theme."""

    model_config = ConfigDict(extra="forbid")

    light: str
    dark: str

    @field_validator("light", "dark")
    @classmethod
    def _hex(cls, v: str) -> str:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
            raise ValueError("must be a #rrggbb hex color")
        return v


class Org(BaseModel):
    """An open source organization from the LCUY ecosystem, listed above projects."""

    model_config = ConfigDict(extra="forbid")

    name: str
    url: HttpUrl | None = None
    description: str
    tags: list[str] = []
    repository: HttpUrl
    color: OrgColor | None = None

    @field_validator("name", "description")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty")
        return v.strip()

    @field_validator("tags")
    @classmethod
    def _known_tags(cls, v: list[str]) -> list[str]:
        unknown = sorted({tag for tag in v if tag not in TAGS})
        if unknown:
            raise ValueError(f"unknown tags {', '.join(unknown)}; add them to tags.json")
        return v

    @field_validator("repository")
    @classmethod
    def _github_org(cls, v: HttpUrl) -> HttpUrl:
        parts = (v.path or "/").strip("/").split("/")
        if v.host != "github.com" or len(parts) != 1 or not parts[0]:
            raise ValueError("repository must be a GitHub organization URL")
        return v

    @model_validator(mode="after")
    def _url_defaults_to_repository(self) -> Org:
        if self.url is None:
            self.url = self.repository
        return self

    @property
    def relationship(self) -> Literal["official", "community"]:
        owner = (self.repository.path or "/").strip("/")
        if self.repository.host == "github.com" and owner.lower() == ORG.lower():
            return "official"
        return "community"


def load_org_files() -> dict[Path, Org]:
    orgs: dict[Path, Org] = {}
    for path in sorted(ORGS_DIR.glob("*.json")):
        try:
            orgs[path] = Org.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - surface file name in the error
            raise ValueError(f"{path.name}: {exc}") from exc
    return orgs


def load_orgs() -> list[Org]:
    return list(load_org_files().values())

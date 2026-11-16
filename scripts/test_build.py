"""Self-check for scripts/build.py rendering. Run: uv run python scripts/test_build.py"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from models import Entry, Org  # noqa: E402

SAMPLE = Entry(
    name="Sample",
    url="https://example.com",
    description="A sample project.",
    category="Web",
    language=["Python"],
    license="MIT",
    repository="https://github.com/LibreCourseUY/sample",
    maintainers=["@someone"],
)

SAMPLE_ORG = Org(
    name="Sample Org",
    description="A sample org.",
    repository="https://github.com/sample-org",
    color={"light": "#106654", "dark": "#5ec2af"},
)

COMMERCIAL = SAMPLE.model_copy(update={"commercial": True, "name": "Aaa Sample"})

OFFICIAL_ORG = Org(
    name="Zebra Org",
    description="An official org.",
    repository="https://github.com/LibreCourseUY",
)


def _self_check() -> None:
    from build import render_feed, render_orgs, render_projects, render_readme, render_schema

    line = render_projects([SAMPLE], ["Web", "APIs"])
    assert line.startswith("### Web\n"), line
    assert "- [Sample](https://example.com/): A sample project." in line, line
    assert "[@someone](https://github.com/someone)" in line, line
    assert "source" not in line, "no source/extra metadata in the line"
    assert "APIs" not in line, "empty categories must be omitted"

    mixed = render_projects([COMMERCIAL, SAMPLE], ["Web"])
    assert mixed.index("- [Sample]") < mixed.index("- [Aaa Sample]"), "non-commercial first"

    ordered = render_orgs([SAMPLE_ORG, OFFICIAL_ORG])
    assert ordered.index("Zebra Org") < ordered.index("Sample Org"), "official orgs first"

    readme = render_readme([SAMPLE], ["Web"], [SAMPLE_ORG])
    assert readme.count("<!-- PROJECTS:START -->") == 1
    assert readme.count("<!-- PROJECTS:END -->") == 1
    assert readme.count("<!-- ORGS:START -->") == 1
    assert "1 projects and counting" in readme
    assert "- [Sample Org](https://github.com/sample-org): A sample org." in readme
    assert readme.index("## Orgs") < readme.index("## Projects"), "orgs come first"
    assert readme.index("Sample Org") < readme.index("### Web"), "orgs before projects"
    assert "PROJECTS:START -->\n### Web" in readme, "list must be injected at the marker"

    braces = SAMPLE.model_copy(update={"description": "Renders {name}, {} and {{ var }}."})
    assert "Renders {name}, {} and {{ var }}." in render_readme([braces], ["Web"], []), "verbatim"

    assert "MIT" in render_schema()["properties"]["license"]["enum"], "license enum"

    feed = json.loads(render_feed([SAMPLE], ["Web"], [SAMPLE_ORG]))
    assert "open_to_contributions" not in feed["entries"][0], "never assumed"
    assert feed["entries"][0]["relationship"] == "official", "repositories under the org"
    assert feed["entries"][0]["open_source"] is True, "listing requires public OSS"
    assert feed["orgs"][0]["name"] == "Sample Org"
    assert feed["orgs"][0]["relationship"] == "community"
    assert feed["orgs"][0]["color"] == {"light": "#106654", "dark": "#5ec2af"}, "color in feed"
    assert str(SAMPLE_ORG.url) == "https://github.com/sample-org", "org url defaults to repository"

    try:
        Org(
            name="Bad Color",
            description="d",
            repository="https://github.com/bad-color",
            color={"light": "red", "dark": "#000000"},
        )
    except ValueError:
        pass
    else:
        raise AssertionError("non-hex org color accepted")

    bare = Entry(
        name="Bare",
        description="No url of its own.",
        category="Web",
        license="MIT",
        repository="https://github.com/someone/bare",
    )
    assert str(bare.url) == "https://github.com/someone/bare", "url defaults to repository"
    community = json.loads(render_feed([bare], ["Web"], []))["entries"][0]
    assert community["relationship"] == "community", "repositories elsewhere"

    normalized = Entry.model_validate(
        {
            **SAMPLE.model_dump(),
            "language": [
                " rust ", "Rust", "Typescript", "TYPESCRIPT", "Javascript", "PYTHON", "Zig"
            ],
        }
    )
    expected_languages = ["Rust", "TypeScript", "JavaScript", "Python", "Zig"]
    assert normalized.language == expected_languages, "canonical spelling and unique names in order"
    normalized_feed = json.loads(render_feed([normalized], ["Web"], []))
    assert normalized_feed["entries"][0]["language"] == expected_languages, "normalized feed"
    assert not bare.language, "omitted language remains unspecified"
    for blank in ("", "   "):
        try:
            Entry.model_validate({**SAMPLE.model_dump(), "language": [blank]})
        except ValueError:
            pass
        else:
            raise AssertionError("empty language accepted")

    print("build self-check ok")


if __name__ == "__main__":
    _self_check()

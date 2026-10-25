"""Changelog section extraction from real consumer changelog excerpts."""

from pathlib import Path
from textwrap import dedent

import pytest

lazy from release_creator.notes.section import release_section

_CHANGELOGS = Path(__file__).parent / "changelogs"


@pytest.mark.parametrize(
    ("name", "tag", "package", "lines"),
    [
        pytest.param("filelock.rst", "4.2.3", None, (20, 29), id="rst-overline"),
        pytest.param("pipx.rst", "1.18.4", None, (11, 18), id="rst-linked-heading"),
        pytest.param("pyproject-api.rst", "1.12.0", None, (12, 27), id="rst-v-heading"),
        pytest.param("pyproject-api.rst", "v1.11.7", None, (33, 39), id="rst-last-section"),
        pytest.param("pytest-env.md", "1.8.1", None, (8, 14), id="markdown-towncrier"),
        pytest.param("jetbrains-fish.md", "v0.1.9", None, (16, 22), id="keep-a-changelog-references"),
        pytest.param("pyvenvmanage.md", "2.4.5", None, (21, 27), id="keep-a-changelog-trailing-anchor"),
        pytest.param("toml-fmt.md", "pyproject-fmt/2.30.2", "pyproject-fmt", (17, 25), id="package-section"),
        pytest.param("toml-fmt.md", "tox-toml-fmt/1.11.1", "tox-toml-fmt", (30, 38), id="package-section-end"),
    ],
)
def test_release_section_prints_body_without_heading(
    name: str, tag: str, package: str | None, lines: tuple[int, int]
) -> None:
    source = (_CHANGELOGS / name).read_text(encoding="utf-8")
    expected = "".join(source.splitlines(keepends=True)[slice(*lines)])

    assert release_section(source, tag, package, rst=name.endswith(".rst")) == expected


@pytest.mark.parametrize(
    ("name", "tag"),
    [
        pytest.param("filelock.rst", "4.2.4", id="rst"),
        pytest.param("jetbrains-fish.md", "0.1.10", id="markdown"),
    ],
)
def test_release_section_empty_release(name: str, tag: str) -> None:
    source = (_CHANGELOGS / name).read_text(encoding="utf-8")

    assert not release_section(source, tag, rst=name.endswith(".rst"))


def test_release_section_ignores_headings_in_code_fences() -> None:
    source = dedent("""\
        ## 1.2.3 (2026-10-18)

        - Run it:

          ```sh
          ## 1.2.2 (2026-10-17)
          ```

        ## 1.2.2 (2026-10-17)
        """)

    assert release_section(source, "1.2.3") == "- Run it:\n\n  ```sh\n  ## 1.2.2 (2026-10-17)\n  ```\n"


@pytest.mark.parametrize(
    "fake",
    [
        pytest.param(" 1.2.2 (2026-10-17)\n-------------------\n", id="indented-without-overline"),
        pytest.param("1.2.2 (2026-10-17)\n----\n", id="short-underline"),
    ],
)
def test_release_section_ignores_rst_lines_that_are_not_headings(fake: str) -> None:
    source = f"1.2.3 (2026-10-18)\n==================\n\n- Fix it.\n\n{fake}"

    assert release_section(source, "1.2.3", rst=True) == f"- Fix it.\n\n{fake}"


@pytest.mark.parametrize(
    ("source", "tag", "package", "message"),
    [
        pytest.param("## 1.2.2 (2026-10-17)\n", "1.2.3", None, "for 1.2.3, found 0", id="missing"),
        pytest.param("## 1.2.3\n\n## v1.2.3\n", "1.2.3", None, "for 1.2.3, found 2", id="duplicate"),
        pytest.param("## a\n\n### 1.2.3\n", "b/1.2.3", "b", "for package b, found 0", id="missing-package"),
        pytest.param("## a\n\n### 1.2.3\n", "a/1.2.3", "b", "a/1.2.3 does not belong to package b", id="other-package"),
    ],
)
def test_release_section_rejects_ambiguous_input(source: str, tag: str, package: str | None, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        release_section(source, tag, package)

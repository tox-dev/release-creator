"""New Contributors subsection tests for package sections of a shared Markdown changelog."""

from __future__ import annotations

import sys
from textwrap import dedent
from typing import TYPE_CHECKING, Final

import pytest

from release_creator.cli import main
from release_creator.contributors.section import add_new_contributors
from release_creator.notes.render import ReleaseContext, render_markdown

if TYPE_CHECKING:
    from pathlib import Path

    from tests.release_creator.contributors.conftest import GitHub

_CHANGELOG: Final = dedent("""\
    # Changelog

    ## pyproject-fmt

    ### 1.1.0 (2026-10-21)

    <a name="release-pyproject-fmt-1-1-0-added"></a>

    #### Added

    - Add a setting ([#42](https://github.com/tox-dev/toml-fmt/pull/42)) by [@alice](https://github.com/alice).

    ### 1.0.0 (2026-01-01)

    <a name="release-pyproject-fmt-1-0-0-fixed"></a>

    #### Fixed

    - Fix an error ([#40](https://github.com/tox-dev/toml-fmt/pull/40)) by [@dave](https://github.com/dave).

    ## tox-toml-fmt

    ### 1.1.0 (2026-10-20)

    <a name="release-tox-toml-fmt-1-1-0-fixed"></a>

    #### Fixed

    - Fix a crash ([#43](https://github.com/tox-dev/toml-fmt/pull/43)) by [@carol](https://github.com/carol).
    """)
_PULLS: Final = {
    "40": ("dave", "User", "2026-01-01T10:00:00Z"),
    "42": ("alice", "User", "2026-10-20T10:00:00Z"),
    "43": ("carol", "User", "2026-10-19T10:00:00Z"),
}
_SUBSECTION: Final = (
    '<a name="release-pyproject-fmt-1-1-0-new-contributors"></a>\n\n'
    "#### New Contributors\n\n"
    "- [@alice](https://github.com/alice) made their first contribution in "
    "[#42](https://github.com/tox-dev/toml-fmt/pull/42)\n\n"
)


@pytest.fixture
def changelog(tmp_path: Path) -> Path:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(_CHANGELOG, encoding="utf-8")
    return path


def test_add_new_contributors_package_targets_package_version(changelog: Path, github: GitHub) -> None:
    github(_PULLS, set())

    add_new_contributors(changelog, "1.1.0", "tox-dev/toml-fmt", "pyproject-fmt")

    assert changelog.read_text(encoding="utf-8") == _CHANGELOG.replace(
        "### 1.0.0 (2026-01-01)\n", f"{_SUBSECTION}### 1.0.0 (2026-01-01)\n", 1
    )


def test_add_new_contributors_package_queries_only_its_section(changelog: Path, github: GitHub) -> None:
    run = github(_PULLS, set())

    add_new_contributors(changelog, "1.1.0", "tox-dev/toml-fmt", "pyproject-fmt")

    assert "pullRequest(number: 42)" in run.call_args_list[0].kwargs["input"]
    assert all("number: 43" not in call.kwargs["input"] for call in run.call_args_list)


def test_add_new_contributors_package_renders_in_notes(changelog: Path, github: GitHub) -> None:
    github(_PULLS, set())
    add_new_contributors(changelog, "1.1.0", "tox-dev/toml-fmt", "pyproject-fmt")
    context = ReleaseContext(tag="pyproject-fmt/1.1.0", repository="tox-dev/toml-fmt", package="pyproject-fmt")

    body = render_markdown(changelog.read_text(encoding="utf-8"), context)

    assert body.endswith(
        '<a name="release-pyproject-fmt-1-1-0-new-contributors"></a>\n\n### New Contributors\n\n'
        "- [@alice](https://github.com/alice) made their first contribution in "
        "[#42](https://github.com/tox-dev/toml-fmt/pull/42)\n\n"
        "[Full Changelog](https://github.com/tox-dev/toml-fmt/commits/pyproject-fmt/1.1.0)\n"
    )


def _run_cli(monkeypatch: pytest.MonkeyPatch, changelog: Path, package: str) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "contributors",
            "--changelog",
            str(changelog),
            "--version",
            "1.1.0",
            "--repository",
            "tox-dev/toml-fmt",
            "--package",
            package,
        ],
    )
    main()


def test_contributors_cli_package_edits_package_section(
    changelog: Path, github: GitHub, monkeypatch: pytest.MonkeyPatch
) -> None:
    github(_PULLS, set())

    _run_cli(monkeypatch, changelog, "pyproject-fmt")

    assert changelog.read_text(encoding="utf-8") == _CHANGELOG.replace(
        "### 1.0.0 (2026-01-01)\n", f"{_SUBSECTION}### 1.0.0 (2026-01-01)\n", 1
    )

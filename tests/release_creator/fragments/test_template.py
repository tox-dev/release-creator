"""Towncrier template integration tests."""

from __future__ import annotations

import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Exercise the installed Towncrier command.
import sys
from textwrap import dedent
lazy from pathlib import Path

import pytest

from release_creator.notes.render import ReleaseContext, render_markdown, render_rst


def test_markdown_template_keeps_numbered_and_named_pull_requests(tmp_path: Path) -> None:
    (tmp_path / "changelog.d").mkdir()
    (tmp_path / "changelog.d" / "123.bugfix.md").write_text("Fix a numbered bug.\n")
    (tmp_path / "changelog.d" / "+named.bugfix.md").write_text(
        "Fix a named bug ([#124](https://github.com/tox-dev/example/pull/124)) by [@alice](https://github.com/alice).\n"
    )
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n<!-- towncrier release notes start -->\n")
    (tmp_path / "pyproject.toml").write_text(
        dedent("""\
        [tool.towncrier]
        name = "example"
        directory = "changelog.d"
        filename = "CHANGELOG.md"
        template = "release_creator.fragments:template.jinja2"
        title_format = false
        issue_format = "[#{issue}](https://github.com/tox-dev/example/pull/{issue})"
        type = [
          { directory = "bugfix", name = "Fixed", showcontent = true },
        ]
        """)
    )

    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # Fixed command and temporary checkout.
        [str(Path(sys.executable).with_name("towncrier")), "build", "--yes", "--version", "1.2.3"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    assert render_markdown(
        (tmp_path / "CHANGELOG.md").read_text(),
        ReleaseContext(tag="1.2.3", repository="tox-dev/example"),
    ) == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n'
        "- Fix a numbered bug. ([#123](https://github.com/tox-dev/example/pull/123))\n"
        "- Fix a named bug ([#124](https://github.com/tox-dev/example/pull/124)) by @alice.\n\n"
        "**Full Changelog**: https://github.com/tox-dev/example/commits/1.2.3\n"
    )


@pytest.mark.parametrize(
    ("underlines", "expected_category"),
    [
        pytest.param("", "Fixed\n-----", id="default"),
        pytest.param('underlines = ["*", "=", "-"]', "Fixed\n=====", id="overline"),
        pytest.param('underlines = ["-", "~"]', "Fixed\n~~~~~", id="dash"),
    ],
)
def test_rst_template_renders_notes_with_stable_anchors(
    underlines: str, expected_category: str, tmp_path: Path
) -> None:
    (tmp_path / "changelog.d").mkdir()
    (tmp_path / "changelog.d" / "1.bugfix.rst").write_text("Fix the loader.\n")
    old_release = (
        "\n********************\n 0.9.0 (2026-01-01)\n********************\n"
        if underlines.startswith('underlines = ["*"')
        else "\n0.9.0 (2026-01-01)\n==================\n"
    )
    (tmp_path / "changelog.rst").write_text("Changelog\n=========\n\n.. towncrier release notes start\n" + old_release)
    (tmp_path / "pyproject.toml").write_text(
        dedent("""\
        [tool.towncrier]
        name = "example"
        directory = "changelog.d"
        filename = "changelog.rst"
        template = "release_creator.fragments:template.rst.jinja2"
        title_format = false
            issue_format = ":pr:`{issue}`"
        @UNDERLINES@
        type = [
          { directory = "bugfix", name = "Fixed", showcontent = true },
        ]
        """).replace("@UNDERLINES@", underlines)
    )

    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # Fixed command and temporary checkout.
        [str(Path(sys.executable).with_name("towncrier")), "build", "--yes", "--version", "1.2.3"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    changelog = (tmp_path / "changelog.rst").read_text()
    assert expected_category in changelog
    assert render_rst(
        changelog,
        ReleaseContext(tag="1.2.3", repository="tox-dev/example"),
    ) == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n'
        "- Fix the loader. ([#1](https://github.com/tox-dev/example/pull/1))\n\n"
        "**Full Changelog**: https://github.com/tox-dev/example/commits/1.2.3\n"
    )

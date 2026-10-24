"""Towncrier template integration tests."""

from __future__ import annotations

import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Exercise the installed Towncrier command.
import sys
from textwrap import dedent
lazy from pathlib import Path

import pytest

from release_creator.fragments.links import add_pull_request_links
from release_creator.fragments.pull_requests import PullRequest, PullRequestAuthor
from release_creator.notes.render import ReleaseContext, render_markdown, render_rst


@pytest.mark.parametrize(
    ("number", "issue_suffix"),
    [
        pytest.param("123", "", id="same-pr-and-issue"),
        pytest.param("125", " ([#123](https://github.com/tox-dev/example/issues/123))", id="separate-pr-and-issue"),
    ],
)
def test_markdown_template_keeps_numbered_and_named_pull_requests(
    tmp_path: Path, number: str, issue_suffix: str
) -> None:
    (tmp_path / "changelog.d").mkdir()
    (tmp_path / "changelog.d" / "123.bugfix.md").write_text("Fix a numbered bug.\n")
    (tmp_path / "changelog.d" / "+named.bugfix.md").write_text("Fix a named bug.\n")
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n<!-- towncrier release notes start -->\n")
    (tmp_path / "pyproject.toml").write_text(
        dedent("""\
        [tool.towncrier]
        name = "example"
        directory = "changelog.d"
        filename = "CHANGELOG.md"
        template = "release_creator.fragments:template.jinja2"
        title_format = false
        issue_format = "[#{issue}](https://github.com/tox-dev/example/issues/{issue})"
        type = [
          { directory = "bugfix", name = "Fixed", showcontent = true },
        ]
        """)
    )
    add_pull_request_links(
        tmp_path / "changelog.d",
        "tox-dev/example",
        {
            "+named.bugfix.md": PullRequest(number="124", author=PullRequestAuthor(handle="alice", is_bot=False)),
            "123.bugfix.md": PullRequest(number=number, author=PullRequestAuthor(handle="alice", is_bot=False)),
        },
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
        f"- Fix a numbered bug ([#{number}](https://github.com/tox-dev/example/pull/{number})) "
        f"by @alice.{issue_suffix}\n"
        "- Fix a named bug ([#124](https://github.com/tox-dev/example/pull/124)) by @alice.\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


def test_markdown_template_links_two_fragments_from_one_pull_request(tmp_path: Path) -> None:
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    (directory / "+first.feature.md").write_text("Add an option by [@alice](https://github.com/alice).\n")
    (directory / "+second.bugfix.md").write_text("Fix a fallback by [@alice](https://github.com/alice).\n")
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n<!-- towncrier release notes start -->\n")
    (tmp_path / "pyproject.toml").write_text(
        dedent("""\
        [tool.towncrier]
        name = "example"
        directory = "changelog.d"
        filename = "CHANGELOG.md"
        template = "release_creator.fragments:template.jinja2"
        title_format = false
        type = [
          { directory = "feature", name = "Added", showcontent = true },
          { directory = "bugfix", name = "Fixed", showcontent = true },
        ]
        """)
    )
    add_pull_request_links(
        directory,
        "tox-dev/example",
        {
            name: PullRequest(number="42", author=PullRequestAuthor(handle="alice", is_bot=False))
            for name in ("+first.feature.md", "+second.bugfix.md")
        },
    )

    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # Fixed command and temporary checkout.
        [str(Path(sys.executable).with_name("towncrier")), "build", "--yes", "--version", "1.2.3"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    notes = render_markdown(
        changelog.read_text(),
        ReleaseContext(tag="1.2.3", repository="tox-dev/example"),
        "* Add an option by @alice in https://github.com/tox-dev/example/pull/42\n",
    )
    assert "Add an option by @alice ([#42](https://github.com/tox-dev/example/pull/42))." in notes
    assert "Fix a fallback by @alice ([#42](https://github.com/tox-dev/example/pull/42))." in notes


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(("md", "template.jinja2", "#{issue}", "pull/123"), id="markdown"),
        pytest.param(("rst", "template.rst.jinja2", ":pr:`{issue}`", ":pr:`123`"), id="rst"),
    ],
)
@pytest.mark.parametrize("mention", [pytest.param("", id="plain"), pytest.param(" in pypa/pip#12", id="other-repo")])
def test_template_does_not_confuse_short_issue_with_longer_pull_request(
    tmp_path: Path, case: tuple[str, str, str, str], mention: str
) -> None:
    extension, template, issue_format, pull_link = case
    (tmp_path / "changelog.d").mkdir()
    fragment = tmp_path / "changelog.d" / f"12.bugfix.{extension}"
    fragment.write_text(f"Fix a numbered bug{mention}.\n")
    changelog = tmp_path / f"CHANGELOG.{extension}"
    changelog.write_text("Changelog\n=========\n" if extension == "rst" else "# Changelog\n")
    (tmp_path / "pyproject.toml").write_text(
        dedent(f"""\
        [tool.towncrier]
        name = "example"
        directory = "changelog.d"
        filename = "{changelog.name}"
        template = "release_creator.fragments:{template}"
        title_format = false
        issue_format = "{issue_format}"
        type = [{{ directory = "bugfix", name = "Fixed", showcontent = true }}]
        """)
    )
    add_pull_request_links(
        tmp_path / "changelog.d",
        "tox-dev/example",
        {fragment.name: PullRequest(number="123", author=PullRequestAuthor(handle="alice", is_bot=False))},
    )

    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # Fixed command and temporary checkout.
        [str(Path(sys.executable).with_name("towncrier")), "build", "--yes", "--version", "1.2.3"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    assert pull_link in changelog.read_text()
    assert f"({issue_format.format(issue='12')})" in changelog.read_text()


def _build_rst_fragment(tmp_path: Path, source: str, underlines: str = "", filename: str = "1.bugfix.rst") -> str:
    (tmp_path / "changelog.d").mkdir()
    (tmp_path / "changelog.d" / filename).write_text(source)
    old_release = (
        "\n********************\n 0.9.0 (2026-01-01)\n********************\n"
        if underlines.startswith('underlines = ["*"')
        else "\n0.9.0 (2026-01-01)\n==================\n"
    )
    (tmp_path / "changelog.rst").write_text(f"Changelog\n=========\n\n.. towncrier release notes start\n{old_release}")
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
    add_pull_request_links(
        tmp_path / "changelog.d",
        "tox-dev/example",
        {filename: PullRequest(number="2", author=PullRequestAuthor(handle="alice", is_bot=False))},
    )

    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # Fixed command and temporary checkout.
        [str(Path(sys.executable).with_name("towncrier")), "build", "--yes", "--version", "1.2.3"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    return (tmp_path / "changelog.rst").read_text()


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
    changelog = _build_rst_fragment(tmp_path, "Fix the loader.\n", underlines)
    assert expected_category in changelog
    assert render_rst(
        changelog,
        ReleaseContext(tag="1.2.3", repository="tox-dev/example"),
    ) == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n'
        "- Fix the loader ([#2](https://github.com/tox-dev/example/pull/2)) by @alice. "
        "([#1](https://github.com/tox-dev/example/pull/1))\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


def test_rst_template_renders_literal_marker_credit(tmp_path: Path) -> None:
    changelog = _build_rst_fragment(tmp_path, "Fix the loader::\n\n  code output\n", filename="+literal.bugfix.rst")

    notes = render_rst(
        changelog,
        ReleaseContext(tag="1.2.3", repository="tox-dev/example"),
        "* Fix the loader by @alice in https://github.com/tox-dev/example/pull/2\n",
    )

    assert notes == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n'
        "- Fix the loader ([#2](https://github.com/tox-dev/example/pull/2)) by @alice:\n\n"
        "  ```\n  code output\n  ```\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


def test_rst_template_preserves_configured_category_style(tmp_path: Path) -> None:
    (tmp_path / "changelog.d").mkdir()
    (tmp_path / "changelog.d" / "1.change.rst").write_text("Change a setting.\n")
    (tmp_path / "changelog.rst").write_text("Changelog\n=========\n\n.. towncrier release notes start\n")
    (tmp_path / "pyproject.toml").write_text(
        dedent("""\
        [tool.towncrier]
        name = "example"
        directory = "changelog.d"
        filename = "changelog.rst"
        template = "release_creator.fragments:template.rst.jinja2"
        title_format = false
        underlines = ["*", "=", "-"]
        type = [{ directory = "change", name = "Changes", showcontent = true }]
        """)
    )

    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # Fixed Towncrier fixture.
        [str(Path(sys.executable).with_name("towncrier")), "build", "--yes", "--version", "1.2.3"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    assert "Changes\n=======" in (tmp_path / "changelog.rst").read_text()

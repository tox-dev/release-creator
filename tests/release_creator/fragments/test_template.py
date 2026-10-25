"""Towncrier template integration tests."""

from __future__ import annotations

import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Exercise the installed Towncrier command.
import sys
from textwrap import dedent
lazy from pathlib import Path

import pytest

from release_creator.fragments.links import add_pull_request_links
from release_creator.fragments.pull_requests import PullRequest, PullRequestAuthor, PullRequestCredit
from release_creator.notes.render import ReleaseContext, render_markdown, render_rst


def _alice_pull(number: str) -> PullRequest:
    return PullRequest(
        number=number,
        author=PullRequestAuthor(handle="alice", is_bot=False),
        credits=(PullRequestCredit(name="alice", linked=True),),
    )


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
    changelog = _build_markdown_fragments(
        tmp_path,
        {"123.bugfix.md": "Fix a numbered bug.\n", "+named.bugfix.md": "Fix a named bug.\n"},
        {
            "+named.bugfix.md": _alice_pull("124"),
            "123.bugfix.md": _alice_pull(number),
        },
        issue_format="[#{issue}](https://github.com/tox-dev/example/issues/{issue})",
    )

    assert render_markdown(
        changelog,
        ReleaseContext(tag="1.2.3", repository="tox-dev/example"),
    ) == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n'
        f"- Fix a numbered bug ([#{number}](https://github.com/tox-dev/example/pull/{number})) "
        f"by [@alice](https://github.com/alice).{issue_suffix}\n"
        "- Fix a named bug ([#124](https://github.com/tox-dev/example/pull/124)) "
        "by [@alice](https://github.com/alice).\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


def test_markdown_template_links_two_fragments_from_one_pull_request(tmp_path: Path) -> None:
    changelog = _build_markdown_fragments(
        tmp_path,
        {
            "+first.feature.md": "Add an option by [@alice](https://github.com/alice).\n",
            "+second.bugfix.md": "Fix a fallback by [@alice](https://github.com/alice).\n",
        },
        {name: _alice_pull("42") for name in ("+first.feature.md", "+second.bugfix.md")},
        categories=("feature", "bugfix"),
    )

    notes = render_markdown(
        changelog,
        ReleaseContext(tag="1.2.3", repository="tox-dev/example"),
    )
    assert (
        "Add an option by [@alice](https://github.com/alice) ([#42](https://github.com/tox-dev/example/pull/42))."
    ) in notes
    assert (
        "Fix a fallback by [@alice](https://github.com/alice) ([#42](https://github.com/tox-dev/example/pull/42))."
    ) in notes


@pytest.mark.parametrize(
    ("source", "entry"),
    [
        pytest.param(
            "First.\n\nSecond.\n",
            "- First.\n\n  Second ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@alice](https://github.com/alice).",
            id="two-paragraphs",
        ),
        pytest.param(
            "First.\n\n```python\nprint(1)\n```\n",
            "- First ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@alice](https://github.com/alice).\n\n  ```python\n  print(1)\n  ```",
            id="code-block",
        ),
    ],
)
def test_markdown_template_preserves_prose_continuations(tmp_path: Path, source: str, entry: str) -> None:
    changelog = _build_markdown_fragments(
        tmp_path,
        {"+change.bugfix.md": source},
        {"+change.bugfix.md": _alice_pull("42")},
    )

    notes = render_markdown(
        changelog,
        ReleaseContext(tag="1.2.3", repository="tox-dev/example"),
    )
    assert notes == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n'
        f"{entry}\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


@pytest.mark.parametrize(
    ("source", "error"),
    [
        pytest.param(
            "Add <code>by [@mallory](https://github.com/mallory).\n",
            "unclosed HTML literal element",
            id="inline-opening",
        ),
        pytest.param("Add support.\n\n<pre>hidden\n", "unclosed HTML literal element", id="block-opening"),
        pytest.param("Add support.\n\n<code>\nby someone\n", "unclosed HTML literal element", id="block-lines"),
        pytest.param(
            "Add support.\n\n<pre/>\n",
            "self-closing HTML literal elements are unsupported",
            id="self-closing-block",
        ),
        pytest.param("Add support.\n\n</kbd>\n", "mismatched HTML literal elements", id="block-closing"),
        pytest.param("Add support </kbd>.\n", "mismatched HTML literal elements", id="inline-closing"),
        pytest.param(
            "Add support.\n\n<code><kbd>sample</code></kbd>\n",
            "mismatched HTML literal elements",
            id="crossed-block-tags",
        ),
        pytest.param("Add support.\n\n<div><!--\n\nby someone\n", "incomplete HTML markup", id="open-comment"),
        pytest.param("Add support.\n\n<!--\n", "incomplete HTML markup", id="trailing-comment"),
        pytest.param("Add <details>support</details>.\n", "collapsible HTML sections", id="inline-details"),
        pytest.param("Add support.\n\n<summary>x</summary>\n", "collapsible HTML sections", id="block-summary"),
    ],
)
def test_markdown_template_rejects_malformed_literal_before_build(tmp_path: Path, source: str, error: str) -> None:

    with pytest.raises(ValueError, match=error):
        _build_markdown_fragments(
            tmp_path,
            {"+change.bugfix.md": source},
            {"+change.bugfix.md": _alice_pull("42")},
        )

    assert (tmp_path / "changelog.d" / "+change.bugfix.md").read_text() == source


def test_markdown_template_preserves_balanced_literal_block(tmp_path: Path) -> None:
    changelog = _build_markdown_fragments(
        tmp_path,
        {"+change.bugfix.md": "Add support.\n\n<pre>sample</pre>\n"},
        {"+change.bugfix.md": _alice_pull("42")},
    )

    assert render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example")) == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n'
        "- Add support ([#42](https://github.com/tox-dev/example/pull/42)) "
        "by [@alice](https://github.com/alice).\n\n"
        "  <pre>sample</pre>\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


def _build_markdown_fragments(
    tmp_path: Path,
    sources: dict[str, str],
    pull_requests: dict[str, PullRequest],
    *,
    categories: tuple[str, ...] = ("bugfix",),
    issue_format: str | None = None,
) -> str:
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    for name, source in sources.items():
        (directory / name).write_text(source)
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n<!-- towncrier release notes start -->\n")
    category_names = {"feature": "Added", "bugfix": "Fixed"}
    types = "\n".join(
        f'  {{ directory = "{category}", name = "{category_names[category]}", showcontent = true }},'
        for category in categories
    )
    issue_line = f"issue_format = {issue_format!r}\n" if issue_format is not None else ""
    (tmp_path / "pyproject.toml").write_text(
        '[tool.towncrier]\nname = "example"\ndirectory = "changelog.d"\nfilename = "CHANGELOG.md"\n'
        'template = "release_creator.fragments:template.jinja2"\ntitle_format = false\n'
        f"{issue_line}type = [\n{types}\n]\n"
    )
    add_pull_request_links(directory, "tox-dev/example", pull_requests)
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # Fixed command and temporary checkout.
        [str(Path(sys.executable).with_name("towncrier")), "build", "--yes", "--version", "1.2.3"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    return changelog.read_text()


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
        {fragment.name: _alice_pull("123")},
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
        {filename: _alice_pull("2")},
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
    )

    assert notes == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n'
        "- Fix the loader ([#2](https://github.com/tox-dev/example/pull/2)) by @alice:\n\n"
        "  ```\n  code output\n  ```\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


def test_rst_template_preserves_two_paragraphs(tmp_path: Path) -> None:
    changelog = _build_rst_fragment(tmp_path, "First.\n\nSecond.\n", filename="+paragraphs.bugfix.rst")

    notes = render_rst(
        changelog,
        ReleaseContext(tag="1.2.3", repository="tox-dev/example"),
    )

    assert notes == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n'
        "- First. Second ([#2](https://github.com/tox-dev/example/pull/2)) by @alice.\n\n"
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

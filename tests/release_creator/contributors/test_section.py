"""New Contributors subsection tests."""

from __future__ import annotations

import json
import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Model the GitHub CLI boundary.
import sys
from textwrap import dedent
from typing import TYPE_CHECKING, Final
from unittest.mock import create_autospec

import pytest

from release_creator import process
from release_creator.cli import main
from release_creator.contributors.section import add_new_contributors
from release_creator.notes.render import ReleaseContext, render_markdown, render_rst

if TYPE_CHECKING:
    from pathlib import Path

    from tests.release_creator.contributors.conftest import GitHub

_MARKDOWN: Final = dedent("""\
    # Changelog

    <!-- towncrier release notes start -->

    <a name="release-1-2-3"></a>

    ## 1.2.3 (2026-10-25)

    <a name="release-1-2-3-added"></a>

    ### Added

    - Add a cache ([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice) and [@bob](https://github.com/bob).
    - Add a flag ([#43](https://github.com/tox-dev/example/pull/43)) by [@carol](https://github.com/carol).

    <a name="release-1-2-2"></a>

    ## 1.2.2 (2026-10-01)

    <a name="release-1-2-2-fixed"></a>

    ### Fixed

    - Fix a bug ([#40](https://github.com/tox-dev/example/pull/40)) by [@alice](https://github.com/alice).
    """)
_RST: Final = dedent("""\
    Changelog
    =========

    .. towncrier release notes start

    .. _release-1-2-3:

    1.2.3 (2026-10-25)
    ==================

    .. _release-1-2-3-added:

    Added
    -----

    - Add a cache (:pr:`42`) by :user:`alice` and :user:`bob`.
    - Add a flag (:pr:`43`) by :user:`carol`.

    .. _release-1-2-2:

    1.2.2 (2026-10-01)
    ==================

    .. _release-1-2-2-fixed:

    Fixed
    -----

    - Fix a bug (:pr:`40`) by :user:`alice`.
    """)
_PULLS: Final = {"42": ("alice", "User", "2026-10-20T10:00:00Z"), "43": ("carol", "User", "2026-10-21T10:00:00Z")}


def _write(tmp_path: Path, extension: str) -> Path:
    changelog = tmp_path / f"CHANGELOG.{extension}"
    changelog.write_text(_MARKDOWN if extension == "md" else _RST, encoding="utf-8")
    return changelog


def test_add_new_contributors_markdown(tmp_path: Path, github: GitHub) -> None:
    github(_PULLS, {"carol"})
    changelog = _write(tmp_path, "md")

    add_new_contributors(changelog, "1.2.3", "tox-dev/example")

    assert changelog.read_text() == _MARKDOWN.replace(
        "by [@carol](https://github.com/carol).\n\n",
        "by [@carol](https://github.com/carol).\n\n"
        '<a name="release-1-2-3-new-contributors"></a>\n\n'
        "### New Contributors\n\n"
        "- [@alice](https://github.com/alice) made their first contribution in "
        "[#42](https://github.com/tox-dev/example/pull/42)\n\n",
    )


def test_add_new_contributors_rst(tmp_path: Path, github: GitHub) -> None:
    github(_PULLS, {"carol"})
    changelog = _write(tmp_path, "rst")

    add_new_contributors(changelog, "1.2.3", "tox-dev/example")

    assert changelog.read_text() == _RST.replace(
        "by :user:`carol`.\n\n",
        "by :user:`carol`.\n\n"
        ".. _release-1-2-3-new-contributors:\n\n"
        "New Contributors\n"
        "----------------\n\n"
        "- :user:`alice` made their first contribution in :pr:`42`\n\n",
    )


def test_add_new_contributors_searches_before_the_merge(tmp_path: Path, github: GitHub) -> None:
    run = github(_PULLS, set())

    add_new_contributors(_write(tmp_path, "md"), "1.2.3", "tox-dev/example")

    search = run.call_args_list[-1].kwargs["input"]
    assert 'query: "repo:tox-dev/example is:pr is:merged author:alice merged:<2026-10-20T10:00:00Z"' in search
    assert 'query: "repo:tox-dev/example is:pr is:merged author:carol merged:<2026-10-21T10:00:00Z"' in search


def test_add_new_contributors_orders_by_merge_time(tmp_path: Path, github: GitHub) -> None:
    github({"42": ("alice", "User", "2026-10-22T10:00:00Z"), "43": ("carol", "User", "2026-10-21T10:00:00Z")}, set())
    changelog = _write(tmp_path, "rst")

    add_new_contributors(changelog, "1.2.3", "tox-dev/example")

    assert (
        "- :user:`carol` made their first contribution in :pr:`43`\n"
        "- :user:`alice` made their first contribution in :pr:`42`\n"
    ) in changelog.read_text()


@pytest.mark.parametrize(
    ("merged", "expected"),
    [
        pytest.param(("2026-10-22T10:00:00Z", "2026-10-21T10:00:00Z"), ("Alice", "43"), id="later-pull-first"),
        pytest.param(("2026-10-20T10:00:00Z", "2026-10-21T10:00:00Z"), ("alice", "42"), id="earlier-pull-first"),
    ],
)
def test_add_new_contributors_uses_earliest_pull_per_author(
    tmp_path: Path, github: GitHub, merged: tuple[str, str], expected: tuple[str, str]
) -> None:
    run = github({"42": ("alice", "User", merged[0]), "43": ("Alice", "User", merged[1])}, set())
    changelog = _write(tmp_path, "rst")

    add_new_contributors(changelog, "1.2.3", "tox-dev/example")

    login, number = expected
    assert f"- :user:`{login}` made their first contribution in :pr:`{number}`\n\n" in changelog.read_text()
    assert run.call_args_list[-1].kwargs["input"].count("search(") == 1


@pytest.mark.parametrize(
    "author",
    [
        pytest.param(("dependabot", "Bot"), id="bot-type"),
        pytest.param(("pre-commit-ci[bot]", "User"), id="bot-login"),
        pytest.param(("claude", "User"), id="claude"),
        pytest.param(("codex", "User"), id="codex"),
        pytest.param(("CommandCodeBot", "User"), id="commandcode"),
        pytest.param(("copilot", "User"), id="copilot-case-insensitive"),
    ],
)
def test_add_new_contributors_excludes_bots_and_ai(tmp_path: Path, github: GitHub, author: tuple[str, str]) -> None:
    run = github({"42": (*author, "2026-10-20T10:00:00Z"), "43": ("carol", "User", "2026-10-21T10:00:00Z")}, {"carol"})
    changelog = _write(tmp_path, "md")

    add_new_contributors(changelog, "1.2.3", "tox-dev/example")

    assert changelog.read_text() == _MARKDOWN
    assert f"author:{author[0]}" not in run.call_args_list[-1].kwargs["input"]


def test_add_new_contributors_ignores_co_authors(tmp_path: Path, github: GitHub) -> None:
    run = github(_PULLS, {"alice", "carol"})

    add_new_contributors(_write(tmp_path, "md"), "1.2.3", "tox-dev/example")

    assert "author:bob" not in run.call_args_list[-1].kwargs["input"]


@pytest.mark.parametrize("extension", ["md", "rst"])
def test_add_new_contributors_omits_section_without_newcomers(tmp_path: Path, github: GitHub, extension: str) -> None:
    github(_PULLS, {"alice", "carol"})
    changelog = _write(tmp_path, extension)

    add_new_contributors(changelog, "1.2.3", "tox-dev/example")

    assert changelog.read_text() == (_MARKDOWN if extension == "md" else _RST)


@pytest.mark.parametrize(
    ("extension", "content"),
    [
        pytest.param("md", "## 1.2.3 (today)\n\n### Added\n\n- Add a cache.\n", id="markdown"),
        pytest.param("rst", "1.2.3 (today)\n=============\n\nAdded\n-----\n\n- Add a cache.\n", id="rst"),
    ],
)
def test_add_new_contributors_skips_section_without_pull_requests(
    tmp_path: Path, github: GitHub, extension: str, content: str
) -> None:
    run = github({}, set())
    changelog = tmp_path / f"CHANGELOG.{extension}"
    changelog.write_text(content)

    add_new_contributors(changelog, "1.2.3", "tox-dev/example")

    assert changelog.read_text() == content
    run.assert_not_called()


@pytest.mark.parametrize(
    ("extension", "content", "expected"),
    [
        pytest.param(
            "md",
            "## 1.2.3 (today)\n\n### Added\n\n- Add a cache ([#42](https://github.com/tox-dev/example/pull/42)).\n",
            "## 1.2.3 (today)\n\n### Added\n\n- Add a cache ([#42](https://github.com/tox-dev/example/pull/42)).\n\n"
            '<a name="release-1-2-3-new-contributors"></a>\n\n### New Contributors\n\n'
            "- [@alice](https://github.com/alice) made their first contribution in "
            "[#42](https://github.com/tox-dev/example/pull/42)\n",
            id="markdown-last-section",
        ),
        pytest.param(
            "rst",
            "*****************\n 1.2.3 (today)\n*****************\n\nAdded\n~~~~~\n\n- Add a cache (:pr:`42`).\n\n"
            "*****************\n 1.2.2 (today)\n*****************\n\nAdded\n~~~~~\n\n- Add a flag (:pr:`40`).\n",
            "*****************\n 1.2.3 (today)\n*****************\n\nAdded\n~~~~~\n\n- Add a cache (:pr:`42`).\n\n"
            ".. _release-1-2-3-new-contributors:\n\nNew Contributors\n~~~~~~~~~~~~~~~~\n\n"
            "- :user:`alice` made their first contribution in :pr:`42`\n\n"
            "*****************\n 1.2.2 (today)\n*****************\n\nAdded\n~~~~~\n\n- Add a flag (:pr:`40`).\n",
            id="rst-overline",
        ),
        pytest.param(
            "rst",
            "1.2.3 (today)\n=============\n\nAdded\n-----\n\n- Add a cache (:pr:`42`).\n",
            "1.2.3 (today)\n=============\n\nAdded\n-----\n\n- Add a cache (:pr:`42`).\n\n"
            ".. _release-1-2-3-new-contributors:\n\nNew Contributors\n----------------\n\n"
            "- :user:`alice` made their first contribution in :pr:`42`\n",
            id="rst-last-section",
        ),
    ],
)
def test_add_new_contributors_layouts(
    tmp_path: Path, github: GitHub, extension: str, content: str, expected: str
) -> None:
    github({"42": ("alice", "User", "2026-10-20T10:00:00Z")}, set())
    changelog = tmp_path / f"CHANGELOG.{extension}"
    changelog.write_text(content)

    add_new_contributors(changelog, "1.2.3", "tox-dev/example")

    assert changelog.read_text() == expected


@pytest.mark.parametrize(
    ("filename", "heading", "version"),
    [
        pytest.param("CHANGELOG.rst", "1.18.4 (2026-10-25)\n===================", "1.18.4", id="rst-date"),
        pytest.param(
            "CHANGELOG.rst",
            "`1.18.4 <https://github.com/tox-dev/example/tree/1.18.4>`_ - 2026-10-25\n"
            "======================================================================",
            "1.18.4",
            id="rst-linked",
        ),
        pytest.param("CHANGELOG.rst", "v1.6.4 (2026-10-25)\n===================", "1.6.4", id="rst-v-prefix"),
        pytest.param("CHANGELOG.md", "## [1.2.3] - 2026-10-25", "1.2.3", id="md-keep-a-changelog"),
    ],
)
def test_add_new_contributors_finds_notes_headings(
    tmp_path: Path, github: GitHub, filename: str, heading: str, version: str
) -> None:
    github({"42": ("alice", "User", "2026-10-20T10:00:00Z")}, set())
    changelog = tmp_path / filename
    rst = filename.endswith(".rst")
    item = "- Add a cache (:pr:`42`)." if rst else "- Add a cache ([#42](https://github.com/tox-dev/example/pull/42))."
    category = "Added\n-----" if rst else "### Added"
    changelog.write_text(f"{heading}\n\n{category}\n\n{item}\n")

    add_new_contributors(changelog, version, "tox-dev/example")

    assert "made their first contribution" in changelog.read_text()


@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [
        pytest.param("CHANGELOG.txt", "", "unsupported changelog format", id="format"),
        pytest.param("CHANGELOG.md", "## 1.2.2 (today)\n", "expected one changelog section for 1.2.3", id="md-missing"),
        pytest.param("CHANGELOG.rst", "1.2.2 (x)\n=========\n", "expected one changelog section", id="rst-missing"),
        pytest.param(
            "CHANGELOG.md",
            "## 1.2.3 (today)\n\n### New Contributors\n\n- [@a](https://github.com/a) made their first contribution\n",
            "New Contributors already present",
            id="md-present",
        ),
        pytest.param(
            "CHANGELOG.rst",
            "1.2.3 (today)\n=============\n\n- Add a cache (:pr:`42`).\n",
            "no category heading",
            id="rst-no-category",
        ),
    ],
)
def test_add_new_contributors_rejects_input(
    tmp_path: Path, github: GitHub, filename: str, content: str, message: str
) -> None:
    github({"42": ("alice", "User", "2026-10-20T10:00:00Z")}, set())
    changelog = tmp_path / filename
    changelog.write_text(content)

    with pytest.raises(ValueError, match=message):
        add_new_contributors(changelog, "1.2.3", "tox-dev/example")

    assert changelog.read_text() == content


def test_add_new_contributors_rejects_unmerged_pull(tmp_path: Path, github: GitHub) -> None:
    github({"42": ("alice", "User", None), "43": ("carol", "User", "2026-10-21T10:00:00Z")}, set())

    with pytest.raises(ValueError, match="pull request #42 is not merged"):
        add_new_contributors(_write(tmp_path, "md"), "1.2.3", "tox-dev/example")


def test_add_new_contributors_searches_deleted_author_as_ghost(tmp_path: Path, github: GitHub) -> None:
    run = github({"42": (None, "User", "2026-10-20T10:00:00Z"), "43": ("carol", "User", "2026-10-21T10:00:00Z")}, set())

    add_new_contributors(_write(tmp_path, "md"), "1.2.3", "tox-dev/example")

    assert "author:ghost merged:<2026-10-20T10:00:00Z" in run.call_args_list[-1].kwargs["input"]


@pytest.mark.parametrize(
    ("responses", "error", "message"),
    [
        pytest.param([(1, "", "API failed")], ValueError, "API failed", id="api-failure"),
        pytest.param([(1, "", "")], ValueError, "could not query GitHub", id="api-failure-silent"),
        pytest.param([(0, "not json", "")], ValueError, "invalid GitHub GraphQL response", id="json"),
        pytest.param([(0, '{"data": {"repository": []}}', "")], TypeError, "invalid GitHub GraphQL", id="scope-type"),
        pytest.param([(0, '{"data": {"repository": {}}}', "")], TypeError, "invalid pull request response", id="pull"),
        pytest.param(
            [
                (
                    0,
                    json.dumps({"data": {"repository": {"p42": {"number": 42, "mergedAt": 5, "author": None}}}}),
                    "",
                )
            ],
            TypeError,
            "invalid merge time",
            id="merge-time",
        ),
        pytest.param(
            [
                (
                    0,
                    json.dumps({
                        "data": {
                            "repository": {
                                "p42": {
                                    "number": 42,
                                    "mergedAt": "2026-10-20T10:00:00Z",
                                    "author": {"login": "alice", "__typename": "User"},
                                }
                            }
                        }
                    }),
                    "",
                ),
                (0, '{"data": {"s0": {}}}', ""),
            ],
            TypeError,
            "invalid GitHub search response",
            id="search",
        ),
    ],
)
def test_add_new_contributors_rejects_bad_responses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    responses: list[tuple[int, str, str]],
    error: type[Exception],
    message: str,
) -> None:
    monkeypatch.setattr(
        process.subprocess,
        "run",
        create_autospec(
            process.subprocess.run,
            side_effect=[subprocess.CompletedProcess([], *response) for response in responses],
        ),
    )
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "## 1.2.3 (today)\n\n### Added\n\n- Add ([#42](https://github.com/tox-dev/example/pull/42)).\n"
    )

    with pytest.raises(error, match=message):
        add_new_contributors(changelog, "1.2.3", "tox-dev/example")


def test_add_new_contributors_batches_large_releases(tmp_path: Path, github: GitHub) -> None:
    pulls = {str(number): (f"user{number}", "User", f"2026-10-20T10:{number % 60:02d}:00Z") for number in range(1, 102)}
    run = github(pulls, set())
    entries = "\n".join(
        f"- Change ([#{number}](https://github.com/tox-dev/example/pull/{number}))." for number in pulls
    )
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(f"## 1.2.3 (today)\n\n### Added\n\n{entries}\n")

    add_new_contributors(changelog, "1.2.3", "tox-dev/example")

    assert [call.kwargs["input"].count("pullRequest(") for call in run.call_args_list] == [100, 1, 0, 0]
    assert [call.kwargs["input"].count("search(") for call in run.call_args_list] == [0, 0, 100, 1]
    assert changelog.read_text().count("made their first contribution") == len(pulls)


@pytest.mark.parametrize("extension", ["md", "rst"])
def test_release_body_matches_changelog_section(tmp_path: Path, github: GitHub, extension: str) -> None:
    github(_PULLS, {"carol"})
    changelog = _write(tmp_path, extension)
    add_new_contributors(changelog, "1.2.3", "tox-dev/example")
    context = ReleaseContext(
        tag="1.2.3",
        repository="tox-dev/example",
        previous="1.2.2",
        artifact_url="https://pypi.org/project/example/1.2.3/",
    )

    body = (render_markdown if extension == "md" else render_rst)(changelog.read_text(), context)

    added = (
        "- Add a cache ([#42](https://github.com/tox-dev/example/pull/42)) by "
        + (
            "[@alice](https://github.com/alice) and [@bob](https://github.com/bob).\n"
            if extension == "md"
            else "@alice and @bob.\n"
        )
        + "- Add a flag ([#43](https://github.com/tox-dev/example/pull/43)) by "
        + ("[@carol](https://github.com/carol).\n\n" if extension == "md" else "@carol.\n\n")
    )
    contributor = (
        "- [@alice](https://github.com/alice)" if extension == "md" else "- @alice"
    ) + " made their first contribution in [#42](https://github.com/tox-dev/example/pull/42)\n\n"
    assert body == (
        '<a name="release-1-2-3-added"></a>\n\n### Features\n\n'
        + added
        + '<a name="release-1-2-3-new-contributors"></a>\n\n### New Contributors\n\n'
        + contributor
        + "[PyPI release](https://pypi.org/project/example/1.2.3/)\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/compare/1.2.2...1.2.3)\n"
    )


def test_contributors_cli_edits_changelog(tmp_path: Path, github: GitHub, monkeypatch: pytest.MonkeyPatch) -> None:
    github(_PULLS, {"carol"})
    changelog = _write(tmp_path, "md")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "contributors",
            "--changelog",
            str(changelog),
            "--version",
            "1.2.3",
            "--repository",
            "tox-dev/example",
        ],
    )

    main()

    assert "### New Contributors" in changelog.read_text()

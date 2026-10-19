"""Release note rendering tests."""

from __future__ import annotations

from dataclasses import replace
from textwrap import dedent

import pytest

from release_creator.notes.render import ReleaseContext, render_markdown, render_rst


def test_render_markdown_maps_categories_and_credits() -> None:
    changelog = dedent("""\
        <a name="release-1-2-3"></a>

        ## 1.2.3 (2026-10-18)

        <a name="release-1-2-3-added"></a>

        ### Added

        - New option ([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice),
          [@bob](https://github.com/bob) and [@carol](https://github.com/carol).

        <a name="release-1-2-2"></a>

        ## 1.2.2 (2026-10-17)

        ### Fixed

        - Old change.
        """)
    context = ReleaseContext(
        tag="1.2.3",
        repository="tox-dev/example",
        previous="1.2.2",
        artifact_url="https://pypi.org/project/example/1.2.3/",
    )
    result = render_markdown(changelog, context)
    assert result == dedent("""\
        <a name="release-1-2-3-added"></a>

        ### Features

        - New option ([#42](https://github.com/tox-dev/example/pull/42)) by @alice, @bob and @carol.

        [PyPI release](https://pypi.org/project/example/1.2.3/)

        **Full Changelog**: https://github.com/tox-dev/example/compare/1.2.2...1.2.3
        """)


def test_render_markdown_first_release_without_artifact() -> None:
    result = render_markdown("## 0.1.0 (2026-02-13)\n", ReleaseContext(tag="0.1.0", repository="tox-dev/example"))
    assert result == "**Full Changelog**: https://github.com/tox-dev/example/commits/0.1.0\n"


@pytest.mark.parametrize(
    "comparison",
    [
        pytest.param("**Full Changelog**: https://github.com/tox-dev/example/compare/old...1.2.3", id="bold"),
        pytest.param("Full Changelog: https://github.com/tox-dev/example/compare/old...1.2.3", id="plain"),
    ],
)
def test_render_markdown_replaces_source_comparison(comparison: str) -> None:
    changelog = f"## 1.2.3 (today)\n\n### Fixed\n\n- Correct a bug.\n\n{comparison}\n"

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example", previous="1.2.2"))

    assert result == (
        "### Bug fixes\n\n- Correct a bug.\n\n"
        "**Full Changelog**: https://github.com/tox-dev/example/compare/1.2.2...1.2.3\n"
    )


def test_render_markdown_cross_checks_pull_request_authors() -> None:
    changelog = dedent("""\
        ## 1.2.3 (today)

        ### Added

        - Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).
        """)
    generated = "* Add a feature by @alice in https://github.com/tox-dev/example/pull/42\n"

    result = render_markdown(
        changelog,
        ReleaseContext(tag="1.2.3", repository="tox-dev/example"),
        generated,
    )

    assert "by @alice" in result


@pytest.mark.parametrize(
    ("changelog", "generated", "message"),
    [
        pytest.param(
            "## 1.2.3 (today)\n\n### Added\n\n- Add a feature ([#42](https://github.com/tox-dev/example/pull/42)).\n",
            "* Add a feature by @alice in https://github.com/tox-dev/example/pull/42\n",
            "does not include @alice",
            id="missing-changelog-credit",
        ),
        pytest.param(
            "## 1.2.3 (today)\n\n### Added\n\n- Add a feature "
            "([#42](https://github.com/tox-dev/example/pull/42)) by @alice.\n",
            "* Add a feature\n",
            "no author for pull request #42",
            id="missing-generated-author",
        ),
        pytest.param(
            "## 1.2.3 (today)\n\n### Added\n\n- Add a feature "
            "([#42](https://github.com/tox-dev/example/pull/42)) by @alice.\n",
            "* Add a feature by @alice in https://github.com/tox-dev/other/pull/42\n",
            "no author for pull request #42",
            id="different-repository",
        ),
        pytest.param(
            "## 1.2.3 (today)\n\n### Added\n\n- Add a feature "
            "([#42](https://github.com/tox-dev/example/pull/42)) by @alice.\n",
            "* Add a feature by @alice in https://github.com/tox-dev/example/pull/42\n"
            "* Add a feature by @bob in https://github.com/tox-dev/example/pull/42\n",
            "conflicting generated authors",
            id="conflicting-generated-authors",
        ),
        pytest.param(
            "## 1.2.3 (today)\n\n### Added\n\n- Add a feature "
            "([#42](https://github.com/tox-dev/example/pull/42)) by @dependabot.\n",
            "* Add a feature by @dependabot[bot] in https://github.com/tox-dev/example/pull/42\n",
            "must not name bot @dependabot",
            id="bot-credit",
        ),
    ],
)
def test_render_markdown_rejects_author_mismatches(changelog: str, generated: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"), generated)


def test_render_markdown_does_not_credit_bot_authors() -> None:
    changelog = (
        "## 1.2.3 (today)\n\n### Added\n\n- Add a feature ([#42](https://github.com/tox-dev/example/pull/42)).\n"
    )
    generated = "* Add a feature by @dependabot[bot] in https://github.com/tox-dev/example/pull/42\n"

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"), generated)

    assert "@dependabot" not in result


@pytest.mark.parametrize(
    "reference",
    [
        pytest.param("#42", id="short-reference"),
        pytest.param("https://github.com/tox-dev/example/pull/42", id="pull-url"),
    ],
)
def test_render_markdown_keeps_credited_new_contributors(reference: str) -> None:
    changelog = "## 1.2.3 (today)\n\n### Added\n\n- New option by [@alice](https://github.com/alice).\n"
    generated = dedent(f"""\
        <!-- Release notes generated using configuration in .github/release.yml at main -->
        ## What's Changed
        * Generated change
        ## New Contributors
        * @alice made their first contribution in {reference}
        * @dependabot[bot] made their first contribution in #43
        * @uncredited made their first contribution in #44
        **Full Changelog**: unrelated
        """)

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"), generated)

    assert result == (
        "### Features\n\n- New option by @alice.\n\n"
        '<a name="release-1-2-3-new-contributors"></a>\n\n'
        "### New Contributors\n\n- @alice made their first contribution in #42\n\n"
        "**Full Changelog**: https://github.com/tox-dev/example/commits/1.2.3\n"
    )


@pytest.mark.parametrize(
    "generated",
    [
        pytest.param("## What's Changed\n* One change\n", id="no-section"),
        pytest.param("## New Contributors\n* @uncredited made their first contribution in #4\n", id="no-credit"),
    ],
)
def test_render_markdown_omits_unverified_contributors(generated: str) -> None:
    result = render_markdown("## 1.2.3 (today)\n", ReleaseContext(tag="1.2.3", repository="tox-dev/example"), generated)
    assert result == "**Full Changelog**: https://github.com/tox-dev/example/commits/1.2.3\n"


def test_render_rst_maps_categories_and_credits() -> None:
    changelog = dedent("""\
        .. _release-1-2-3:

        1.2.3 (2026-10-18)
        ==================

        .. _release-1-2-3-fixed:

        Fixed
        -----

        - Discard bad cache entries (:issue:`42`) - by :user:`alice` and :user:`bob`.
          Preserve ``None`` in the cache.

        .. _release-1-2-2:

        1.2.2 (2026-10-17)
        ==================

        Added
        -----

        - Old change.
        """)
    context = ReleaseContext(tag="1.2.3", repository="tox-dev/example", previous="1.2.2")
    result = render_rst(changelog, context, "pull")
    assert result == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n'
        "- Discard bad cache entries ([#42](https://github.com/tox-dev/example/pull/42)) by @alice and @bob. "
        "Preserve `None` in the cache.\n\n"
        "**Full Changelog**: https://github.com/tox-dev/example/compare/1.2.2...1.2.3\n"
    )


def test_render_rst_converts_explicit_author_link() -> None:
    changelog = dedent("""\
        1.2.3 (2026-10-18)
        ==================

        Added
        -----

        - Accept absolute ``file:///`` URLs (:pull:`3`) by `@alice <https://github.com/alice>`_.
        """)
    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))
    assert "- Accept absolute `file:///` URLs ([#3](https://github.com/tox-dev/example/pull/3)) by @alice." in result


def test_render_rst_keeps_issue_role_as_issue() -> None:
    changelog = "1.2.3 (today)\n==============\n\nFixed\n-----\n\n- Fix a bug (:issue:`5`).\n"
    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))
    assert "[#5](https://github.com/tox-dev/example/issues/5)" in result


def test_render_rst_omits_empty_category() -> None:
    changelog = "1.2.3 (today)\n==============\n\nAdded\n-----\n\nFixed\n-----\n\n- Correct a bug.\n"
    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))
    assert result == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n- Correct a bug.\n\n'
        "**Full Changelog**: https://github.com/tox-dev/example/commits/1.2.3\n"
    )


@pytest.mark.parametrize(
    "comparison",
    [
        pytest.param("**Full Changelog**: https://github.com/tox-dev/example/compare/old...1.2.3", id="bold"),
        pytest.param("Full Changelog: https://github.com/tox-dev/example/compare/old...1.2.3", id="plain"),
    ],
)
def test_render_rst_replaces_source_comparison(comparison: str) -> None:
    changelog = f"1.2.3 (today)\n==============\n\nFixed\n-----\n\n- Correct a bug.\n\n{comparison}\n"

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example", previous="1.2.2"))

    assert result == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n- Correct a bug.\n\n'
        "**Full Changelog**: https://github.com/tox-dev/example/compare/1.2.2...1.2.3\n"
    )


def test_render_rst_stops_at_linked_previous_version() -> None:
    changelog = dedent("""\
        1.2.3 (2026-10-19)
        ==================

        Fixed
        -----

        - Correct a bug.

        `1.2.2 <https://github.com/tox-dev/example/tree/1.2.2>`_ - 2026-10-18
        =====================================================================

        Bugfixes
        --------

        - An older fix.
        """)

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert result == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n- Correct a bug.\n\n'
        "**Full Changelog**: https://github.com/tox-dev/example/commits/1.2.3\n"
    )


@pytest.mark.parametrize(
    ("changelog", "issue_role", "message"),
    [
        pytest.param("", "issue", "found 0", id="absent"),
        pytest.param("1.2.3 (today)\n======\n1.2.3 (today)\n======\n", "issue", "found 2", id="duplicate"),
        pytest.param("1.2.3 (today)\n======\n- Entry.\n", "issue", "outside a category", id="uncategorized"),
        pytest.param("1.2.3 (today)\n======\nAn orphan paragraph.\n", "issue", "unexpected release text", id="orphan"),
        pytest.param(
            "1.2.3 (today)\n======\nUnsupported\n-----------\n",
            "issue",
            "unknown changelog category",
            id="unknown-category",
        ),
        pytest.param("1.2.3 (today)\n======\n", "bad", "invalid issue role", id="issue-role"),
    ],
)
def test_render_rst_rejects_invalid_input(changelog: str, issue_role: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"), issue_role)


@pytest.mark.parametrize(
    ("changelog", "overrides", "message"),
    [
        pytest.param("## 1.2.3 (today)\n", {"tag": "bad/tag"}, "invalid release tag", id="tag"),
        pytest.param("## 1.2.3 (today)\n", {"previous": "bad/tag"}, "invalid previous tag", id="previous"),
        pytest.param("## 1.2.3 (today)\n", {"repository": "bad"}, "invalid repository", id="repository"),
        pytest.param("## 1.2.3 (today)\n", {"artifact_url": "http://bad"}, "artifact URL", id="artifact"),
        pytest.param("", {}, "found 0", id="absent"),
        pytest.param("## 1.2.3 (today)\n## 1.2.3 (today)\n", {}, "found 2", id="duplicate"),
        pytest.param("## 1.2.3 (today)\n### Maintenance\n", {}, "unknown changelog category", id="category"),
    ],
)
def test_render_markdown_rejects_invalid_input(
    changelog: str,
    overrides: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        render_markdown(changelog, replace(ReleaseContext(tag="1.2.3", repository="tox-dev/example"), **overrides))

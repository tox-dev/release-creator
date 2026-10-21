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


def test_render_markdown_preserves_legacy_other_changes() -> None:
    changelog = "## 1.2.3 (today)\n\n### Other changes\n\n- Update development tooling.\n"

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert result == (
        "### Other changes\n\n- Update development tooling.\n\n"
        "**Full Changelog**: https://github.com/tox-dev/example/commits/1.2.3\n"
    )


def test_render_markdown_accepts_two_part_historical_tags() -> None:
    changelog = dedent("""\
        # Changelog

        ## [0.2] - 2021-12-29

        ### Other changes

        - Old maintenance entry.

        <a name="release-0-1"></a>

        ## [0.1] - 2021-06-17

        ### Added

        - First release.

        [0.2]: https://github.com/tox-dev/example/compare/0.1...0.2
        [0.1]: https://github.com/tox-dev/example/commits/0.1
        """)

    result = render_markdown(changelog, ReleaseContext(tag="0.2", repository="tox-dev/example", previous="0.1"))

    assert result == (
        "### Other changes\n\n- Old maintenance entry.\n\n"
        "**Full Changelog**: https://github.com/tox-dev/example/compare/0.1...0.2\n"
    )


@pytest.mark.parametrize(
    "heading",
    [
        pytest.param("## [1.2.3] - 2026-10-19", id="linked-date"),
        pytest.param("## v1.2.3 (2026-10-19)", id="v-prefixed"),
    ],
)
def test_render_markdown_accepts_existing_version_headings(heading: str) -> None:
    changelog = dedent(f"""\
        # Changelog

        {heading}

        ### Added

        - Support another platform.

        ## [1.2.2] - 2026-10-18

        ### Fixed

        - Old fix.

        [1.2.3]: https://github.com/tox-dev/example/compare/v1.2.2...v1.2.3
        [unreleased]: https://github.com/tox-dev/example/compare/v1.2.3...HEAD
        """)

    result = render_markdown(changelog, ReleaseContext(tag="v1.2.3", repository="tox-dev/example"))

    assert result == (
        "### Features\n\n- Support another platform.\n\n"
        "**Full Changelog**: https://github.com/tox-dev/example/commits/v1.2.3\n"
    )


@pytest.mark.parametrize(
    "tag",
    [
        pytest.param("v2.0.0a1", id="alpha"),
        pytest.param("2.0.0b1", id="beta"),
        pytest.param("1.10rc1", id="two-part-candidate"),
        pytest.param("v1.3.4rc", id="candidate-without-number"),
        pytest.param("0.10.2.0", id="four-part"),
    ],
)
def test_render_markdown_accepts_historical_version_shapes(tag: str) -> None:
    changelog = dedent(f"""\
        <a name="release-{tag.replace(".", "-")}"></a>

        ## {tag} (2021-05-13)

        ### Fixed

        - Correct the current release.

        <a name="release-0-1-0a1"></a>

        ## 0.1.0a1 (2020-01-01)

        ### Added

        - An older change.

        [{tag}]: https://github.com/tox-dev/example/commits/{tag}
        """)

    result = render_markdown(changelog, ReleaseContext(tag=tag, repository="tox-dev/example"))

    assert result == (
        "### Bug fixes\n\n- Correct the current release.\n\n"
        f"**Full Changelog**: https://github.com/tox-dev/example/commits/{tag}\n"
    )


def test_render_markdown_selects_package_history() -> None:
    changelog = dedent("""\
        # Changelog

        ## pyproject-fmt

        ### 2.30.4 (2026-10-19)

        #### Fixed

        - Preserve formatted input.

        ### 2.30.3 (2026-10-18)

        #### Added

        - Old feature.

        ## tox-toml-fmt

        ### 2.30.4 (2026-10-19)

        #### Added

        - Different package feature.
        """)
    context = ReleaseContext(
        tag="pyproject-fmt/2.30.4",
        repository="tox-dev/toml-fmt",
        package="pyproject-fmt",
        previous="pyproject-fmt/2.30.3",
    )

    result = render_markdown(changelog, context)

    assert result == (
        "### Bug fixes\n\n- Preserve formatted input.\n\n"
        "**Full Changelog**: https://github.com/tox-dev/toml-fmt/compare/"
        "pyproject-fmt/2.30.3...pyproject-fmt/2.30.4\n"
    )


def test_render_markdown_package_contributor_anchor() -> None:
    changelog = dedent("""\
        ## pyproject-fmt

        ### 2.30.4 (today)

        #### Added

        - Support a new option by [@alice](https://github.com/alice).
        """)
    generated = "## New Contributors\n* @alice made their first contribution in #42\n"

    result = render_markdown(
        changelog,
        ReleaseContext(tag="pyproject-fmt/2.30.4", repository="tox-dev/toml-fmt", package="pyproject-fmt"),
        generated,
    )

    assert '<a name="release-pyproject-fmt-2-30-4-new-contributors"></a>' in result


@pytest.mark.parametrize(
    ("changelog", "count"),
    [
        pytest.param("## other\n", 0, id="absent"),
        pytest.param("## example\n\n## example\n", 2, id="duplicate"),
    ],
)
def test_render_markdown_requires_one_package_history(changelog: str, count: int) -> None:
    with pytest.raises(ValueError, match=f"package section for example, found {count}"):
        render_markdown(
            changelog,
            ReleaseContext(tag="example/1.2.3", repository="tox-dev/example", package="example"),
        )


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
    "generated",
    [
        pytest.param("* Another change\n", id="omitted-pull-request"),
        pytest.param(
            "* Another change by @bob in https://github.com/tox-dev/other/pull/42\n",
            id="same-number-in-another-repository",
        ),
    ],
)
def test_render_markdown_uses_source_credit_when_generated_notes_omit_pull_request(generated: str) -> None:
    changelog = dedent("""\
        ## 1.2.3 (today)

        ### Added

        - Add Python support ([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).
        """)

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"), generated)

    assert "- Add Python support ([#42](https://github.com/tox-dev/example/pull/42)) by @alice." in result


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
            "## 1.2.3 (today)\n\n### Added\n\n- Add a feature ([#42](https://github.com/tox-dev/example/pull/42)).\n",
            "* Add a feature\n",
            "no author for pull request #42",
            id="missing-generated-author",
        ),
        pytest.param(
            "## 1.2.3 (today)\n\n### Added\n\n"
            "- Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) by @alice.\n"
            "- Add another feature ([#42](https://github.com/tox-dev/example/pull/42)).\n",
            "* Another change\n",
            "no author for pull request #42",
            id="missing-credit-on-second-entry",
        ),
        pytest.param(
            "## 1.2.3 (today)\n\n### Added\n\n- Add a feature ([#42](https://github.com/tox-dev/example/pull/42)).\n",
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
    ("reference", "heading", "pull_url"),
    [
        pytest.param("#42", "##", "https://github.com/tox-dev/example/pull/42", id="h2-short-reference"),
        pytest.param("#42", "###", "https://github.com/tox-dev/example/pull/42", id="h3-short-reference"),
        pytest.param(
            "https://github.com/upstream/example/pull/42",
            "##",
            "https://github.com/upstream/example/pull/42",
            id="h2-cross-repository-pull-url",
        ),
        pytest.param(
            "https://github.com/upstream/example/pull/42",
            "###",
            "https://github.com/upstream/example/pull/42",
            id="h3-cross-repository-pull-url",
        ),
    ],
)
def test_render_markdown_keeps_human_new_contributors(reference: str, heading: str, pull_url: str) -> None:
    changelog = "## 1.2.3 (today)\n\n### Added\n\n- New option by [@alice](https://github.com/alice).\n"
    generated = dedent(f"""\
        <!-- Release notes generated using configuration in .github/release.yml at main -->
        ## What's Changed
        * Generated change
        {heading} New Contributors
        * @alice made their first contribution in {reference}
        * @dependabot[bot] made their first contribution in #43
        * @bob made their first contribution in #44
        ## Other changes
        * @charlie made their first contribution in #45
        **Full Changelog**: unrelated
        """)

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"), generated)

    assert result == (
        "### Features\n\n- New option by @alice.\n\n"
        '<a name="release-1-2-3-new-contributors"></a>\n\n'
        f"### New Contributors\n\n- @alice made their first contribution in [#42]({pull_url})\n"
        "- @bob made their first contribution in [#44](https://github.com/tox-dev/example/pull/44)\n\n"
        "**Full Changelog**: https://github.com/tox-dev/example/commits/1.2.3\n"
    )


@pytest.mark.parametrize(
    "generated",
    [
        pytest.param("## What's Changed\n* One change\n", id="no-section"),
        pytest.param("## New Contributors\n* @dependabot[bot] made their first contribution in #4\n", id="bot"),
    ],
)
def test_render_markdown_omits_unverified_contributors(generated: str) -> None:
    result = render_markdown("## 1.2.3 (today)\n", ReleaseContext(tag="1.2.3", repository="tox-dev/example"), generated)
    assert result == "**Full Changelog**: https://github.com/tox-dev/example/commits/1.2.3\n"


def test_render_markdown_keeps_first_contributor_without_news_entry() -> None:
    generated = "## New Contributors\n* @alice made their first contribution in #42\n"

    result = render_markdown("## 1.2.3 (today)\n", ReleaseContext(tag="1.2.3", repository="tox-dev/example"), generated)

    assert result == (
        '<a name="release-1-2-3-new-contributors"></a>\n\n'
        "### New Contributors\n\n"
        "- @alice made their first contribution in [#42](https://github.com/tox-dev/example/pull/42)\n\n"
        "**Full Changelog**: https://github.com/tox-dev/example/commits/1.2.3\n"
    )


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


def test_render_rst_joins_wrapped_author_credit() -> None:
    changelog = dedent("""\
        1.2.3 (2026-10-18)
        ==================

        Fixed
        -----

        - Correct a long description. :pr:`42` - by
          :user:`alice` and :user:`bob`.
        """)

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert result == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n'
        "- Correct a long description. [#42](https://github.com/tox-dev/example/pull/42) by @alice and @bob.\n\n"
        "**Full Changelog**: https://github.com/tox-dev/example/commits/1.2.3\n"
    )


def test_render_rst_joins_wrapped_author_marker() -> None:
    changelog = dedent("""\
        1.2.3 (2026-10-18)
        ==================

        Fixed
        -----

        - Correct a long description. :pr:`42`
          - by :user:`alice` and :user:`bob`.
        """)

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert result == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n'
        "- Correct a long description. [#42](https://github.com/tox-dev/example/pull/42) by @alice and @bob.\n\n"
        "**Full Changelog**: https://github.com/tox-dev/example/commits/1.2.3\n"
    )


def test_render_rst_preserves_legacy_other_changes() -> None:
    changelog = "1.2.3 (today)\n==============\n\nOther changes\n-------------\n\n- Update development tooling.\n"

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert result == (
        '<a name="release-1-2-3-other-changes"></a>\n\n'
        "### Other changes\n\n- Update development tooling.\n\n"
        "**Full Changelog**: https://github.com/tox-dev/example/commits/1.2.3\n"
    )


@pytest.mark.parametrize(
    "heading",
    [
        pytest.param("0.2 (2021-12-29)", id="plain"),
        pytest.param("`0.2 <https://github.com/tox-dev/example/tree/0.2>`_ - 2021-12-29", id="linked"),
    ],
)
def test_render_rst_accepts_two_part_historical_tags(heading: str) -> None:
    changelog = f"{heading}\n================\n\nOther changes\n-------------\n\n- Old maintenance entry.\n"

    result = render_rst(changelog, ReleaseContext(tag="0.2", repository="tox-dev/example"))

    assert result == (
        '<a name="release-0-2-other-changes"></a>\n\n'
        "### Other changes\n\n- Old maintenance entry.\n\n"
        "**Full Changelog**: https://github.com/tox-dev/example/commits/0.2\n"
    )


@pytest.mark.parametrize(
    "tag",
    [
        pytest.param("v2.0.0a1", id="alpha"),
        pytest.param("2.0.0b1", id="beta"),
        pytest.param("1.10rc1", id="two-part-candidate"),
        pytest.param("v1.3.4rc", id="candidate-without-number"),
        pytest.param("0.10.2.0", id="four-part"),
    ],
)
def test_render_rst_accepts_historical_version_shapes(tag: str) -> None:
    changelog = dedent(f"""\
        {tag} (2021-05-13)
        ==================

        Fixed
        -----

        - Correct the current release.

        0.1.0 (2020-01-01)
        ==================

        Added
        -----

        - An older change.
        """)

    result = render_rst(changelog, ReleaseContext(tag=tag, repository="tox-dev/example"))

    assert result == (
        f'<a name="release-{tag.replace(".", "-")}-fixed"></a>\n\n'
        "### Bug fixes\n\n- Correct the current release.\n\n"
        f"**Full Changelog**: https://github.com/tox-dev/example/commits/{tag}\n"
    )


def test_render_rst_accepts_undated_linked_four_part_heading() -> None:
    changelog = dedent("""\
        `0.12.1.0 <https://github.com/tox-dev/example/tree/0.12.1.0>`_
        ===============================================================

        Fixed
        -----

        - Correct the current release.

        `0.12.0.4 <https://github.com/tox-dev/example/tree/0.12.0.4>`_
        ===============================================================

        Added
        -----

        - Add an earlier feature.
        """)

    result = render_rst(changelog, ReleaseContext(tag="0.12.1.0", repository="tox-dev/example"))

    assert result == (
        '<a name="release-0-12-1-0-fixed"></a>\n\n'
        "### Bug fixes\n\n- Correct the current release.\n\n"
        "**Full Changelog**: https://github.com/tox-dev/example/commits/0.12.1.0\n"
    )


def test_render_rst_accepts_linked_prerelease_heading() -> None:
    changelog = dedent("""\
        `v2.0.0a1 <https://github.com/tox-dev/example/tree/v2.0.0a1>`_ - 2021-05-13
        ===========================================================================

        Added
        -----

        - Add the first release.
        """)

    result = render_rst(changelog, ReleaseContext(tag="v2.0.0a1", repository="tox-dev/example"))

    assert result == (
        '<a name="release-v2-0-0a1-added"></a>\n\n'
        "### Features\n\n- Add the first release.\n\n"
        "**Full Changelog**: https://github.com/tox-dev/example/commits/v2.0.0a1\n"
    )


def test_render_rst_omits_empty_prerelease_section() -> None:
    changelog = dedent("""\
        v2.0.0a2 (2021-05-13)
        =====================

        v2.0.0a1 (2021-05-13)
        =====================

        Added
        -----

        - Add the first release.
        """)

    result = render_rst(changelog, ReleaseContext(tag="v2.0.0a2", repository="tox-dev/example"))

    assert result == "**Full Changelog**: https://github.com/tox-dev/example/commits/v2.0.0a2\n"


def test_render_rst_rejects_package_selection() -> None:
    with pytest.raises(ValueError, match="requires a Markdown changelog"):
        render_rst("", ReleaseContext(tag="1.2.3", repository="tox-dev/example", package="example"))


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


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "`PEP 838 <https://peps.python.org/pep-0838/>`_",
            "[PEP 838](https://peps.python.org/pep-0838/)",
            id="named-link",
        ),
        pytest.param(
            "`lxml <https://lxml.de/>`__",
            "[lxml](https://lxml.de/)",
            id="anonymous-link",
        ),
    ],
)
def test_render_rst_converts_external_link(source: str, expected: str) -> None:
    changelog = f"1.2.3 (today)\n==============\n\nAdded\n-----\n\n- Read {source}.\n"

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert result == (
        '<a name="release-1-2-3-added"></a>\n\n### Features\n\n'
        f"- Read {expected}.\n\n"
        "**Full Changelog**: https://github.com/tox-dev/example/commits/1.2.3\n"
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            ":meth:`AsyncReadWriteLock.close() <filelock.AsyncReadWriteLock.close>`",
            "`AsyncReadWriteLock.close()`",
            id="explicit-method-display",
        ),
        pytest.param(
            ":class:`the lock <filelock.ReadWriteLock>`",
            "`the lock`",
            id="explicit-class-display",
        ),
        pytest.param(":class:`~filelock.ReadWriteLock`", "`ReadWriteLock`", id="short-reference"),
        pytest.param(":data:`math.inf`", "`inf`", id="plain-reference"),
    ],
)
def test_render_rst_keeps_role_display(source: str, expected: str) -> None:
    changelog = f"1.2.3 (today)\n==============\n\nFixed\n-----\n\n- Call {source}.\n"

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert result == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n'
        f"- Call {expected}.\n\n"
        "**Full Changelog**: https://github.com/tox-dev/example/commits/1.2.3\n"
    )


def test_render_rst_links_pep_role() -> None:
    changelog = "1.2.3 (today)\n==============\n\nAdded\n-----\n\n- Support :PEP:`751`.\n"

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert result == (
        '<a name="release-1-2-3-added"></a>\n\n### Features\n\n'
        "- Support [PEP 751](https://peps.python.org/pep-0751/).\n\n"
        "**Full Changelog**: https://github.com/tox-dev/example/commits/1.2.3\n"
    )


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
        pytest.param("## 1.2.3 (today)\n", {"tag": "bad//tag"}, "invalid release tag", id="tag"),
        pytest.param("## 1.2.3 (today)\n", {"previous": "bad//tag"}, "invalid previous tag", id="previous"),
        pytest.param("## 1.2.3 (today)\n", {"package": "bad/name"}, "invalid package", id="package"),
        pytest.param(
            "## 1.2.3 (today)\n",
            {"tag": "other/1.2.3", "package": "example"},
            "does not match package",
            id="package-tag",
        ),
        pytest.param("## 1.2.3 (today)\n", {"repository": "bad"}, "invalid repository", id="repository"),
        pytest.param("## 1.2.3 (today)\n", {"artifact_url": "http://bad"}, "artifact URL", id="artifact"),
        pytest.param("", {}, "found 0", id="absent"),
        pytest.param("## 1.2.3 (today)\n## 1.2.3 (today)\n", {}, "found 2", id="duplicate"),
        pytest.param("## 1.2.3 (today)\n### Maintenance\n", {}, "unknown changelog category", id="category"),
        pytest.param("## 1.2.3 (today)\n- Plain bullet.\n", {}, "outside a category", id="uncategorized-bullet"),
        pytest.param("## 1.2.3 (today)\nPlain note.\n", {}, "outside an item", id="uncategorized-prose"),
        pytest.param("## 1.2.3 (today)\n### Fixed\n", {}, "empty changelog category", id="empty-category"),
        pytest.param(
            "## 1.2.3 (today)\n### Added\n### Fixed\n- Fix a bug.\n",
            {},
            "empty changelog category",
            id="empty-category-before-entry",
        ),
        pytest.param(
            "## 1.2.3 (today)\n### Fixed\n- Fix the bug.\nPlain note.\n",
            {},
            "outside an item",
            id="prose-after-bullet",
        ),
    ],
)
def test_render_markdown_rejects_invalid_input(
    changelog: str,
    overrides: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        render_markdown(changelog, replace(ReleaseContext(tag="1.2.3", repository="tox-dev/example"), **overrides))

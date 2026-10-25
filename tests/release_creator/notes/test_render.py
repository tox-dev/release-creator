"""Release note rendering tests."""

from __future__ import annotations

from dataclasses import replace
from textwrap import dedent
lazy from collections.abc import Callable

import pytest

from release_creator.notes.render import ReleaseContext, render_markdown, render_rst


def test_render_markdown_maps_categories_and_credits() -> None:
    entry = (
        "- New option ([#42](https://github.com/tox-dev/example/pull/42)) by "
        "[@alice](https://github.com/alice), [@bob](https://github.com/bob) and [@carol](https://github.com/carol)."
    )
    changelog = dedent("""\
        <a name="release-1-2-3"></a>

        ## 1.2.3 (2026-10-18)

        <a name="release-1-2-3-added"></a>

        ### Added

        @ENTRY@

        <a name="release-1-2-2"></a>

        ## 1.2.2 (2026-10-17)

        ### Fixed

        - Old change.
        """).replace("@ENTRY@", entry)
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

        @ENTRY@

        [PyPI release](https://pypi.org/project/example/1.2.3/)

        [Full Changelog](https://github.com/tox-dev/example/compare/1.2.2...1.2.3)
        """).replace("@ENTRY@", entry)


def test_render_markdown_rejects_markup_inside_anchor() -> None:
    changelog = '## 1.2.3 (today)\n\n<a name="release-1-2-3-added"><details></a>\n\n### Added\n\n- Add support.\n'

    with pytest.raises(ValueError, match="release text outside an item"):
        render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))


def test_render_markdown_first_release_without_artifact() -> None:
    result = render_markdown("## 0.1.0 (2026-02-13)\n", ReleaseContext(tag="0.1.0", repository="tox-dev/example"))
    assert result == "[Full Changelog](https://github.com/tox-dev/example/commits/0.1.0)\n"


def test_render_markdown_preserves_legacy_other_changes() -> None:
    changelog = "## 1.2.3 (today)\n\n### Other changes\n\n- Update development tooling.\n"

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert result == (
        "### Other changes\n\n- Update development tooling.\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
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
        "[Full Changelog](https://github.com/tox-dev/example/compare/0.1...0.2)\n"
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
        "[Full Changelog](https://github.com/tox-dev/example/commits/v1.2.3)\n"
    )


@pytest.mark.parametrize(
    "tag",
    [
        pytest.param("v2.0.0a1", id="alpha"),
        pytest.param("2.0.0b1", id="beta"),
        pytest.param("1.10rc1", id="two-part-candidate"),
        pytest.param("v1.3.4rc", id="candidate-without-number"),
        pytest.param("0.10.2.0", id="four-part"),
        pytest.param("1.3.4.post1", id="postrelease"),
        pytest.param("1.3.4.dev1", id="development"),
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
        f"[Full Changelog](https://github.com/tox-dev/example/commits/{tag})\n"
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
        "[Full Changelog](https://github.com/tox-dev/toml-fmt/compare/"
        "pyproject-fmt/2.30.3...pyproject-fmt/2.30.4)\n"
    )


def test_render_markdown_accepts_underscore_package_anchors() -> None:
    changelog = dedent("""\
        ## some_name

        ### 1.0.0 (today)

        <a name="release-some_name-1-0-0-fixed"></a>

        #### Fixed

        - Fix the current release.

        <a name="release-some_name-1-0-1"></a>

        Draft text for the next release.
        """)

    result = render_markdown(
        changelog, ReleaseContext(tag="some_name/1.0.0", repository="tox-dev/example", package="some_name")
    )

    assert "- Fix the current release." in result
    assert "Draft text" not in result


def test_render_markdown_stops_at_next_package_release_anchor() -> None:
    changelog = dedent("""\
        ## pyproject-fmt

        ### 2.30.4 (today)

        #### Fixed

        - Preserve formatted input.

        <a name="release-other-2-0-0"></a>

        - Preserve package-local history.

        <a name="release-pyproject-fmt-2-30-5"></a>

        Draft text for the next release.
        """)

    result = render_markdown(
        changelog,
        ReleaseContext(tag="pyproject-fmt/2.30.4", repository="tox-dev/toml-fmt", package="pyproject-fmt"),
    )

    assert "- Preserve formatted input." in result
    assert "- Preserve package-local history." in result
    assert "Draft text for the next release." not in result


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
        pytest.param("[Full Changelog](https://github.com/tox-dev/example/compare/old...1.2.3)", id="link"),
    ],
)
def test_render_markdown_replaces_source_comparison(comparison: str) -> None:
    changelog = f"## 1.2.3 (today)\n\n### Fixed\n\n- Correct a bug.\n\n{comparison}\n"

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example", previous="1.2.2"))

    assert result == (
        "### Bug fixes\n\n- Correct a bug.\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/compare/1.2.2...1.2.3)\n"
    )


def test_render_markdown_cross_checks_pull_request_authors() -> None:
    changelog = dedent("""\
        ## 1.2.3 (today)

        ### Added

        - Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).
        """)

    result = render_markdown(
        changelog,
        ReleaseContext(tag="1.2.3", repository="tox-dev/example"),
    )

    assert "by [@alice](https://github.com/alice)" in result


def test_render_rst_checks_credit_before_pull_request() -> None:
    changelog = "1.2.3 (2026-10-23)\n==================\n\nAdded\n-----\n\n- Patch by :user:`alice`. (:pr:`42`)\n"

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "Patch by @alice. ([#42](https://github.com/tox-dev/example/pull/42))" in result


def test_render_markdown_checks_shared_credit_for_multiple_pull_requests() -> None:
    changelog = (
        "## 1.2.3 (today)\n\n### Added\n\n"
        "- Add support ([#42](https://github.com/tox-dev/example/pull/42)), "
        "([#43](https://github.com/tox-dev/example/pull/43)) by @alice.\n"
    )

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "([#43](https://github.com/tox-dev/example/pull/43)) by @alice" in result


@pytest.mark.parametrize(
    "references",
    [
        pytest.param(
            "[#5](https://github.com/tox-dev/example/pull/5) [#6](https://github.com/tox-dev/example/pull/6)",
            id="adjacent-links",
        ),
        pytest.param("(#5) (#6)", id="adjacent-short-references"),
    ],
)
def test_render_markdown_shares_credit_for_adjacent_references(references: str) -> None:
    changelog = f"## 1.2.3 (today)\n\n### Added\n\n- Add support {references} by @alice.\n"

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "by @alice" in result


def test_render_rst_shares_credit_for_adjacent_roles() -> None:
    changelog = "1.2.3 (today)\n==============\n\nAdded\n-----\n\n- Add support (:pr:`5`) (:pr:`6`) by :user:`alice`.\n"

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "by @alice" in result


@pytest.mark.parametrize(
    "entry",
    [
        pytest.param(
            "([#5](https://github.com/tox-dev/example/pull/5), "
            "[#6](https://github.com/tox-dev/example/pull/6)) by @alice and @bob",
            id="paired-links",
        ),
        pytest.param(
            "Fix by @alice and @bob ([#5](https://github.com/tox-dev/example/pull/5), [#6](https://github.com/tox-dev/example/pull/6))",
            id="credit-first",
        ),
    ],
)
def test_render_markdown_accepts_shared_multi_author_credit(entry: str) -> None:

    result = render_markdown(
        f"## 1.2.3 (today)\n\n### Fixed\n\n- {entry}.\n",
        ReleaseContext(tag="1.2.3", repository="tox-dev/example"),
    )

    assert entry in result


@pytest.mark.parametrize(
    "literal",
    [
        pytest.param("`(#5)`", id="plain-code-span"),
        pytest.param("``x` (#5)``", id="different-width-inner-backtick"),
    ],
)
def test_render_markdown_ignores_pull_reference_in_code_span(literal: str) -> None:
    changelog = f"## 1.2.3 (today)\n\n### Fixed\n\n- Document {literal}.\n"

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "### Bug fixes" in result


def test_render_markdown_scopes_distinct_credits_on_one_line() -> None:
    changelog = (
        "## 1.2.3 (today)\n\n### Added\n\n"
        "- Add support ([#42](https://github.com/tox-dev/example/pull/42)) by @alice; "
        "refine it ([#43](https://github.com/tox-dev/example/pull/43)) by @bob.\n"
    )

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "[#42](https://github.com/tox-dev/example/pull/42)) by @alice" in result
    assert "[#43](https://github.com/tox-dev/example/pull/43)) by @bob" in result


def test_render_markdown_scopes_credit_before_first_pull_request() -> None:
    changelog = (
        "## 1.2.3 (today)\n\n### Added\n\n"
        "- Add support by @alice ([#42](https://github.com/tox-dev/example/pull/42)); "
        "refine it ([#43](https://github.com/tox-dev/example/pull/43)) by @bob.\n"
    )

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert (
        "- Add support by @alice ([#42](https://github.com/tox-dev/example/pull/42)); "
        "refine it ([#43](https://github.com/tox-dev/example/pull/43)) by @bob."
    ) in result


def test_render_markdown_shares_credit_before_paired_pull_requests() -> None:
    changelog = (
        "## 1.2.3 (today)\n\n### Added\n\n"
        "- Add support by @alice ([#42](https://github.com/tox-dev/example/pull/42)), "
        "([#43](https://github.com/tox-dev/example/pull/43)).\n"
    )

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert (
        "- Add support by @alice ([#42](https://github.com/tox-dev/example/pull/42)), "
        "([#43](https://github.com/tox-dev/example/pull/43))."
    ) in result


@pytest.mark.parametrize(
    "entry",
    [
        pytest.param(
            "- Fix startup https://github.com/tox-dev/example/pull/42 by @alice; "
            "see https://github.com/tox-dev/example/pull/43 for the earlier attempt.",
            id="bare-primary-and-semicolon-see",
        ),
        pytest.param(
            "- Fix startup ([#42](https://github.com/tox-dev/example/pull/42)) by @alice. "
            "See https://github.com/tox-dev/example/pull/43 for the earlier attempt.",
            id="linked-primary-and-sentence-see",
        ),
        pytest.param(
            "- Fix startup ([#42](https://github.com/tox-dev/example/pull/42)) by @alice; "
            "compare https://github.com/tox-dev/example/pull/43 for the earlier attempt.",
            id="linked-primary-and-semicolon-compare",
        ),
        pytest.param(
            "- Fix startup ([#42](https://github.com/tox-dev/example/pull/42)) by @alice, "
            "see https://github.com/tox-dev/example/pull/43 for the earlier attempt.",
            id="linked-primary-and-comma-see",
        ),
        pytest.param(
            "- Fix startup ([#42](https://github.com/tox-dev/example/pull/42)) by @alice\n"
            "  see https://github.com/tox-dev/example/pull/43 for the earlier attempt.",
            id="linked-primary-and-wrapped-see",
        ),
    ],
)
def test_render_markdown_ignores_contextual_pull_url(entry: str) -> None:
    changelog = f"## 1.2.3 (today)\n\n### Fixed\n\n{entry}\n"

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "https://github.com/tox-dev/example/pull/43 for the earlier attempt" in result


@pytest.mark.parametrize("phrase", [pytest.param("by default", id="default"), pytest.param("by design", id="design")])
def test_render_markdown_ignores_contextual_url_before_noncredit_by(phrase: str) -> None:
    changelog = (
        "## 1.2.3 (today)\n\n### Fixed\n\n"
        "- Fix startup (#42) by @alice; "
        f"see https://github.com/tox-dev/example/pull/43 {phrase}.\n"
    )

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert f"https://github.com/tox-dev/example/pull/43 {phrase}" in result


@pytest.mark.parametrize(
    ("render", "heading", "reference"),
    [
        pytest.param(
            render_markdown,
            "## 1.2.3 (today)\n\n### Fixed\n\n",
            "[#42](https://github.com/tox-dev/example/issues/42)",
            id="markdown-link",
        ),
        pytest.param(render_rst, "1.2.3 (today)\n==============\n\nFixed\n-----\n\n", ":issue:`42`", id="rst-role"),
        pytest.param(
            render_rst,
            "1.2.3 (today)\n==============\n\nFixed\n-----\n\n",
            "`#42 <https://github.com/tox-dev/example/issues/42>`_",
            id="rst-link",
        ),
    ],
)
def test_render_ignores_issue_without_pull_author(
    render: Callable[[str, ReleaseContext], str], heading: str, reference: str
) -> None:
    changelog = f"{heading}- Fix startup ({reference}).\n"

    result = render(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "[#42](https://github.com/tox-dev/example/issues/42)" in result


def test_render_ignores_repository_issue_shorthand_without_pull_author() -> None:
    changelog = "## 1.2.3 (today)\n\n### Fixed\n\n- Fix startup (tox-dev/example#42).\n"

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "tox-dev/example#42" in result


@pytest.mark.parametrize(
    "reference",
    [
        pytest.param("[#43](https://github.com/tox-dev/example/pull/43)", id="number-label"),
        pytest.param("[PR #43](https://github.com/tox-dev/example/pull/43)", id="pr-label"),
    ],
)
def test_render_markdown_ignores_contextual_linked_pull(reference: str) -> None:
    changelog = (
        f"## 1.2.3 (today)\n\n### Fixed\n\n- Fix startup (#42) by @alice; see {reference} for the earlier attempt.\n"
    )

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert reference in result


def test_render_rst_ignores_contextual_linked_pull() -> None:
    changelog = (
        "1.2.3 (today)\n==============\n\nFixed\n-----\n\n"
        "- Fix startup (#42) by @alice; "
        "see `PR #43 <https://github.com/tox-dev/example/pull/43>`_ for the earlier attempt.\n"
    )

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "[PR #43](https://github.com/tox-dev/example/pull/43)" in result


def test_render_markdown_ignores_other_repository_short_reference() -> None:
    changelog = "## 1.2.3 (today)\n\n### Fixed\n\n- Follow other/project#42 in our fix (#43) by @alice.\n"

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "other/project#42" in result


@pytest.mark.parametrize(
    "url",
    [
        pytest.param("https://example.com/path/#42", id="numeric-fragment"),
        pytest.param("http://example.com/path/#GH-42", id="github-style-fragment"),
        pytest.param("https://example.com/redirect?to=https://github.com/tox-dev/example/pull/42", id="nested-url"),
        pytest.param("https://example.com/docs/tox-dev/example#42", id="repository-shorthand-in-url"),
    ],
)
def test_render_markdown_ignores_unrelated_url_fragments(url: str) -> None:
    changelog = f"## 1.2.3 (today)\n\n### Added\n\n- Explain {url} and fix (#43) by @alice.\n"

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert url in result


@pytest.mark.parametrize(
    "literal",
    [
        pytest.param("`(#42)`", id="inline-markdown"),
        pytest.param("``(#42)``", id="long-inline-markdown"),
    ],
)
def test_render_markdown_ignores_short_pull_references_in_code(literal: str) -> None:
    changelog = f"## 1.2.3 (today)\n\n### Added\n\n- Display the literal syntax {literal} in the help text.\n"

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "Display the literal syntax `(#42)`" in result


def test_render_rst_ignores_short_pull_references_in_inline_literals() -> None:
    changelog = (
        "1.2.3 (today)\n==============\n\nAdded\n-----\n\n- Display the literal syntax ``(#42)`` in the help text.\n"
    )

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "Display the literal syntax `(#42)`" in result


@pytest.mark.parametrize(
    "code",
    [
        pytest.param("  ```text\n  (#42)\n  ```", id="fence"),
        pytest.param("  ````text\n  ```\n  (#42)\n  ```\n  ````", id="nested-fence"),
    ],
)
def test_render_markdown_ignores_short_pull_references_in_fences(code: str) -> None:
    changelog = f"## 1.2.3 (today)\n\n### Added\n\n- Display the literal syntax:\n\n{code}\n"

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "(#42)" in result


@pytest.mark.parametrize(
    "profile",
    [
        pytest.param("https://github.com/alice/", id="trailing-slash"),
        pytest.param("https://www.github.com/alice", id="www"),
    ],
)
def test_render_markdown_accepts_canonical_profile_variants(profile: str) -> None:
    changelog = f"## 1.2.3 (today)\n\n### Added\n\n- Add support (#42) by [@alice]({profile}).\n"

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert f"by [@alice]({profile})." in result


def test_render_markdown_ignores_other_repository_link_label() -> None:
    changelog = (
        "## 1.2.3 (today)\n\n### Added\n\n"
        "- Follow [other/project#42](https://github.com/other/project/pull/42) by @alice.\n"
    )

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "[other/project#42](https://github.com/other/project/pull/42)" in result


def test_render_markdown_keeps_plain_link_label() -> None:
    changelog = "## 1.2.3 (today)\n\n### Added\n\n- Add [the parser](https://example.com/x) (#5) by @alice.\n"

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "- Add [the parser](https://example.com/x) (#5) by @alice." in result


def test_render_markdown_matches_author_handle_case_insensitively() -> None:
    changelog = "## 1.2.3 (today)\n\n### Added\n\n- Add support (#42) by @alice.\n"

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "by @alice" in result


@pytest.mark.parametrize(
    "tag",
    [
        pytest.param("style", id="style"),
        pytest.param("textarea", id="textarea"),
        pytest.param("code", id="code"),
    ],
)
def test_render_markdown_accepts_prose_naming_html_element(tag: str) -> None:
    changelog = f"## 1.2.3 (today)\n\n### Fixed\n\n- Keep <{tag}> elements (#5) by @alice.\n"

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert f"- Keep <{tag}> elements (#5) by @alice." in result


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        pytest.param(
            "- Show `[@alice](https://github.com/alice)` literally.\n",
            "- Show `[@alice](https://github.com/alice)` literally.\n",
            id="inline",
        ),
        pytest.param(
            "- Show example:\n\n  ```md\n  [@alice](https://github.com/alice)\n  ```\n",
            "- Show example:\n\n  ```md\n  [@alice](https://github.com/alice)\n  ```\n",
            id="fenced",
        ),
    ],
)
def test_render_markdown_keeps_author_links_in_code(entry: str, expected: str) -> None:
    changelog = f"## 1.2.3 (today)\n\n### Fixed\n\n{entry}"

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert (
        result == f"### Bug fixes\n\n{expected}\n[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


@pytest.mark.parametrize(
    "opening",
    [
        pytest.param("<br>", id="br"),
        pytest.param('<br title="x > y">', id="br-quoted-attribute"),
        pytest.param("<hr>", id="hr"),
        pytest.param("<br />", id="self-closing-br"),
    ],
)
def test_render_markdown_accepts_credit_after_html_break(opening: str) -> None:
    changelog = f"## 1.2.3 (today)\n\n### Fixed\n\n- Fix https://github.com/tox-dev/example/pull/5{opening}by @alice.\n"

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert result == (
        "### Bug fixes\n\n"
        f"- Fix https://github.com/tox-dev/example/pull/5{opening}by @alice.\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


@pytest.mark.parametrize(
    ("separator", "expected_break"),
    [
        pytest.param("  \n  ", "\\\n  ", id="hard-break"),
        pytest.param("\n\n  ", "\n\n  ", id="paragraph"),
    ],
)
def test_render_markdown_accepts_credit_across_one_list_item(separator: str, expected_break: str) -> None:
    changelog = (
        f"## 1.2.3 (today)\n\n### Fixed\n\n- Fix [#5](https://github.com/tox-dev/example/pull/5){separator}by @alice.\n"
    )

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert result == (
        "### Bug fixes\n\n"
        f"- Fix [#5](https://github.com/tox-dev/example/pull/5){expected_break}by @alice.\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


def test_render_markdown_keeps_html_anchor_and_literal_link_example() -> None:
    changelog = dedent("""\
        ## 1.2.3 (today)

        ### Fixed

        - Keep <a name="parser"></a> and the literal `<a href="https://github.com/mallory">` example.
        """)

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert '<a name="parser"></a>' in result
    assert '`<a href="https://github.com/mallory">`' in result


def test_render_rst_accepts_profile_link_with_different_handle_case() -> None:
    changelog = dedent("""\
        1.2.3 (today)
        =============

        Added
        -----

        - Add support (:pr:`42`) by `@Alice <https://github.com/alice>`_.
        """)

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "by @Alice" in result


def test_render_markdown_accepts_multiple_profile_credit_links() -> None:
    changelog = dedent("""\
        ## 1.2.3 (today)

        ### Added

        - Add support ([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice) and [@bob](https://github.com/bob).
        """)

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "by [@alice](https://github.com/alice) and [@bob](https://github.com/bob)" in result


def test_render_markdown_accepts_reference_profile_credit_link() -> None:
    changelog = (
        "## 1.2.3 (today)\n\n### Added\n\n"
        "- Add support (#42) by [@alice][profile].\n\n"
        "  [profile]: https://github.com/alice\n"
    )

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "by [@alice][profile]" in result


def test_render_rst_maps_categories_and_credits() -> None:
    changelog = dedent("""\
        .. _release-1-2-3:

        1.2.3 (2026-10-18)
        ==================

        .. _release-1-2-3-fixed:

        Fixed
        -----

        - Discard bad cache entries (:pr:`42`) - by :user:`alice` and :user:`bob`.
          Preserve ``None`` in the cache.

        .. _release-1-2-2:

        1.2.2 (2026-10-17)
        ==================

        Added
        -----

        - Old change.
        """)
    context = ReleaseContext(tag="1.2.3", repository="tox-dev/example", previous="1.2.2")
    result = render_rst(changelog, context)
    assert result == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n'
        "- Discard bad cache entries ([#42](https://github.com/tox-dev/example/pull/42)) by @alice and @bob. "
        "Preserve `None` in the cache.\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/compare/1.2.2...1.2.3)\n"
    )


def test_render_rst_keeps_top_level_warning_outside_bullet() -> None:
    changelog = dedent("""\
        v20.0.0b1 (2020-01-28)
        =======================

        Removed
        -------

        - A shim remains for Python 2.

        .. warning::

            Version ``20.0.0b1`` starts a new release history. The old history is in the `legacy docs
            <https://virtualenv.pypa.io/en/legacy/changes.html>`_.
        """)

    result = render_rst(changelog, ReleaseContext(tag="20.0.0b1", repository="pypa/virtualenv"))

    assert result == (
        '<a name="release-20-0-0b1-removed"></a>\n\n### Removals\n\n'
        "- A shim remains for Python 2.\n\n"
        "> **Warning:** Version `20.0.0b1` starts a new release history. The old history is in the "
        "[legacy docs](https://virtualenv.pypa.io/en/legacy/changes.html).\n\n"
        "[Full Changelog](https://github.com/pypa/virtualenv/commits/20.0.0b1)\n"
    )


def test_render_rst_preserves_warning_before_category_items() -> None:
    changelog = dedent("""\
        1.2.3 (today)
        ==============

        Fixed
        -----

        .. warning::

            Restart after upgrading.

        - Fix startup (#42) by @alice.
        """)

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert result.index("### Bug fixes") < result.index("> **Warning:**") < result.index("- Fix startup")


@pytest.mark.parametrize(
    ("language", "source", "expected"),
    [
        pytest.param(
            "dockerfile",
            "ENV VIRTUALENV_READ_ONLY_APP_DATA=1\n      RUN virtualenv /tmp/venv",
            "ENV VIRTUALENV_READ_ONLY_APP_DATA=1\n  RUN virtualenv /tmp/venv",
            id="dockerfile",
        ),
        pytest.param(
            "console",
            "created virtual environment in 350ms\n        creator CPython3Posix(dest=/x)",
            "created virtual environment in 350ms\n    creator CPython3Posix(dest=/x)",
            id="console",
        ),
    ],
)
def test_render_rst_keeps_nested_code_block(language: str, source: str, expected: str) -> None:
    changelog = (
        "20.2.0 (2020-08-25)\n===================\n\nAdded\n-----\n\n"
        "- Display the virtual environment, for example:\n\n"
        f"  .. code-block:: {language}\n\n      {source}\n\n"
        "  Patch by :user:`alice`. (:pr:`2009`)\n"
    )

    result = render_rst(changelog, ReleaseContext(tag="20.2.0", repository="pypa/virtualenv"))

    assert result == (
        '<a name="release-20-2-0-added"></a>\n\n### Features\n\n'
        "- Display the virtual environment, for example:\n\n"
        f"  ```{language}\n  {expected}\n  ```\n\n"
        "  Patch by @alice. ([#2009](https://github.com/pypa/virtualenv/pull/2009))\n\n"
        "[Full Changelog](https://github.com/pypa/virtualenv/commits/20.2.0)\n"
    )


def test_render_rst_preserves_code_only_bullet() -> None:
    changelog = dedent("""\
        1.2.3 (today)
        =============

        Added
        -----

        - .. code-block:: python

              print("x")
        """)

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert '- ```python\n  print("x")\n  ```' in result


def test_render_rst_keeps_nested_bullets() -> None:
    changelog = dedent("""\
        v20.24.4 (2023-08-30)
        =====================

        Packaging
        ---------

        - Upgrade embedded wheels:

          - setuptools to ``68.1.2`` from ``68.1.0`` on ``3.8+``
          - wheel to ``0.41.2`` from ``0.41.1`` on ``3.7+`` (:pr:`2628`)
        """)

    result = render_rst(changelog, ReleaseContext(tag="20.24.4", repository="pypa/virtualenv"))

    assert result == (
        '<a name="release-20-24-4-packaging"></a>\n\n### Packaging\n\n'
        "- Upgrade embedded wheels:\n"
        "  - setuptools to `68.1.2` from `68.1.0` on `3.8+`\n"
        "  - wheel to `0.41.2` from `0.41.1` on `3.7+` ([#2628](https://github.com/pypa/virtualenv/pull/2628))\n\n"
        "[Full Changelog](https://github.com/pypa/virtualenv/commits/20.24.4)\n"
    )


@pytest.mark.parametrize(
    "detail",
    [
        pytest.param("by design, it is read-only.", id="ordinary-prose"),
        pytest.param("by @design.", id="unlinked-handle"),
    ],
)
def test_render_rst_keeps_nested_by_design_bullet(detail: str) -> None:
    changelog = f"1.2.3 (today)\n==============\n\nAdded\n-----\n\n- Introduce safe mode.\n\n  - {detail}\n"

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert result == (
        '<a name="release-1-2-3-added"></a>\n\n### Features\n\n'
        f"- Introduce safe mode.\n  - {detail}\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


def test_render_rst_keeps_nested_bullet_without_intro() -> None:
    changelog = (
        "4.24.2 (2025-03-07)\n=====================\n\nFixed\n-----\n\n"
        "- - ``--parallel-no-spinner`` respects ``--parallel N`` (:issue:`3495`)\n"
    )

    result = render_rst(changelog, ReleaseContext(tag="4.24.2", repository="tox-dev/tox"))

    assert "- - `--parallel-no-spinner` respects `--parallel N` " in result
    assert "[#3495](https://github.com/tox-dev/tox/issues/3495)" in result


def test_render_rst_joins_item_paragraphs() -> None:
    changelog = (
        "1.2.3 (today)\n==============\n\nFixed\n-----\n\n"
        "- Preserve the existing file.\n\n  Explain why the file is kept. (:pr:`42`)\n"
    )

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "- Preserve the existing file. Explain why the file is kept. " in result


def test_render_rst_keeps_paragraph_after_nested_bullets() -> None:
    changelog = dedent("""\
        v20.0.24 (2020-07-15)
        =====================

        Added
        -----

        - Ensure seeded packages remain current:

          - add a CLI flag
          - upgrade embedded wheels after 28 days

          More details under :ref:`wheels` - by :user:`alice`. (:issue:`1821`)
        """)

    result = render_rst(changelog, ReleaseContext(tag="20.0.24", repository="pypa/virtualenv"))

    assert result == (
        '<a name="release-20-0-24-added"></a>\n\n### Features\n\n'
        "- Ensure seeded packages remain current:\n\n"
        "  - add a CLI flag\n"
        "  - upgrade embedded wheels after 28 days\n\n"
        "  More details under `wheels` by @alice. ([#1821](https://github.com/pypa/virtualenv/issues/1821))\n\n"
        "[Full Changelog](https://github.com/pypa/virtualenv/commits/20.0.24)\n"
    )


def test_render_rst_keeps_group_credit_after_nested_bullets() -> None:
    changelog = dedent("""\
        v20.27.0 (2024-10-17)
        =====================

        Packaging
        ---------

        - Upgrade embedded wheels:

          - setuptools to ``75.2.0``
          - Removed pip of ``24.0``
          - by :user:`alice`. (:pr:`2783`)
        """)

    result = render_rst(changelog, ReleaseContext(tag="20.27.0", repository="pypa/virtualenv"))

    assert result == (
        '<a name="release-20-27-0-packaging"></a>\n\n### Packaging\n\n'
        "- Upgrade embedded wheels:\n\n"
        "  - setuptools to `75.2.0`\n"
        "  - Removed pip of `24.0`\n\n"
        "  by @alice. ([#2783](https://github.com/pypa/virtualenv/pull/2783))\n\n"
        "[Full Changelog](https://github.com/pypa/virtualenv/commits/20.27.0)\n"
    )


@pytest.mark.parametrize(
    ("source", "message"),
    [
        pytest.param(".. code-block:: console\n\n    output\n", "code block outside", id="top-level-code"),
        pytest.param("- Entry.\n\n  .. code-block:: console\n", "empty RST directive", id="empty-code"),
        pytest.param("  - Nested entry.\n", "release item outside", id="orphan-nested-item"),
        pytest.param("- Entry.\n\n.. note::\n", "unexpected release text", id="unknown-directive"),
    ],
)
def test_render_rst_rejects_malformed_blocks(source: str, message: str) -> None:
    changelog = f"1.2.3 (today)\n=============\n\nAdded\n-----\n\n{source}"

    with pytest.raises(ValueError, match=message):
        render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))


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
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
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
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


def test_render_rst_keeps_indented_version_shaped_text() -> None:
    changelog = dedent("""\
        1.2.3 (2026-10-18)
        ==================

        Added
        -----

        - Support Python
          3.14 (free-threaded)
          builds.
        - Keep the second change.

        1.2.2 (2026-10-17)
        ==================
        """)

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "3.14 (free-threaded) builds." in result
    assert "Keep the second change." in result


def test_render_rst_preserves_legacy_other_changes() -> None:
    changelog = "1.2.3 (today)\n==============\n\nOther changes\n-------------\n\n- Update development tooling.\n"

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert result == (
        '<a name="release-1-2-3-other-changes"></a>\n\n'
        "### Other changes\n\n- Update development tooling.\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
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
        "[Full Changelog](https://github.com/tox-dev/example/commits/0.2)\n"
    )


@pytest.mark.parametrize(
    "tag",
    [
        pytest.param("v2.0.0a1", id="alpha"),
        pytest.param("2.0.0b1", id="beta"),
        pytest.param("1.10rc1", id="two-part-candidate"),
        pytest.param("v1.3.4rc", id="candidate-without-number"),
        pytest.param("0.10.2.0", id="four-part"),
        pytest.param("1.3.4.post1", id="postrelease"),
        pytest.param("1.3.4.dev1", id="development"),
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
        f"[Full Changelog](https://github.com/tox-dev/example/commits/{tag})\n"
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
        "[Full Changelog](https://github.com/tox-dev/example/commits/0.12.1.0)\n"
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
        "[Full Changelog](https://github.com/tox-dev/example/commits/v2.0.0a1)\n"
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

    assert result == "[Full Changelog](https://github.com/tox-dev/example/commits/v2.0.0a2)\n"


def test_render_rst_rejects_version_without_adornment() -> None:
    changelog = "1.2.3 (today)\n\nFixed\n-----\n\n- Correct a bug.\n"

    with pytest.raises(ValueError, match=r"expected one changelog section for 1\.2\.3, found 0"):
        render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))


def test_render_rst_ignores_indented_version_heading() -> None:
    changelog = "1.2.3 (today)\n=============\n\n  1.2.2 (old)\n  ===========\n"

    with pytest.raises(ValueError, match=r"expected one changelog section for 1\.2\.2, found 0"):
        render_rst(changelog, ReleaseContext(tag="1.2.2", repository="tox-dev/example"))


def test_render_rst_ignores_unadorned_version_in_body() -> None:
    changelog = dedent("""\
        1.2.3 (today)
        =============

        Fixed
        -----

        - Correct a bug.

          1.2.2 (old)

        - Correct another bug.
        """)

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "- Correct another bug." in result


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
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param("<path>", r"\<path>", id="angle-brackets"),
        pytest.param("2*3*4", r"2\*3\*4", id="asterisks"),
        pytest.param("<img src=x>", r"\<img src=x>", id="html-image"),
        pytest.param("<details>", r"\<details>", id="html-details"),
        pytest.param("~~removed~~", r"\~\~removed\~\~", id="strikethrough"),
        pytest.param("~y~", r"\~y\~", id="single-tilde"),
    ],
)
def test_render_rst_escapes_markdown_syntax(source: str, expected: str) -> None:
    changelog = f"1.2.3 (today)\n==============\n\nAdded\n-----\n\n- Show {source}.\n"

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert f"- Show {expected}." in result


def test_render_rst_rejects_escape_placeholder() -> None:
    changelog = "1.2.3 (today)\n==============\n\nAdded\n-----\n\n- Show \ue000.\n"

    with pytest.raises(ValueError, match="private-use character reserved for escaping"):
        render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))


def test_render_rst_uses_longer_fence_for_backticks() -> None:
    changelog = dedent("""\
        1.2.3 (today)
        ==============

        Added
        -----

        - Show this example:

          .. code-block:: text

              ```
              hello
              ```
        """)

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "````text\n  ```\n  hello\n  ```\n  ````" in result


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
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


def test_render_rst_preserves_inline_literal_spaces() -> None:
    changelog = "1.2.3 (today)\n==============\n\nFixed\n-----\n\n- Keep ``a  b`` valid across\n  wrapped prose.\n"

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "- Keep `a  b` valid across wrapped prose." in result


def test_render_rst_normalizes_spaces_between_literals() -> None:
    changelog = "1.2.3 (today)\n==============\n\nFixed\n-----\n\n- Keep ``a``  ``b`` valid.\n"

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "- Keep `a` `b` valid." in result


def test_render_rst_preserves_literal_html_entity() -> None:
    changelog = "1.2.3 (today)\n==============\n\nFixed\n-----\n\n- Print literal &copy; in HTML.\n"

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert r"- Print literal \&copy; in HTML." in result


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "Type ``:ivar:``, ``:cvar:`` and ``:var:`` fields",
            "Type `:ivar:`, `:cvar:` and `:var:` fields",
            id="rst-inline-literals",
        ),
        pytest.param(
            "Use `:rtype:` and `:return:` fields",
            "Use `:rtype:` and `:return:` fields",
            id="single-backtick-literals",
        ),
        pytest.param(
            "Merge into ``:returns:`` beside :class:`the field <package.Field>`",
            "Merge into `:returns:` beside `the field`",
            id="literal-and-role",
        ),
    ],
)
def test_render_rst_preserves_field_literals(source: str, expected: str) -> None:
    changelog = f"1.2.3 (today)\n==============\n\nFixed\n-----\n\n- {source}.\n"

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert result == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n'
        f"- {expected}.\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


def test_render_rst_keeps_roles_inside_inline_code() -> None:
    changelog = (
        "1.2.3 (today)\n==============\n\nFixed\n-----\n\n- Document ``:pr:`` and link :pr:`43` by :user:`alice`.\n"
    )

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "Document `:pr:` and link" in result
    assert "[#43](https://github.com/tox-dev/example/pull/43) by @alice" in result


def test_render_rst_rejects_file_inclusion() -> None:
    changelog = "1.2.3 (today)\n==============\n\nAdded\n-----\n\n.. include:: /etc/passwd\n"

    with pytest.raises(ValueError, match="unexpected release text"):
        render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))


@pytest.mark.parametrize(
    ("role", "message"),
    [
        pytest.param(":PEP:`bad`", "invalid PEP number", id="pep"),
        pytest.param(":pr:`wrong`", "invalid pr number", id="pull-request"),
    ],
)
def test_render_rst_rejects_invalid_numeric_role(role: str, message: str) -> None:
    changelog = f"1.2.3 (today)\n==============\n\nFixed\n-----\n\n- Link {role}.\n"

    with pytest.raises(ValueError, match=message):
        render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))


def test_render_rst_keeps_duplicate_reference_labels() -> None:
    changelog = (
        "1.2.3 (today)\n==============\n\nAdded\n-----\n\n"
        "- First `#42 <https://github.com/tox-dev/example/issues/42>`_.\n\n"
        "Fixed\n-----\n\n- Second `#42 <https://github.com/tox-dev/example/issues/42>`_.\n"
    )

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert result == (
        '<a name="release-1-2-3-added"></a>\n\n### Features\n\n'
        "- First [#42](https://github.com/tox-dev/example/issues/42).\n\n"
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n'
        "- Second [#42](https://github.com/tox-dev/example/issues/42).\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


def test_render_rst_escapes_link_destinations() -> None:
    changelog = "1.2.3 (today)\n==============\n\nAdded\n-----\n\n- Read `the guide <https://example.org/a)b~c>`_.\n"

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "[the guide](https://example.org/a%29b%7Ec)" in result


def test_render_rst_rejects_nested_warning() -> None:
    changelog = (
        "1.2.3 (today)\n==============\n\nAdded\n-----\n\n- Add a feature.\n\n  .. warning::\n\n     A caveat.\n"
    )

    with pytest.raises(TypeError, match="unexpected release text: warning"):
        render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))


def test_render_rst_rejects_warning_only_item() -> None:
    changelog = "1.2.3 (today)\n==============\n\nAdded\n-----\n\n- .. warning::\n\n     A caveat.\n"

    with pytest.raises(TypeError, match="unexpected release text: warning"):
        render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))


def test_render_rst_keeps_bare_url() -> None:
    changelog = "1.2.3 (today)\n==============\n\nAdded\n-----\n\n- See https://example.org/guide.\n"

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "- See https://example.org/guide." in result


def test_render_rst_keeps_internal_reference_label() -> None:
    changelog = "1.2.3 (today)\n==============\n\n.. _detail:\n\nAdded\n-----\n\n- See detail_.\n"

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "- See detail." in result


def test_render_rst_keeps_inline_emphasis() -> None:
    changelog = "1.2.3 (today)\n==============\n\nAdded\n-----\n\n- *Read* the **new** guide.\n"

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert "- *Read* the **new** guide." in result


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        pytest.param(":PEP:`751`", "[PEP 751](https://peps.python.org/pep-0751/)", id="pep"),
        pytest.param(
            ":PEP:`517#in-tree-build-backends`",
            "[PEP 517](https://peps.python.org/pep-0517/#in-tree-build-backends)",
            id="section",
        ),
    ],
)
def test_render_rst_links_pep_role(role: str, expected: str) -> None:
    changelog = f"1.2.3 (today)\n==============\n\nAdded\n-----\n\n- Support {role}.\n"

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert result == (
        '<a name="release-1-2-3-added"></a>\n\n### Features\n\n'
        f"- Support {expected}.\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


def test_render_rst_keeps_issue_role_as_issue() -> None:
    changelog = "1.2.3 (today)\n==============\n\nFixed\n-----\n\n- Fix a bug (:issue:`5`).\n"
    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))
    assert "[#5](https://github.com/tox-dev/example/issues/5)" in result


@pytest.mark.parametrize(
    ("changelog", "format_name"),
    [
        pytest.param("## 1.2.3 (today)\n", "markdown", id="markdown"),
        pytest.param("1.2.3 (today)\n==============\n", "rst", id="rst"),
    ],
)
def test_render_empty_release_section_has_comparison_link(changelog: str, format_name: str) -> None:
    context = ReleaseContext(
        tag="1.2.3", repository="tox-dev/example", artifact_url="https://pypi.org/project/example/1.2.3/"
    )

    result = (render_markdown if format_name == "markdown" else render_rst)(changelog, context)

    assert result == (
        "[PyPI release](https://pypi.org/project/example/1.2.3/)\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


def test_render_rst_omits_empty_category() -> None:
    changelog = "1.2.3 (today)\n==============\n\nAdded\n-----\n\nFixed\n-----\n\n- Correct a bug.\n"
    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))
    assert result == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n- Correct a bug.\n\n'
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


@pytest.mark.parametrize(
    "comparison",
    [
        pytest.param("**Full Changelog**: https://github.com/tox-dev/example/compare/old...1.2.3", id="bold"),
        pytest.param("Full Changelog: https://github.com/tox-dev/example/compare/old...1.2.3", id="plain"),
        pytest.param("`Full Changelog <https://github.com/tox-dev/example/compare/old...1.2.3>`__", id="rst-link"),
    ],
)
def test_render_rst_replaces_source_comparison(comparison: str) -> None:
    changelog = f"1.2.3 (today)\n==============\n\nFixed\n-----\n\n- Correct a bug.\n\n{comparison}\n"

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example", previous="1.2.2"))

    assert result == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Bug fixes\n\n- Correct a bug.\n\n'
        "[Full Changelog](https://github.com/tox-dev/example/compare/1.2.2...1.2.3)\n"
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
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


@pytest.mark.parametrize(
    ("changelog", "message"),
    [
        pytest.param("", "found 0", id="absent"),
        pytest.param("1.2.3 (today)\n======\n1.2.3 (today)\n======\n", "found 2", id="duplicate"),
        pytest.param("1.2.3 (today)\n======\n- Entry.\n", "outside a category", id="uncategorized"),
        pytest.param("1.2.3 (today)\n======\nAn orphan paragraph.\n", "unexpected release text", id="orphan"),
        pytest.param(
            "1.2.3 (today)\n======\nUnsupported\n-----------\n",
            "unknown changelog category",
            id="unknown-category",
        ),
    ],
)
def test_render_rst_rejects_invalid_input(changelog: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))


@pytest.mark.parametrize(
    ("changelog", "overrides", "message"),
    [
        pytest.param("## 1.2.3 (today)\n", {"tag": "bad//tag"}, "invalid release tag", id="tag"),
        pytest.param("## 1.2.3 (today)\n", {"previous": "bad//tag"}, "invalid previous tag", id="previous"),
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


def test_render_markdown_keeps_new_contributors_section() -> None:
    changelog = dedent("""\
        ## 1.2.3 (today)

        ### Added

        - Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).

        ### New Contributors

        - [@alice](https://github.com/alice) made their first contribution in [#42](https://github.com/tox-dev/example/pull/42)
        """)

    result = render_markdown(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert result == (
        "### Features\n\n"
        "- Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n\n"
        "### New Contributors\n\n"
        "- [@alice](https://github.com/alice) made their first contribution in "
        "[#42](https://github.com/tox-dev/example/pull/42)\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )


def test_render_rst_keeps_new_contributors_section() -> None:
    changelog = dedent("""\
        1.2.3 (today)
        =============

        Added
        -----

        - Add a feature (:pr:`42`) by :user:`alice`.

        New Contributors
        ----------------

        - :user:`alice` made their first contribution in :pr:`42`
        """)

    result = render_rst(changelog, ReleaseContext(tag="1.2.3", repository="tox-dev/example"))

    assert result == (
        '<a name="release-1-2-3-added"></a>\n\n'
        "### Features\n\n"
        "- Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) by @alice.\n\n"
        '<a name="release-1-2-3-new-contributors"></a>\n\n'
        "### New Contributors\n\n"
        "- @alice made their first contribution in [#42](https://github.com/tox-dev/example/pull/42)\n\n"
        "[Full Changelog](https://github.com/tox-dev/example/commits/1.2.3)\n"
    )

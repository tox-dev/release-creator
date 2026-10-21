"""Assembled Markdown anchor tests."""

import pytest

from release_creator.anchors.markdown import add_release_anchors


def test_add_release_anchors_repairs_knope_insertion() -> None:
    changelog = (
        "# Changelog\n\n"
        '<a name="release-2026-1010-0"></a>\n\n'
        "## 2026.1021.0 (2026-10-21)\n\n"
        "### Fixed\n\n- Fix an icon.\n\n"
        "### Security\n\n- Remove a distrusted root.\n\n"
        "## 2026.1010.0 (2026-10-10)\n\n"
        '<a name="release-2026-1010-0-added"></a>\n\n'
        "### Added\n\n- Support Python 3.15.\n"
    )

    result = add_release_anchors(changelog)

    assert result == (
        "# Changelog\n\n"
        '<a name="release-2026-1021-0"></a>\n\n'
        "## 2026.1021.0 (2026-10-21)\n\n"
        '<a name="release-2026-1021-0-fixed"></a>\n\n'
        "### Fixed\n\n- Fix an icon.\n\n"
        '<a name="release-2026-1021-0-security"></a>\n\n'
        "### Security\n\n- Remove a distrusted root.\n\n"
        '<a name="release-2026-1010-0"></a>\n\n'
        "## 2026.1010.0 (2026-10-10)\n\n"
        '<a name="release-2026-1010-0-added"></a>\n\n'
        "### Added\n\n- Support Python 3.15.\n"
    )


def test_add_release_anchors_is_repeatable() -> None:
    changelog = "## 2026.1021.0\n\n### Fixed\n\n- Fix an icon.\n"

    result = add_release_anchors(changelog)

    assert add_release_anchors(result) == result


def test_add_release_anchors_preserves_other_anchors() -> None:
    changelog = '<a name="custom-intro"></a>\n\n## 2026.1021.0\n'

    assert add_release_anchors(changelog) == (
        '<a name="custom-intro"></a>\n\n<a name="release-2026-1021-0"></a>\n\n## 2026.1021.0\n'
    )


def test_add_release_anchors_requires_release_heading() -> None:
    with pytest.raises(ValueError, match="no Markdown release headings"):
        add_release_anchors("# Changelog\n")


@pytest.mark.parametrize(
    ("changelog", "expected"),
    [
        pytest.param(
            '## 2026.1021.0\n<a name="release-2026-1021-0"></a>\n',
            '<a name="release-2026-1021-0"></a>\n\n## 2026.1021.0\n',
            id="trailing-anchor",
        ),
        pytest.param(
            '<a name="release-2026-1021-0"></a>\n## 2026.1021.0\n',
            '<a name="release-2026-1021-0"></a>\n\n## 2026.1021.0\n',
            id="adjacent-anchor",
        ),
        pytest.param(
            "# Changelog\n## 2026.1021.0\n",
            '# Changelog\n\n<a name="release-2026-1021-0"></a>\n\n## 2026.1021.0\n',
            id="missing-spacing",
        ),
    ],
)
def test_add_release_anchors_normalizes_anchor_spacing(changelog: str, expected: str) -> None:
    assert add_release_anchors(changelog) == expected

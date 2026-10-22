"""Package changelog previews."""

from typing import TYPE_CHECKING

import pytest

from release_creator.changelog.preview import render_preview

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def changelog(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    path = source / "CHANGELOG.md"
    path.write_text(
        "# Changelog\n\n"
        "## pyproject-fmt\n\n"
        "### 2.30.3 (2026-10-10)\n\n"
        '<a name="release-pyproject-fmt-2-30-3"></a>\n\n'
        "#### Added\n\n"
        "- Require Python 3.11.\n\n"
        "## tox-toml-fmt\n\n"
        "### 1.11.1 (2026-10-10)\n\n"
        "#### Fixed\n\n"
        "- Preserve TOML comments.\n",
        encoding="utf-8",
    )
    return path


def test_render_preview_selects_package_and_adds_draft(changelog: Path, tmp_path: Path) -> None:
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    (fragments / "+next.feature.md").write_text("Support Python 3.15.\n", encoding="utf-8")
    (fragments / "481.bugfix.md").write_text("Keep trailing comments\nwhen formatting.\n", encoding="utf-8")
    original = changelog.read_bytes()

    result = render_preview(changelog, "pyproject-fmt", fragments)

    assert result == (
        "# Changelog\n\n## pyproject-fmt\n\n"
        '<a name="draft-pyproject-fmt"></a>\n\n'
        "### Draft\n\n"
        '<a name="draft-pyproject-fmt-added"></a>\n\n'
        "#### Added\n\n- Support Python 3.15.\n\n"
        '<a name="draft-pyproject-fmt-fixed"></a>\n\n'
        "#### Fixed\n\n- Keep trailing comments when formatting.\n\n"
        "### 2.30.3 (2026-10-10)\n\n"
        '<a name="release-pyproject-fmt-2-30-3"></a>\n\n'
        "#### Added\n\n- Require Python 3.11.\n"
    )
    assert changelog.read_bytes() == original
    assert sorted(path.name for path in fragments.iterdir()) == ["+next.feature.md", "481.bugfix.md"]


def test_render_preview_omits_empty_draft(changelog: Path, tmp_path: Path) -> None:
    result = render_preview(changelog, "tox-toml-fmt", tmp_path)

    assert result == (
        "# Changelog\n\n## tox-toml-fmt\n\n### 1.11.1 (2026-10-10)\n\n#### Fixed\n\n- Preserve TOML comments.\n"
    )


def test_render_preview_supports_first_draft(changelog: Path, tmp_path: Path) -> None:
    changelog.write_text("# Changelog\n\n## pyproject-fmt\n", encoding="utf-8")
    (tmp_path / "+first.feature.1.md").write_text("First release.\n", encoding="utf-8")

    result = render_preview(changelog, "pyproject-fmt", tmp_path)

    assert result.endswith('### Draft\n\n<a name="draft-pyproject-fmt-added"></a>\n\n#### Added\n\n- First release.\n')


@pytest.mark.parametrize(
    ("package", "source", "error"),
    [
        pytest.param("", "## pyproject-fmt\n", "invalid package", id="empty-package"),
        pytest.param("../other", "## pyproject-fmt\n", "invalid package", id="path-package"),
        pytest.param("missing", "## pyproject-fmt\n", "found 0", id="missing-package"),
        pytest.param("pyproject-fmt", "## pyproject-fmt\n\n## pyproject-fmt\n", "found 2", id="duplicate-package"),
    ],
)
def test_render_preview_rejects_package(package: str, source: str, error: str, changelog: Path, tmp_path: Path) -> None:
    changelog.write_text(source, encoding="utf-8")

    with pytest.raises(ValueError, match=error):
        render_preview(changelog, package, tmp_path)


@pytest.mark.parametrize(
    ("filename", "content", "error"),
    [
        pytest.param("missing.feature.md", "Valid.\n", "invalid changelog fragment", id="unprefixed-name"),
        pytest.param("+name.other.md", "Valid.\n", "invalid changelog fragment", id="unknown-category"),
        pytest.param("+name.feature.md", " \n", "one nonempty paragraph", id="empty"),
        pytest.param("+name.feature.md", "First.\n\nSecond.\n", "one nonempty paragraph", id="two-paragraphs"),
        pytest.param("+name.feature.md", "- Already a bullet.\n", "one nonempty paragraph", id="bullet"),
        pytest.param("+name.feature.md", "# Heading\n", "one nonempty paragraph", id="heading"),
    ],
)
def test_render_preview_rejects_bad_fragment(
    filename: str, content: str, error: str, changelog: Path, tmp_path: Path
) -> None:
    (tmp_path / filename).write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match=error):
        render_preview(changelog, "pyproject-fmt", tmp_path)


def test_render_preview_ignores_non_markdown(changelog: Path, tmp_path: Path) -> None:
    (tmp_path / ".gitkeep").write_text("", encoding="utf-8")
    (tmp_path / "+later.feature.rst").write_text("RST fragment.\n", encoding="utf-8")

    result = render_preview(changelog, "pyproject-fmt", tmp_path)

    assert "Draft" not in result

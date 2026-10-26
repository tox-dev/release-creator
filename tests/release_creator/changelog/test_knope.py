"""Knope changelog draft previews."""

from typing import TYPE_CHECKING

import pytest

from release_creator.changelog.knope import render_knope_preview

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def knope_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        '# Changelog\n\nIntro.\n\n<a name="release-2026-1010-0"></a>\n\n## 2026.1010.0\n\n### Added\n\n- Old.\n',
        encoding="utf-8",
    )
    config = tmp_path / "knope.toml"
    config.write_text(
        '[package]\nextra_changelog_sections = [\n  { name = "Added", types = ["minor"] },\n'
        '  { name = "Security", types = ["security"] },\n]\n',
        encoding="utf-8",
    )
    fragments = tmp_path / ".changeset"
    fragments.mkdir()
    return changelog, config, fragments


def test_render_knope_preview_adds_draft_without_mutation(knope_files: tuple[Path, Path, Path]) -> None:
    changelog, config, fragments = knope_files
    (fragments / "trust-roots.md").write_text(
        "---\ndefault: security\n---\n\n# Remove a distrusted root\n\nKeep the old root in history.\n",
        encoding="utf-8",
    )
    (fragments / "python.md").write_text("---\ndefault: minor\n---\n\n# Support Python 3.15\n", encoding="utf-8")
    original = changelog.read_bytes()

    result = render_knope_preview(changelog, config, fragments)

    assert result == (
        '# Changelog\n\nIntro.\n\n<a name="draft"></a>\n\n## Draft\n\n'
        '<a name="draft-added"></a>\n\n### Added\n\n- Support Python 3.15\n\n'
        '<a name="draft-security"></a>\n\n### Security\n\n'
        "- Remove a distrusted root\n\n  Keep the old root in history.\n\n"
        '<a name="release-2026-1010-0"></a>\n\n## 2026.1010.0\n\n### Added\n\n- Old.\n'
    )
    assert changelog.read_bytes() == original
    assert sorted(path.name for path in fragments.iterdir()) == ["python.md", "trust-roots.md"]


def test_render_knope_preview_omits_empty_draft(knope_files: tuple[Path, Path, Path]) -> None:
    changelog, config, fragments = knope_files

    result = render_knope_preview(changelog, config, fragments)

    assert result == changelog.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("content", "error"),
    [
        pytest.param("# Missing front matter\n", "missing YAML front matter", id="missing-frontmatter"),
        pytest.param("---\n[]\n---\n\n# Summary\n", "empty changeset front matter", id="nonmapping-frontmatter"),
        pytest.param("---\ndefault: [\n---\n\n# Summary\n", "invalid changeset front matter", id="invalid-yaml"),
        pytest.param("---\ndefault: bogus\n---\n\n# Summary\n", "unsupported changeset type", id="bad-type"),
        pytest.param("---\ndefault: security\n---\n\n# \n", "empty changeset summary", id="empty-summary"),
    ],
)
def test_render_knope_preview_rejects_bad_changeset(
    content: str, error: str, knope_files: tuple[Path, Path, Path]
) -> None:
    changelog, config, fragments = knope_files
    (fragments / "news.md").write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match=error):
        render_knope_preview(changelog, config, fragments)


def test_render_knope_preview_handles_first_release(knope_files: tuple[Path, Path, Path]) -> None:
    changelog, config, fragments = knope_files
    changelog.write_text("# Changelog\n\nIntro.\n", encoding="utf-8")
    (fragments / "first.md").write_text("---\ndefault: minor\n---\n\n# First release\n", encoding="utf-8")

    result = render_knope_preview(changelog, config, fragments)

    assert result == (
        '# Changelog\n\nIntro.\n\n<a name="draft"></a>\n\n## Draft\n\n'
        '<a name="draft-added"></a>\n\n### Added\n\n- First release\n'
    )


def test_render_knope_preview_accepts_standard_types_without_custom_sections(
    knope_files: tuple[Path, Path, Path],
) -> None:
    changelog, config, fragments = knope_files
    config.write_text("[package]\n", encoding="utf-8")
    (fragments / "fix.md").write_text("---\ndefault: patch\n---\n\n# Fix command output\n", encoding="utf-8")

    result = render_knope_preview(changelog, config, fragments)

    assert '<a name="draft-fixed"></a>\n\n### Fixed\n\n- Fix command output\n' in result


def test_render_knope_preview_accepts_single_named_package(knope_files: tuple[Path, Path, Path]) -> None:
    changelog, config, fragments = knope_files
    config.write_text("[packages.fixture]\n", encoding="utf-8")
    (fragments / "fix.md").write_text("---\nfixture: patch\n---\n\n# Fix command output\n", encoding="utf-8")

    assert "### Fixed\n\n- Fix command output" in render_knope_preview(changelog, config, fragments)

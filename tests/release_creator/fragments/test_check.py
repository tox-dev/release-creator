"""Check pull request news against real Git history."""

import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Exercise the public command in a real repository.
import sys
lazy from pathlib import Path

import pytest
lazy from pytest_mock import MockerFixture

from release_creator.cli import main
from release_creator.fragments.check import changed_changesets, changed_fragments, validate_fragment_deletions


def _git(*args: str) -> None:
    git = shutil.which("git")
    assert git is not None
    subprocess.run([git, *args], check=True)  # ruff: ignore[subprocess-without-shell-equals-true]  # Git fixture.


@pytest.fixture
def news_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "changelog.d").mkdir()
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.towncrier]\ndirectory = "changelog.d"\nfilename = "CHANGELOG.md"\n'
        'type = [{ directory = "feature", name = "Added" }]\n',
        encoding="utf-8",
    )
    _git("init", "-qb", "main", str(tmp_path))
    _git("-C", str(tmp_path), "add", ".")
    _git("-C", str(tmp_path), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Initial")
    _git("-C", str(tmp_path), "update-ref", "refs/remotes/origin/main", "HEAD")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    ("filename", "content", "count", "error"),
    [
        pytest.param("+topic.feature.md", "Add a feature.\n", 1, "", id="named"),
        pytest.param(
            "+topic.feature.md",
            "- Add a feature.\n",
            0,
            "fragment must be prose",
            id="nested-towncrier-bullet",
        ),
        pytest.param(
            "+topic.feature.md",
            "> Add a feature.\n",
            0,
            "fragment must be prose",
            id="nested-towncrier-quote",
        ),
        pytest.param(
            "+topic.feature.md",
            "Add a feature.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n",
            0,
            "fragment must be prose",
            id="towncrier-table",
        ),
        pytest.param("+topic.feature.md", "<!-- hidden -->\n", 0, "fragment must be prose", id="comment-only"),
        pytest.param("+topic.feature.md", "---\n", 0, "fragment must be prose", id="thematic-only"),
        pytest.param("+topic.feature.md", "<div>Hidden</div>\n", 0, "fragment must be prose", id="html-only"),
        pytest.param(
            "+topic.feature.md",
            "Add <code>by [@mallory](https://github.com/mallory).\n",
            0,
            "unclosed HTML literal element",
            id="unclosed-html-literal",
        ),
        pytest.param("42.feature.md", "Add a feature.\n", 1, "", id="numbered"),
        pytest.param("+topic.feature.1.md", "Add a feature.\n", 1, "", id="multiple-entries"),
        pytest.param("42.feature.2.md", "Add a feature.\n", 1, "", id="numbered-counter"),
        pytest.param("+topic.doc.md", "Add a feature.\n", 0, "unsupported changelog fragment", id="category"),
        pytest.param("topic.feature.md", "Add a feature.\n", 0, "unsupported changelog fragment", id="name"),
        pytest.param("+topic.feature.md", " \n", 0, "empty changelog fragment", id="empty"),
        pytest.param("README.md", "Read me.\n", 0, "", id="outside-directory"),
        pytest.param("nested/+topic.feature.md", "Nested.\n", 0, "", id="nested-directory"),
        pytest.param("notes.txt", "Other file.\n", 0, "unsupported changelog fragment", id="other-extension"),
        pytest.param("README.rst", "Fragment guide.\n", 0, "", id="fragment-guide"),
        pytest.param("+topic.feature.md~", "Editor backup.\n", 0, "", id="editor-backup"),
        pytest.param(".keep", "", 0, "", id="directory-marker"),
        pytest.param("+.md", "Uncategorized.\n", 0, "unsupported changelog fragment", id="incomplete-name"),
        pytest.param(
            "+topic.feature", "Add a feature.\n", 0, "unsupported changelog fragment extension", id="no-suffix"
        ),
        pytest.param(
            "+topic.feature.md.bak",
            "Add a feature.\n",
            0,
            "unsupported changelog fragment extension",
            id="extra-suffix",
        ),
        pytest.param(
            "+topic.feature.rst",
            "Add a feature.\n",
            0,
            "unsupported changelog fragment extension",
            id="wrong-extension",
        ),
    ],
)
def test_changed_fragments(news_repository: Path, filename: str, content: str, count: int, error: str) -> None:
    destination = news_repository / (filename if filename == "README.md" else f"changelog.d/{filename}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    _git("add", "-f", str(destination))
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Change")

    if error:
        with pytest.raises(ValueError, match=error):
            changed_fragments(news_repository / "pyproject.toml", "main")
    else:
        assert changed_fragments(news_repository / "pyproject.toml", "main") == count


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("Fix A.\n\n  - subdetail\n", id="nested-list"),
        pytest.param("Fix A.\n\n.. raw:: html\n\n   <b>x</b>\n", id="raw-directive"),
        pytest.param("Fix A.\n\nDetails\n=======\n", id="section"),
        pytest.param("=== ===\nA   B\n=== ===\n1   2\n=== ===\n", id="table"),
        pytest.param("Fix A.\n\n.. hidden comment\n\nMore detail.\n", id="embedded-comment"),
        pytest.param(".. hidden comment\n", id="comment-only"),
    ],
)
def test_changed_fragments_rejects_rst_structure(news_repository: Path, content: str) -> None:
    config = news_repository / "pyproject.toml"
    config.write_text(config.read_text().replace("CHANGELOG.md", "CHANGELOG.rst"), encoding="utf-8")
    fragment = news_repository / "changelog.d/+topic.feature.rst"
    fragment.write_text(content, encoding="utf-8")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Change")

    with pytest.raises(ValueError, match="fragment must be prose"):
        changed_fragments(config, "main")

    assert fragment.read_text() == content


@pytest.mark.parametrize(
    ("suffix", "content", "error"),
    [
        pytest.param(
            ".md", "Add a feature by [@alice](https://github.com/alice).\n", "author credit", id="markdown-credit"
        ),
        pytest.param(
            ".md",
            "Add a feature by **[@alice](https://github.com/alice)**.\n",
            "author credit",
            id="markdown-emphasized-credit",
        ),
        pytest.param(
            ".md",
            "Add a feature ([#5](https://github.com/tox-dev/example/pull/5)).\n",
            "pull request link",
            id="markdown-pull-link",
        ),
        pytest.param(
            ".md",
            "Add a feature, see https://github.com/other/example/pull/5.\n",
            "pull request link",
            id="markdown-pull-url",
        ),
        pytest.param(".md", "Add a feature :pr:`5`.\n", "pull request link", id="markdown-pr-role"),
        pytest.param(".md", "Add `by [@alice](https://github.com/alice)` syntax.\n", "", id="markdown-code-credit"),
        pytest.param(".md", "Fix [#5](https://github.com/tox-dev/example/issues/5).\n", "", id="markdown-issue-link"),
        pytest.param(".rst", "Add a feature by :user:`alice`.\n", "author credit", id="rst-user-role"),
        pytest.param(
            ".rst",
            "Add a feature by `@alice <https://github.com/alice>`_.\n",
            "author credit",
            id="rst-profile-link",
        ),
        pytest.param(".rst", "Add a feature :pr:`5`.\n", "pull request link", id="rst-pr-role"),
        pytest.param(".rst", "Add a feature :pull:`5`.\n", "pull request link", id="rst-pull-role"),
        pytest.param(
            ".rst",
            "Add a feature, see https://github.com/tox-dev/example/pull/5.\n",
            "pull request link",
            id="rst-pull-url",
        ),
        pytest.param(".rst", "Document ``by :user:`alice` and :pr:`5``` roles.\n", "", id="rst-literal"),
        pytest.param(".rst", "Fix :issue:`5`.\n", "", id="rst-issue-role"),
    ],
)
def test_changed_fragments_rejects_hand_written_attribution(
    news_repository: Path, suffix: str, content: str, error: str
) -> None:
    config = news_repository / "pyproject.toml"
    config.write_text(config.read_text().replace("CHANGELOG.md", f"CHANGELOG{suffix}"), encoding="utf-8")
    (news_repository / f"changelog.d/+topic.feature{suffix}").write_text(content, encoding="utf-8")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Change")

    if error:
        with pytest.raises(ValueError, match=f"hand-written {error} in changelog fragment"):
            changed_fragments(config, "main")
    else:
        assert changed_fragments(config, "main") == 1


def test_changed_fragments_ignores_towncrier_template(news_repository: Path) -> None:
    config = news_repository / "pyproject.toml"
    config.write_text(config.read_text() + 'template = "changelog.d/template.jinja2"\n')
    (news_repository / "changelog.d/template.jinja2").write_text("{{ version }}\n")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Add template")

    assert changed_fragments(config, "main") == 0


def test_changed_fragments_rejects_renamed_extension(news_repository: Path) -> None:
    source = news_repository / "changelog.d/+topic.feature.md"
    source.write_text("Add a feature.\n")
    _git("add", str(source))
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Add news")
    _git("update-ref", "refs/remotes/origin/main", "HEAD")
    _git("mv", str(source), str(source.with_suffix(".rst")))
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Rename news")

    with pytest.raises(ValueError, match="unsupported changelog fragment extension"):
        changed_fragments(news_repository / "pyproject.toml", "main")


def test_changed_fragments_reports_missing_repository_root(news_repository: Path, mocker: MockerFixture) -> None:
    (news_repository / "changelog.d/+topic.feature.md").write_text("Add a feature.\n")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        side_effect=[
            subprocess.CompletedProcess([], 0, "changelog.d/+topic.feature.md\0", ""),
            subprocess.CompletedProcess([], 1, "", "no root"),
        ],
    )

    with pytest.raises(ValueError, match="no root"):
        changed_fragments(news_repository / "pyproject.toml", "main")


@pytest.mark.parametrize(
    ("base", "filename"),
    [
        pytest.param("", "CHANGELOG.md", id="missing-base"),
        pytest.param("main", "CHANGELOG.txt", id="unsupported-format"),
    ],
)
def test_changed_fragments_rejects_invalid_context(news_repository: Path, base: str, filename: str) -> None:
    config = news_repository / "pyproject.toml"
    config.write_text(config.read_text(encoding="utf-8").replace("CHANGELOG.md", filename), encoding="utf-8")

    with pytest.raises(ValueError, match="news validation needs a PR base"):
        changed_fragments(config, base)


def test_changed_fragments_reads_towncrier_tables(news_repository: Path) -> None:
    (news_repository / "towncrier.toml").write_text(
        '[tool.towncrier]\ndirectory = "changelog.d"\nfilename = "CHANGELOG.md"\n'
        '[tool.towncrier.fragment.change]\nname = "Changes"\n',
        encoding="utf-8",
    )
    (news_repository / "changelog.d" / "+topic.change.2.md").write_text("Change behavior.\n", encoding="utf-8")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Change")

    assert changed_fragments(news_repository / "pyproject.toml", "main") == 1


def test_changed_fragments_uses_towncrier_defaults(news_repository: Path) -> None:
    (news_repository / "pyproject.toml").write_text('[tool.towncrier]\nname = "fixture"\n', encoding="utf-8")
    (news_repository / "NEWS.rst").write_text("News\n====\n", encoding="utf-8")
    directory = news_repository / "newsfragments"
    directory.mkdir()
    (directory / "42.feature.rst").write_text("Add defaults.\n", encoding="utf-8")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Change")

    assert changed_fragments(news_repository / "pyproject.toml", "main") == 1


def test_changed_fragments_rejects_missing_towncrier_table(news_repository: Path) -> None:
    (news_repository / "pyproject.toml").write_text('[project]\nname = "fixture"\n', encoding="utf-8")

    with pytest.raises(ValueError, match=r"missing \[tool.towncrier\]"):
        changed_fragments(news_repository / "pyproject.toml", "main")


@pytest.mark.parametrize(
    ("addition", "message"),
    [
        pytest.param('package = "fixture"\n', "explicit Towncrier fragment directory", id="package-default"),
        pytest.param('[[tool.towncrier.section]]\npath = "core"\n', "sections are not supported", id="sections"),
    ],
)
def test_changed_fragments_rejects_unsupported_towncrier_layout(
    news_repository: Path, addition: str, message: str
) -> None:
    config = news_repository / "pyproject.toml"
    source = config.read_text(encoding="utf-8")
    if addition.startswith("package"):
        source = source.replace('directory = "changelog.d"\n', "")
    config.write_text(f"{source}{addition}", encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        changed_fragments(config, "main")


def test_changed_fragments_from_subdirectory(news_repository: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = news_repository / "package"
    directory = package / "changelog.d"
    directory.mkdir(parents=True)
    (package / "pyproject.toml").write_text(
        '[tool.towncrier]\nname = "fixture"\ndirectory = "changelog.d"\n'
        'filename = "CHANGELOG.md"\ntype = [{ directory = "feature", name = "Added" }]\n',
        encoding="utf-8",
    )
    (package / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (directory / "+nested.feature.md").write_text("Add nested package.\n", encoding="utf-8")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Change")
    monkeypatch.chdir(package)

    assert changed_fragments(Path("pyproject.toml"), "main") == 1


def test_changed_fragments_rejects_towncrier_duplicate(news_repository: Path) -> None:
    for filename in ("42.feature.md", "42.feature.0.md"):
        (news_repository / "changelog.d" / filename).write_text("Add a feature.\n", encoding="utf-8")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Change")

    with pytest.raises(ValueError, match=r"multiple files for 42\.feature"):
        changed_fragments(news_repository / "pyproject.toml", "main")


@pytest.mark.parametrize(
    ("filename", "valid"),
    [
        pytest.param("+topic.feature.md", True, id="named"),
        pytest.param("42.feature.2.md", True, id="counter"),
        pytest.param("topic.feature.md", False, id="unprefixed"),
        pytest.param("42.other.md", False, id="unknown-category"),
        pytest.param("template.jinja", False, id="template"),
        pytest.param("nested/42.feature.md", False, id="nested"),
        pytest.param("42.feature.rst", False, id="wrong-extension"),
    ],
)
def test_validate_fragment_deletions(news_repository: Path, filename: str, valid: bool) -> None:
    _stage_fragment_deletion(news_repository, filename)

    if valid:
        validate_fragment_deletions(news_repository / "pyproject.toml")
    else:
        with pytest.raises(ValueError, match="unsupported release fragment"):
            validate_fragment_deletions(news_repository / "pyproject.toml")


def test_validate_fragment_deletions_reads_towncrier_toml(news_repository: Path) -> None:
    (news_repository / "towncrier.toml").write_text(
        '[tool.towncrier]\ndirectory = "changelog.d"\nfilename = "CHANGELOG.md"\n'
        '[tool.towncrier.fragment.change]\nname = "Changes"\n',
        encoding="utf-8",
    )
    _stage_fragment_deletion(news_repository, "+topic.change.2.md")

    validate_fragment_deletions(news_repository / "pyproject.toml")


def test_validate_fragment_deletions_cli(
    news_repository: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stage_fragment_deletion(news_repository, "template.jinja")
    monkeypatch.setattr(sys, "argv", ["release-creator", "validate-fragment-deletions"])

    with pytest.raises(SystemExit, match="2"):
        main()

    assert "unsupported release fragment" in capsys.readouterr().err


def _stage_fragment_deletion(repository: Path, filename: str) -> None:
    fragment = repository / "changelog.d" / filename
    fragment.parent.mkdir(parents=True, exist_ok=True)
    fragment.write_text("A change.\n", encoding="utf-8")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Add fragment")
    fragment.unlink()
    _git("add", "-u")


def test_towncrier_check_rejects_unprefixed_fragment(news_repository: Path) -> None:
    config = Path(__file__).resolve().parents[3] / "pyproject.toml"
    shutil.copyfile(config, news_repository / "pyproject.toml")
    (news_repository / "docs").mkdir()
    (news_repository / "docs" / "changelog.md").write_text("# Changelog\n", encoding="utf-8")
    (news_repository / "changelog.d" / "topic.feature.md").write_text("Add a feature.\n", encoding="utf-8")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Change")

    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # Installed CLI in a temporary repo.
        [str(Path(sys.executable).with_name("towncrier")), "check", "--compare-with", "origin/main"],
        cwd=news_repository,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 1
    assert "Issue name 'topic' does not match the configured pattern" in result.stderr


def test_changed_fragments_rejects_missing_base(news_repository: Path) -> None:
    with pytest.raises(ValueError, match="bad revision"):
        changed_fragments(news_repository / "pyproject.toml", "missing")


def test_validate_news_cli_reports_count(
    news_repository: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (news_repository / "changelog.d" / "+topic.feature.md").write_text("Add a feature.\n", encoding="utf-8")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Change")
    monkeypatch.setattr(sys, "argv", ["release-creator", "validate-news", "--base", "main"])

    main()

    assert capsys.readouterr().out == "1\n"


@pytest.mark.parametrize(
    ("content", "count", "error"),
    [
        pytest.param("---\ndefault: security\n---\n\n# Remove a distrusted root\n", 1, "", id="custom-type"),
        pytest.param("---\ndefault: patch\n---\n\n# Fix a bug\n", 1, "", id="built-in-type"),
        pytest.param("---\ndefault: patch # maintenance fix\n---\n\n# Fix a bug\n", 1, "", id="yaml-comment"),
        pytest.param("---\ndefault: unknown\n---\n\n# Fix a bug\n", 0, "unsupported changeset type", id="type"),
        pytest.param(
            "---\ndefault: [patch\n---\n\n# Fix a bug\n", 0, "invalid changeset front matter", id="invalid-yaml"
        ),
        pytest.param("---\n---\n\n# Fix a bug\n", 0, "empty changeset front matter", id="empty-front-matter"),
        pytest.param("---\ndefault: patch\n---\n\n# \n", 0, "empty changeset summary", id="empty-summary"),
        pytest.param("Fix a bug\n", 0, "missing YAML front matter", id="missing-front-matter"),
    ],
)
def test_changed_changesets(news_repository: Path, content: str, count: int, error: str) -> None:
    (news_repository / ".changeset").mkdir()
    (news_repository / "knope.toml").write_text(
        '[package]\nextra_changelog_sections = [{ name = "Security", types = ["security"] }]\n',
        encoding="utf-8",
    )
    (news_repository / ".changeset" / "trust-roots.md").write_text(content, encoding="utf-8")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Change")

    if error:
        with pytest.raises(ValueError, match=error):
            changed_changesets(news_repository / "knope.toml", "main")
    else:
        assert changed_changesets(news_repository / "knope.toml", "main") == count


def test_validate_news_cli_reports_knope_count(
    news_repository: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (news_repository / ".changeset").mkdir()
    (news_repository / "knope.toml").write_text("[package]\n", encoding="utf-8")
    (news_repository / ".changeset" / "fix.md").write_text("---\ndefault: patch\n---\n\n# Fix a bug\n")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Change")
    monkeypatch.setattr(sys, "argv", ["release-creator", "validate-news", "--format", "knope", "--base", "main"])

    main()

    assert capsys.readouterr().out == "1\n"


def test_changed_changesets_requires_base(news_repository: Path) -> None:
    with pytest.raises(ValueError, match="news validation needs a PR base"):
        changed_changesets(news_repository / "knope.toml", "")


def test_changed_changesets_skips_directory_guide(news_repository: Path) -> None:
    (news_repository / ".changeset").mkdir()
    (news_repository / "knope.toml").write_text("[package]\n", encoding="utf-8")
    (news_repository / ".changeset" / "README.md").write_text("Changeset guide.\n")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Change")

    assert changed_changesets(news_repository / "knope.toml", "main") == 0


def test_changed_changesets_accepts_single_named_package(news_repository: Path) -> None:
    (news_repository / ".changeset").mkdir()
    (news_repository / "knope.toml").write_text("[packages.fixture]\n", encoding="utf-8")
    (news_repository / ".changeset" / "fix.md").write_text("---\nfixture: patch\n---\n\n# Fix a bug\n")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Change")

    assert changed_changesets(news_repository / "knope.toml", "main") == 1


def test_changed_changesets_accepts_footer_only_section(news_repository: Path) -> None:
    (news_repository / ".changeset").mkdir()
    (news_repository / "knope.toml").write_text(
        '[package]\nextra_changelog_sections = [{ name = "Security", footers = ["Security-Note"] }]\n',
        encoding="utf-8",
    )
    (news_repository / ".changeset" / "fix.md").write_text("---\ndefault: patch\n---\n\n# Fix a bug\n")
    _git("add", ".")
    _git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "Change")

    assert changed_changesets(news_repository / "knope.toml", "main") == 1


@pytest.mark.parametrize(
    "section",
    [
        pytest.param('{ types = ["security"] }', id="missing-name"),
        pytest.param('{ name = "Security" }', id="missing-types"),
        pytest.param('{ name = "Security", footers = "Security-Note" }', id="invalid-footers"),
    ],
)
def test_changed_changesets_rejects_incomplete_section(news_repository: Path, section: str) -> None:
    (news_repository / "knope.toml").write_text(
        f"[package]\nextra_changelog_sections = [{section}]\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="Knope changelog sections need"):
        changed_changesets(news_repository / "knope.toml", "main")


@pytest.mark.parametrize(
    ("configuration", "error", "message"),
    [
        pytest.param("[other]\n", ValueError, "expected one", id="no-package"),
        pytest.param("[packages.first]\n[packages.second]\n", ValueError, "expected one", id="multiple-packages"),
        pytest.param(
            '[package]\nextra_changelog_sections = "bad"\n',
            TypeError,
            "Knope changelog sections need",
            id="sections-type",
        ),
        pytest.param(
            '[package]\nextra_changelog_sections = ["bad"]\n',
            TypeError,
            "Knope changelog sections need",
            id="section-type",
        ),
    ],
)
def test_changed_changesets_rejects_invalid_package_layout(
    news_repository: Path, configuration: str, error: type[Exception], message: str
) -> None:
    config = news_repository / "knope.toml"
    config.write_text(configuration, encoding="utf-8")

    with pytest.raises(error, match=message):
        changed_changesets(config, "main")

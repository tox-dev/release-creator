"""Towncrier template integration tests."""

import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Exercise the installed Towncrier command.
import sys
from pathlib import Path
from textwrap import dedent

import pytest

lazy from release_creator.notes.section import release_section


def _build(tmp_path: Path, changelog: str, template: str, underlines: str = "") -> str:
    (tmp_path / "changelog.d").mkdir()
    extension = Path(changelog).suffix
    (tmp_path / "changelog.d" / f"12.bugfix{extension}").write_text("Fix a numbered bug.\n")
    (tmp_path / "changelog.d" / f"+named.bugfix{extension}").write_text("Fix a named bug.\n")
    (tmp_path / changelog).write_text(
        "###########\n Changelog\n###########\n\n.. towncrier release notes start\n"
        if extension == ".rst"
        else "# Changelog\n"
    )
    (tmp_path / "pyproject.toml").write_text(
        dedent(f"""\
        [tool.towncrier]
        name = "example"
        directory = "changelog.d"
        filename = "{changelog}"
        template = "release_creator.fragments:{template}"
        title_format = false
        issue_format = "#{{issue}}"
        {underlines}
        type = [{{ directory = "bugfix", name = "Fixed", showcontent = true }}]
        """)
    )
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # Fixed command and temporary checkout.
        [str(Path(sys.executable).with_name("towncrier")), "build", "--yes", "--version", "1.2.3"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    return (tmp_path / changelog).read_text()


def test_markdown_template_anchors_release_and_category(tmp_path: Path) -> None:
    changelog = _build(tmp_path, "CHANGELOG.md", "template.jinja2")

    assert release_section(changelog, "1.2.3") == (
        '<a name="release-1-2-3-fixed"></a>\n\n### Fixed\n\n- Fix a numbered bug. (#12)\n- Fix a named bug.\n'
    )


@pytest.mark.parametrize(
    ("underlines", "category"),
    [
        pytest.param("", "Fixed\n-----", id="default"),
        pytest.param('underlines = ["*", "=", "-"]', "Fixed\n=====", id="overline"),
        pytest.param('underlines = ["-", "~"]', "Fixed\n~~~~~", id="dash"),
    ],
)
def test_rst_template_anchors_release_and_category(tmp_path: Path, underlines: str, category: str) -> None:
    changelog = _build(tmp_path, "changelog.rst", "template.rst.jinja2", underlines)

    assert release_section(changelog, "1.2.3", rst=True) == (
        f".. _release-1-2-3-fixed:\n\n{category}\n\n- Fix a numbered bug. (#12)\n- Fix a named bug.\n"
    )

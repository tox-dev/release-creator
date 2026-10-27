"""Package sections whose version anchor follows the version heading, as toml-fmt's CHANGELOG.md writes them."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING, Final

from release_creator.contributors.section import add_new_contributors
from release_creator.notes.render import ReleaseContext, render_markdown

if TYPE_CHECKING:
    from pathlib import Path

    from tests.release_creator.contributors.conftest import GitHub

_CHANGELOG: Final = dedent("""\
    # Changelog

    ## pyproject-fmt

    ### 2.30.3 (2026-10-10)

    <a name="release-pyproject-fmt-2-30-3"></a>

    <a name="release-pyproject-fmt-2-30-3-added"></a>

    #### Added

    - **Require 3.11 and default to 3.15.** ([#480](https://github.com/tox-dev/toml-fmt/pull/480)) by
      [@gaborbernat](https://github.com/gaborbernat).

    ### 2.30.2 (2026-10-09)

    <a name="release-pyproject-fmt-2-30-2"></a>

    <a name="release-pyproject-fmt-2-30-2-fixed"></a>

    #### Fixed

    - **Format every input after an earlier one changes.** ([#479](https://github.com/tox-dev/toml-fmt/pull/479)) by
      [@gaborbernat](https://github.com/gaborbernat).

    ## tox-toml-fmt

    ### 1.11.1 (2026-10-10)

    <a name="release-tox-toml-fmt-1-11-1"></a>

    <a name="release-tox-toml-fmt-1-11-1-added"></a>

    #### Added

    - **Require 3.11 and default to 3.15.** ([#480](https://github.com/tox-dev/toml-fmt/pull/480)) by
      [@gaborbernat](https://github.com/gaborbernat).
    """)


def test_notes_package_drops_anchor_after_heading() -> None:
    context = ReleaseContext(tag="pyproject-fmt/2.30.3", repository="tox-dev/toml-fmt", package="pyproject-fmt")

    body = render_markdown(_CHANGELOG, context)

    assert body == (
        '<a name="release-pyproject-fmt-2-30-3-added"></a>\n\n'
        "### Features\n\n"
        "- **Require 3.11 and default to 3.15.** ([#480](https://github.com/tox-dev/toml-fmt/pull/480)) by "
        "[@gaborbernat](https://github.com/gaborbernat).\n\n"
        "[📜 Full Changelog](https://github.com/tox-dev/toml-fmt/commits/pyproject-fmt/2.30.3)\n"
    )


def test_contributors_package_keeps_anchor_after_heading(tmp_path: Path, github: GitHub) -> None:
    github({"480": ("gaborbernat", "User", "2026-10-10T10:00:00Z")}, set())
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(_CHANGELOG, encoding="utf-8")

    add_new_contributors(changelog, "2.30.3", "tox-dev/toml-fmt", "pyproject-fmt")

    assert changelog.read_text(encoding="utf-8") == _CHANGELOG.replace(
        "### 2.30.2 (2026-10-09)\n",
        '<a name="release-pyproject-fmt-2-30-3-new-contributors"></a>\n\n'
        "#### New Contributors\n\n"
        "- [@gaborbernat](https://github.com/gaborbernat) made their first contribution in "
        "[#480](https://github.com/tox-dev/toml-fmt/pull/480)\n\n"
        "### 2.30.2 (2026-10-09)\n",
        1,
    )

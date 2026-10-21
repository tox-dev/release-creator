"""Anchor command tests."""

import sys
from typing import TYPE_CHECKING

from release_creator.cli import main

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_anchors_cli_updates_changelog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("## 2026.1021.0\n\n### Security\n\n- Fix trust roots.\n")
    monkeypatch.setattr(sys, "argv", ["release-creator", "anchors", "--changelog", str(changelog)])

    main()

    assert changelog.read_text() == (
        '<a name="release-2026-1021-0"></a>\n\n'
        "## 2026.1021.0\n\n"
        '<a name="release-2026-1021-0-security"></a>\n\n'
        "### Security\n\n- Fix trust roots.\n"
    )

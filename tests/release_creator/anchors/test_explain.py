"""What the anchors command reports on stderr about its choices."""

import sys
from typing import TYPE_CHECKING

import pytest

from release_creator.cli import main

if TYPE_CHECKING:
    from pathlib import Path

_PLAIN = "## 2026.1021.0\n\n### Security\n\n- Fix trust roots.\n"


def _anchor(monkeypatch: pytest.MonkeyPatch, changelog: Path) -> None:
    monkeypatch.setattr(sys, "argv", ["release-creator", "anchors", "--changelog", str(changelog)])
    main()


@pytest.mark.parametrize(
    ("runs", "state"), [pytest.param(1, "updated", id="updated"), pytest.param(2, "already in place", id="in-place")]
)
def test_anchors_explains_on_stderr(
    runs: int, state: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(_PLAIN)

    for _ in range(runs):
        _anchor(monkeypatch, changelog)

    assert capsys.readouterr().err.splitlines()[-1] == f"Anchors: 2 release anchors in {changelog}, {state}"


def test_anchors_keeps_stdout_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(_PLAIN)

    _anchor(monkeypatch, changelog)

    assert not capsys.readouterr().out

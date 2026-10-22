"""Git checkout shared by fragment tests."""

import shutil
from typing import TYPE_CHECKING

import pytest

from release_creator.process import run_text

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def git_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    git = shutil.which("git")
    assert git is not None
    assert run_text([git, "init", "-q", str(tmp_path)]).returncode == 0
    assert run_text([git, "-C", str(tmp_path), "config", "user.name", "Test"]).returncode == 0
    assert run_text([git, "-C", str(tmp_path), "config", "user.email", "test@example.com"]).returncode == 0
    monkeypatch.chdir(tmp_path)
    return tmp_path, git

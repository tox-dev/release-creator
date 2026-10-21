"""Artifact fixtures."""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    directory = tmp_path / "dist"
    directory.mkdir()
    (directory / "example-1.0.0-py3-none-any.whl").write_bytes(b"wheel")
    (directory / "example-1.0.0.tar.gz").write_bytes(b"sdist")
    return directory

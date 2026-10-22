"""PyPI artifact command."""

import sys
from typing import TYPE_CHECKING

from release_creator.cli import main

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from pytest_mock import MockerFixture


def test_artifacts_prints_published_urls(
    dist: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    urls = ["https://files.pythonhosted.org/packages/example-1.0.0.tar.gz"]
    verify = mocker.patch("release_creator.artifacts.cli.verify_artifacts", return_value=urls)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "artifacts",
            "--project",
            "example",
            "--version",
            "1.0.0",
            "--dist",
            str(dist),
            "--wait-seconds",
            "120",
        ],
    )

    main()

    verify.assert_called_once_with("example", "1.0.0", dist, 120)
    assert capsys.readouterr().out == f"{urls[0]}\n"

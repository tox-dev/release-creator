"""PyPI artifact command."""

import hashlib
import io
import json
import operator
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
    files = [
        {
            "filename": path.name,
            "hashes": {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
            "url": f"https://files.pythonhosted.org/packages/{path.name}",
        }
        for path in dist.iterdir()
    ]
    request = mocker.patch(
        "release_creator.artifacts.reconcile.urlopen",
        return_value=io.BytesIO(json.dumps({"meta": {"api-version": "1.4"}, "files": files}).encode()),
    )
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

    assert request.call_count == 1
    assert capsys.readouterr().out == "".join(
        f"{item['url']}\n" for item in sorted(files, key=operator.itemgetter("filename"))
    )

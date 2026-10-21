"""PyPI artifact command."""

import hashlib
import io
import json
import sys
from email.message import Message
from http import HTTPStatus
from typing import TYPE_CHECKING
from urllib.error import HTTPError

import pytest

from release_creator.cli import main

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def test_artifacts_stage_writes_missing_count(
    dist: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mocker.patch(
        "release_creator.artifacts.reconcile.urlopen",
        side_effect=HTTPError("https://pypi.org", HTTPStatus.NOT_FOUND, "missing", Message(), None),
    )
    output = tmp_path / "output"
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
            "--mode",
            "stage",
            "--missing-dir",
            str(tmp_path / "missing"),
            "--github-output",
            str(output),
        ],
    )

    main()

    assert output.read_text(encoding="utf-8") == "missing_count=2\n"
    assert capsys.readouterr().out == "2\n"


def test_artifacts_verify_accepts_exact_release(
    dist: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    mocker.patch(
        "release_creator.artifacts.reconcile.urlopen",
        return_value=io.BytesIO(
            json.dumps({
                "urls": [
                    {"filename": path.name, "digests": {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}
                    for path in dist.iterdir()
                ]
            }).encode()
        ),
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
            "--mode",
            "verify",
        ],
    )

    main()

    assert capsys.readouterr().out == "0\n"


@pytest.mark.parametrize(
    ("mode", "extra", "expected"),
    [
        pytest.param("stage", [], "stage mode requires --missing-dir", id="stage-without-directory"),
        pytest.param("verify", ["--missing-dir", "missing"], "verify mode does not accept", id="verify-with-directory"),
        pytest.param("verify", ["--github-output", "output"], "verify mode does not accept", id="verify-with-output"),
        pytest.param(
            "stage",
            ["--missing-dir", "missing", "--wait-seconds", "1"],
            "stage mode does not accept",
            id="stage-with-wait",
        ),
    ],
)
def test_artifacts_rejects_incompatible_options(
    mode: str,
    extra: list[str],
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
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
            "dist",
            "--mode",
            mode,
            *extra,
        ],
    )

    with pytest.raises(SystemExit) as error:
        main()

    expected_usage_error = 2
    assert error.value.code == expected_usage_error
    assert expected in capsys.readouterr().err

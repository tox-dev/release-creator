"""Marketplace command output."""

import sys
from email.message import Message
from io import BytesIO
from urllib.error import HTTPError
from zipfile import BadZipFile, ZipFile
lazy from pathlib import Path

import pytest
lazy from pytest_mock import MockerFixture

from release_creator.cli import main


@pytest.fixture
def archive(tmp_path: Path) -> Path:
    path = tmp_path / "signed.zip"
    with ZipFile(path, "w") as output:
        output.writestr("plugin/main.jar", b"signed")
    return path


@pytest.mark.parametrize(("absent", "expected"), [(False, "publish=false\n"), (True, "publish=true\n")])
def test_marketplace_cli_writes_publish_decision(
    archive: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    *,
    absent: bool,
    expected: str,
) -> None:
    output = archive.parent / "github-output"
    request = mocker.patch(
        "release_creator.marketplace.compare.urlopen",
        side_effect=HTTPError("https://plugins.jetbrains.com", 404, "missing", Message(), None) if absent else None,
        return_value=BytesIO(archive.read_bytes()),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "marketplace",
            "--plugin-id",
            "com.example.plugin",
            "--version",
            "2.4.6",
            "--archive",
            str(archive),
            "--github-output",
            str(output),
        ],
    )

    main()

    assert output.read_text(encoding="utf-8") == expected
    assert request.call_count == 1


def test_marketplace_cli_verifies_without_output(
    archive: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mocker.patch("release_creator.marketplace.compare.urlopen", return_value=BytesIO(archive.read_bytes()))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "marketplace",
            "--plugin-id",
            "com.example.plugin",
            "--version",
            "2.4.6",
            "--archive",
            str(archive),
            "--mode",
            "verify",
        ],
    )

    main()

    assert capsys.readouterr().out == "publish=false\n"


def test_marketplace_cli_reports_invalid_zip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    archive = tmp_path / "invalid.zip"
    archive.write_bytes(b"not a ZIP")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "marketplace",
            "--plugin-id",
            "com.example.plugin",
            "--version",
            "2.4.6",
            "--archive",
            str(archive),
        ],
    )

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code != 0
    assert str(BadZipFile("File is not a zip file")) in capsys.readouterr().err

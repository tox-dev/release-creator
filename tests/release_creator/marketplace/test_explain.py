"""What the marketplace command reports on stderr about its choices."""

import sys
from email.message import Message
from io import BytesIO
from urllib.error import HTTPError
from zipfile import ZipFile
lazy from pathlib import Path

import pytest
lazy from pytest_mock import MockerFixture

from release_creator.cli import main


@pytest.fixture
def archive(tmp_path: Path) -> Path:
    path = tmp_path / "signed.zip"
    with ZipFile(path, "w") as output:
        output.writestr("plugin/main.jar", b"signed")
        output.writestr("plugin/lib.jar", b"library")
    return path


def _reconcile(mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch, archive: Path, *, absent: bool) -> None:
    mocker.patch(
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
            str(archive.parent / "github-output"),
        ],
    )
    main()


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            (
                True,
                "Marketplace: no visible version 2.4.6 of com.example.plugin, so it needs publishing",
                "publish=true",
            ),
            id="absent",
        ),
        pytest.param(
            (
                False,
                "Marketplace: version 2.4.6 of com.example.plugin matches the signed ZIP, so it is already published",
                "publish=false",
            ),
            id="published",
        ),
    ],
)
def test_marketplace_explains_on_stderr(
    case: tuple[bool, str, str],
    archive: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    absent, decision, result = case
    _reconcile(mocker, monkeypatch, archive, absent=absent)

    assert capsys.readouterr().err.splitlines() == [
        f"Signed ZIP: {archive} has 2 members",
        decision,
        f"GitHub step output: appended {result} to {archive.parent / 'github-output'}",
    ]


def test_marketplace_keeps_stdout_to_the_decision(
    archive: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _reconcile(mocker, monkeypatch, archive, absent=True)

    assert capsys.readouterr().out == "publish=true\n"
    assert (archive.parent / "github-output").read_text(encoding="utf-8") == "publish=true\n"


def test_marketplace_explains_missing_github_output(
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
        ],
    )

    main()

    assert capsys.readouterr().err.splitlines()[-1] == "GitHub step output: not written (no --github-output)"

"""Marketplace command output."""

import sys
lazy from pathlib import Path

import pytest
lazy from pytest_mock import MockerFixture

from release_creator.cli import main


@pytest.mark.parametrize(("absent", "expected"), [(False, "publish=false\n"), (True, "publish=true\n")])
def test_marketplace_cli_writes_publish_decision(
    tmp_path: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    *,
    absent: bool,
    expected: str,
) -> None:
    output = tmp_path / "github-output"
    compare = mocker.patch("release_creator.marketplace.cli.reconcile_marketplace", return_value=absent)
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
            str(tmp_path / "signed.zip"),
            "--github-output",
            str(output),
        ],
    )

    main()

    assert output.read_text(encoding="utf-8") == expected
    compare.assert_called_once_with("com.example.plugin", "2.4.6", tmp_path / "signed.zip", "stage")


def test_marketplace_cli_verifies_without_output(
    tmp_path: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mocker.patch("release_creator.marketplace.cli.reconcile_marketplace", return_value=False)
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
            str(tmp_path / "signed.zip"),
            "--mode",
            "verify",
        ],
    )

    main()

    assert capsys.readouterr().out == "publish=false\n"

"""Marketplace archive identity and retry behavior."""

import http
import io
import zipfile
from email.message import Message
from typing import TYPE_CHECKING
from urllib.error import HTTPError
lazy from pathlib import Path

import pytest
lazy from pytest_mock import MockerFixture

from release_creator.marketplace.compare import reconcile_marketplace

if TYPE_CHECKING:
    from collections.abc import Mapping


@pytest.fixture
def archive(tmp_path: Path) -> Path:
    path = tmp_path / "plugin-signed.zip"
    _zip(path, {"plugin/": b"", "plugin/lib/main.jar": b"signed", "plugin/lib/options.jar": b"search"})
    return path


def _zip(path: Path, members: Mapping[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as output:
        for name, content in members.items():
            output.writestr(name, content)


def _marketplace(mocker: MockerFixture, members: Mapping[str, bytes]) -> None:
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for name, body in members.items():
            output.writestr(name, body)
    mocker.patch("release_creator.marketplace.compare.urlopen", return_value=io.BytesIO(content.getvalue()))


def test_marketplace_accepts_repacked_archive(archive: Path, mocker: MockerFixture) -> None:
    _marketplace(mocker, {"plugin/": b"", "plugin/lib/main.jar": b"signed", "plugin/lib/options.jar": b"search"})

    assert not reconcile_marketplace("com.example.plugin", "2.4.6", archive, "stage")


@pytest.mark.parametrize(
    "members",
    [
        pytest.param({"plugin/lib/main.jar": b"changed"}, id="changed-member"),
        pytest.param({"plugin/lib/main.jar": b"signed"}, id="missing-member"),
        pytest.param(
            {"plugin/": b"", "plugin/lib/main.jar": b"signed", "plugin/lib/options.jar": b"search", "extra": b"x"},
            id="extra-member",
        ),
    ],
)
def test_marketplace_rejects_different_members(
    archive: Path, mocker: MockerFixture, members: Mapping[str, bytes]
) -> None:
    _marketplace(mocker, members)

    with pytest.raises(ValueError, match="archive differs"):
        reconcile_marketplace("com.example.plugin", "2.4.6", archive, "stage")


@pytest.mark.parametrize("mode", ["stage", "verify"])
def test_marketplace_handles_absent_version(archive: Path, mocker: MockerFixture, mode: str) -> None:
    mocker.patch(
        "release_creator.marketplace.compare.urlopen",
        side_effect=HTTPError("https://plugins.jetbrains.com", 404, "missing", Message(), None),
    )

    if mode == "stage":
        assert reconcile_marketplace("com.example.plugin", "9999.0.0", archive, "stage")
    else:
        with pytest.raises(ValueError, match="no visible version"):
            reconcile_marketplace("com.example.plugin", "9999.0.0", archive, "verify")


def test_marketplace_propagates_other_http_errors(archive: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "release_creator.marketplace.compare.urlopen",
        side_effect=HTTPError(
            "https://plugins.jetbrains.com", http.HTTPStatus.SERVICE_UNAVAILABLE, "unavailable", Message(), None
        ),
    )

    with pytest.raises(HTTPError) as error:
        reconcile_marketplace("com.example.plugin", "2.4.6", archive, "stage")

    assert error.value.code == http.HTTPStatus.SERVICE_UNAVAILABLE


@pytest.mark.parametrize("source", ["local", "remote"])
def test_marketplace_rejects_duplicate_members(archive: Path, mocker: MockerFixture, source: str) -> None:
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as output:
        output.writestr("plugin/lib/main.jar", b"one")
        with pytest.warns(UserWarning, match="Duplicate name"):
            output.writestr("plugin/lib/main.jar", b"two")
    if source == "local":
        archive.write_bytes(content.getvalue())
    else:
        mocker.patch("release_creator.marketplace.compare.urlopen", return_value=io.BytesIO(content.getvalue()))

    with pytest.raises(ValueError, match="duplicate plugin ZIP member"):
        reconcile_marketplace("com.example.plugin", "2.4.6", archive, "stage")


@pytest.mark.parametrize("source", ["local", "remote"])
def test_marketplace_rejects_invalid_zip(archive: Path, mocker: MockerFixture, source: str) -> None:
    if source == "local":
        archive.write_bytes(b"not a ZIP")
    else:
        mocker.patch("release_creator.marketplace.compare.urlopen", return_value=io.BytesIO(b"not a ZIP"))

    with pytest.raises(ValueError, match="invalid plugin ZIP"):
        reconcile_marketplace("com.example.plugin", "2.4.6", archive, "stage")


def test_marketplace_rejects_empty_zip(archive: Path) -> None:
    with zipfile.ZipFile(archive, "w"):
        pass

    with pytest.raises(ValueError, match="no members"):
        reconcile_marketplace("com.example.plugin", "2.4.6", archive, "stage")


def test_marketplace_rejects_directory_content(archive: Path) -> None:
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("plugin/", b"unexpected")

    with pytest.raises(ValueError, match="directory member has content"):
        reconcile_marketplace("com.example.plugin", "2.4.6", archive, "stage")


@pytest.mark.parametrize(("plugin_id", "version"), [("", "1.0"), ("com.example.plugin", ""), (" plugin", "1.0")])
def test_marketplace_rejects_invalid_coordinates(archive: Path, plugin_id: str, version: str) -> None:
    with pytest.raises(ValueError, match="plugin ID and version"):
        reconcile_marketplace(plugin_id, version, archive, "stage")


def test_marketplace_rejects_symlink(tmp_path: Path, archive: Path) -> None:
    linked = tmp_path / "linked.zip"
    linked.symlink_to(archive)

    with pytest.raises(ValueError, match="not a regular file"):
        reconcile_marketplace("com.example.plugin", "2.4.6", linked, "stage")

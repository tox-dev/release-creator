"""Marketplace archive identity and retry behavior."""

import http
import io
import stat
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


def _zip(
    path: Path | io.BytesIO,
    members: Mapping[str, bytes],
    modes: Mapping[str, int] | None = None,
    compression: int = zipfile.ZIP_STORED,
) -> None:
    with zipfile.ZipFile(path, "w", compression=compression) as output:
        for name, content in members.items():
            if modes is not None and name in modes:
                member = zipfile.ZipInfo(name)
                member.create_system = 3
                member.external_attr = modes[name] << 16
                output.writestr(member, content)
            else:
                output.writestr(name, content)


def _marketplace(mocker: MockerFixture, members: Mapping[str, bytes], modes: Mapping[str, int] | None = None) -> None:
    content = io.BytesIO()
    _zip(content, members, modes, zipfile.ZIP_DEFLATED)
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


def test_marketplace_rejects_duplicate_member(archive: Path, mocker: MockerFixture) -> None:
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as output:
        output.writestr("plugin/lib/main.jar", b"different")
        for name, body in {
            "plugin/": b"",
            "plugin/lib/main.jar": b"signed",
            "plugin/lib/options.jar": b"search",
        }.items():
            output.writestr(name, body)
    mocker.patch("release_creator.marketplace.compare.urlopen", return_value=io.BytesIO(content.getvalue()))

    with pytest.raises(ValueError, match="duplicate plugin ZIP member"):
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
def test_marketplace_rejects_invalid_zip(archive: Path, mocker: MockerFixture, source: str) -> None:
    if source == "local":
        archive.write_bytes(b"not a ZIP")
    else:
        mocker.patch("release_creator.marketplace.compare.urlopen", return_value=io.BytesIO(b"not a ZIP"))

    with pytest.raises(zipfile.BadZipFile):
        reconcile_marketplace("com.example.plugin", "2.4.6", archive, "stage")


def test_marketplace_rejects_permission_change(archive: Path, mocker: MockerFixture) -> None:
    _marketplace(
        mocker,
        {"plugin/": b"", "plugin/lib/main.jar": b"signed", "plugin/lib/options.jar": b"search"},
        {"plugin/lib/main.jar": stat.S_IFREG | 0o755},
    )

    with pytest.raises(ValueError, match="archive differs"):
        reconcile_marketplace("com.example.plugin", "2.4.6", archive, "stage")


def test_marketplace_rejects_symlink_member(archive: Path, mocker: MockerFixture) -> None:
    _marketplace(
        mocker,
        {"plugin/": b"", "plugin/lib/main.jar": b"signed", "plugin/lib/options.jar": b"search"},
        {"plugin/lib/main.jar": stat.S_IFLNK | 0o777},
    )

    with pytest.raises(ValueError, match="archive differs"):
        reconcile_marketplace("com.example.plugin", "2.4.6", archive, "stage")


def test_marketplace_rejects_changed_zip_origin(archive: Path, mocker: MockerFixture) -> None:
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as output:
        for name, body in {
            "plugin/": b"",
            "plugin/lib/main.jar": b"signed",
            "plugin/lib/options.jar": b"search",
        }.items():
            member = zipfile.ZipInfo(name)
            member.create_system = 0
            output.writestr(member, body)
    mocker.patch("release_creator.marketplace.compare.urlopen", return_value=io.BytesIO(content.getvalue()))

    with pytest.raises(ValueError, match="archive differs"):
        reconcile_marketplace("com.example.plugin", "2.4.6", archive, "stage")

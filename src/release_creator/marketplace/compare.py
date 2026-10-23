"""Check a published plugin by its uncompressed ZIP members."""

lazy import hashlib
lazy import http
lazy import shutil
lazy import stat
lazy import tempfile
lazy from pathlib import Path
lazy from typing import IO, Final, Literal
lazy from urllib.error import HTTPError
lazy from urllib.parse import urlencode
lazy from urllib.request import Request, urlopen
lazy from zipfile import ZipFile


def reconcile_marketplace(plugin_id: str, version: str, archive: Path, mode: Literal["stage", "verify"]) -> bool:
    """Return whether an absent version needs publishing; verify an existing version's ZIP members.

    :param plugin_id: Marketplace plugin ID.
    :param version: Plugin version.
    :param archive: Signed plugin ZIP to compare.
    :param mode: Whether to stage or verify the Marketplace version.
    :returns: Whether a version absent from Marketplace needs publishing.
    :raises ValueError: The archive differs from Marketplace or is absent during verification.
    :raises HTTPError: Marketplace returned an HTTP error other than 404.
    """
    local = _read_members(archive)
    request = Request(
        f"https://plugins.jetbrains.com/plugin/download?{urlencode({'pluginId': plugin_id, 'version': version})}",
        headers={"Accept": "application/zip", "Cache-Control": "no-cache"},
    )
    try:
        remote = _download_members(request)
    except HTTPError as error:
        if error.code != http.HTTPStatus.NOT_FOUND:
            raise
        if mode == "verify":
            msg = f"Marketplace has no visible version {version} for {plugin_id}"
            raise ValueError(msg) from error
        return True
    if remote != local:
        msg = f"Marketplace archive differs from the signed plugin ZIP for {plugin_id} {version}"
        raise ValueError(msg)
    return False


def _download_members(request: Request) -> dict[str, tuple[str, str, int]]:
    with urlopen(request, timeout=30) as response, tempfile.TemporaryFile() as downloaded:  # ruff: ignore[suspicious-url-open-usage]  # The origin is fixed to HTTPS Marketplace.
        shutil.copyfileobj(response, downloaded, 1 << 20)
        downloaded.seek(0)
        return _read_members(downloaded)


def _read_members(source: Path | IO[bytes]) -> dict[str, tuple[str, str, int]]:
    zip_unix_system: Final = 3
    with ZipFile(source) as archive:
        members: dict[str, tuple[str, str, int]] = {}
        for member in archive.infolist():
            if member.filename in members:
                msg = f"duplicate plugin ZIP member: {member.filename}"
                raise ValueError(msg)
            mode = member.external_attr >> 16
            permissions = stat.S_IMODE(mode) if member.create_system == zip_unix_system else member.external_attr
            if member.is_dir():
                digest = hashlib.sha256(b"").hexdigest()
            else:
                with archive.open(member) as stream:
                    hasher = hashlib.sha256()
                    while chunk := stream.read(1 << 20):
                        hasher.update(chunk)
                    digest = hasher.hexdigest()
            kind = "directory" if member.is_dir() else "file"
            file_type = stat.S_IFMT(mode) if member.create_system == zip_unix_system else 0
            members[member.filename] = digest, f"{member.create_system}:{file_type}:{kind}", permissions
        if not any(kind.endswith(":file") for _, kind, _ in members.values()):
            msg = "plugin ZIP contains no files"
            raise ValueError(msg)
    return members


__all__ = [
    "reconcile_marketplace",
]

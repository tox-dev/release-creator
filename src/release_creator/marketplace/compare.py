"""Check a published plugin by its uncompressed ZIP members."""

lazy import hashlib
lazy import http
lazy import shutil
lazy import tempfile
lazy from pathlib import Path
lazy from typing import IO, Literal
lazy from urllib.error import HTTPError
lazy from urllib.parse import urlencode
lazy from urllib.request import Request, urlopen
lazy from zipfile import BadZipFile, ZipFile


def reconcile_marketplace(plugin_id: str, version: str, archive: Path, mode: Literal["stage", "verify"]) -> bool:
    """Return whether an absent version needs publishing; verify an existing version's member bytes.

    Returns:
        Whether a version absent from Marketplace needs publishing.

    Raises:
        ValueError: The archive is invalid, differs from Marketplace, or is absent during verification.
        HTTPError: Marketplace returned an HTTP error other than 404.

    """
    if not plugin_id or not version or any(value.strip() != value for value in (plugin_id, version)):
        msg = "plugin ID and version must be nonempty and have no surrounding whitespace"
        raise ValueError(msg)
    if archive.is_symlink() or not archive.is_file():
        msg = f"plugin archive is not a regular file: {archive}"
        raise ValueError(msg)
    local = _member_digests(archive)
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


def _download_members(request: Request) -> dict[str, str]:
    with urlopen(request, timeout=30) as response, tempfile.TemporaryFile() as downloaded:  # ruff: ignore[suspicious-url-open-usage]  # The origin is fixed to HTTPS Marketplace.
        shutil.copyfileobj(response, downloaded, 1 << 20)
        downloaded.seek(0)
        return _member_digests(downloaded)


def _member_digests(source: Path | IO[bytes]) -> dict[str, str]:
    try:
        members = _read_members(source)
    except BadZipFile as error:
        msg = "invalid plugin ZIP"
        raise ValueError(msg) from error
    if not members:
        msg = "plugin ZIP has no members"
        raise ValueError(msg)
    return members


def _read_members(source: Path | IO[bytes]) -> dict[str, str]:
    with ZipFile(source) as archive:
        members: dict[str, str] = {}
        for member in archive.infolist():
            if member.filename in members:
                msg = f"duplicate plugin ZIP member: {member.filename}"
                raise ValueError(msg)
            if member.is_dir():
                if member.file_size:
                    msg = f"directory member has content: {member.filename}"
                    raise ValueError(msg)
                digest = hashlib.sha256(b"").hexdigest()
            else:
                with archive.open(member) as stream:
                    hasher = hashlib.sha256()
                    while chunk := stream.read(1 << 20):
                        hasher.update(chunk)
                    digest = hasher.hexdigest()
            members[member.filename] = digest
    return members


__all__ = [
    "reconcile_marketplace",
]

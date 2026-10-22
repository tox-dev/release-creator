"""Verify published PyPI distributions against local build files."""

lazy import hashlib
lazy import http
lazy import json
lazy import time
lazy from pathlib import Path
lazy from typing import cast
lazy from urllib.error import HTTPError
lazy from urllib.parse import quote, unquote, urlsplit, urlunsplit
lazy from urllib.request import Request, urlopen

lazy from packaging.utils import (
    InvalidSdistFilename,
    InvalidWheelFilename,
    canonicalize_name,
    parse_sdist_filename,
    parse_wheel_filename,
)
lazy from packaging.version import InvalidVersion, Version


def verify_artifacts(project: str, version: str, dist: Path, wait_seconds: int) -> list[str]:
    """Wait only for PyPI's complete, consistent release view.

    :param project: PyPI project name.
    :param version: Release version.
    :param dist: Directory holding the expected distribution files.
    :param wait_seconds: Maximum time to wait for PyPI propagation.
    :returns: Published distribution URLs for provenance verification.
    :raises ValueError: The release is incomplete at the deadline or its files differ.
    :raises _IncompleteReleaseError: PyPI has not published every expected file by the deadline.
    """
    if wait_seconds < 0:
        msg = "wait_seconds must be nonnegative"
        raise ValueError(msg)
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            urls = _verify_files(project, version, dist)
        except _IncompleteReleaseError:
            if (remaining := deadline - time.monotonic()) <= 0:
                raise
            time.sleep(min(2, remaining))
        else:
            return urls


def _verify_files(project: str, version: str, dist: Path) -> list[str]:
    """Require PyPI to contain exactly the locally built files.

    :param project: PyPI project name.
    :param version: Release version.
    :param dist: Directory holding the expected distribution files.
    :returns: Published distribution URLs.
    :raises ValueError: An artifact set is incomplete, mismatched, or malformed.
    :raises _IncompleteReleaseError: PyPI has not published every expected file.
    """
    try:
        normalized_project = canonicalize_name(project, validate=True)
        release_version = Version(version)
    except (InvalidVersion, ValueError) as error:
        msg = f"invalid PyPI project or version: {project} {version}"
        raise ValueError(msg) from error
    if not dist.is_dir():
        msg = f"artifact directory does not exist: {dist}"
        raise ValueError(msg)
    local = _local_files(dist, normalized_project, release_version)
    remote = _remote_files(normalized_project, release_version)
    if extra := remote.keys() - local.keys():
        msg = f"PyPI has unexpected files: {', '.join(sorted(extra))}"
        raise ValueError(msg)
    if mismatched := {name for name in remote if remote[name][0] != local[name]}:
        msg = f"PyPI has different SHA256 digests: {', '.join(sorted(mismatched))}"
        raise ValueError(msg)
    if missing := sorted(local.keys() - remote.keys()):
        msg = f"PyPI is missing files: {', '.join(missing)}"
        raise _IncompleteReleaseError(msg)
    return [remote[name][1] for name in sorted(local)]


class _IncompleteReleaseError(ValueError):
    pass


def _local_files(dist: Path, project: str, version: Version) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in dist.iterdir():
        if path.name.startswith("."):
            continue
        if path.is_symlink() or not path.is_file():
            msg = f"invalid artifact path: {path}"
            raise ValueError(msg)
        try:
            name, artifact_version = (
                parse_wheel_filename(path.name)[:2] if path.name.endswith(".whl") else parse_sdist_filename(path.name)
            )
        except (InvalidSdistFilename, InvalidWheelFilename) as error:
            msg = f"invalid artifact filename: {path.name}"
            raise ValueError(msg) from error
        if name != project or artifact_version != version:
            msg = f"artifact belongs to another project or version: {path.name}"
            raise ValueError(msg)
        files[path.name] = _sha256(path)
    if not files:
        msg = f"artifact directory is empty: {dist}"
        raise ValueError(msg)
    return files


def _remote_files(project: str, version: Version) -> dict[str, tuple[str, str]]:
    files: dict[str, tuple[str, str]] = {}
    for item in _simple_index(project):
        if not isinstance(item, dict):
            msg = "PyPI returned an invalid release file"
            raise TypeError(msg)
        name = item.get("filename")
        if not isinstance(name, str):
            msg = "PyPI returned an invalid filename"
            raise TypeError(msg)
        try:
            release_name, release_version = (
                parse_wheel_filename(name)[:2] if name.endswith(".whl") else parse_sdist_filename(name)
            )
        except InvalidSdistFilename, InvalidWheelFilename:
            continue
        if release_name != project or release_version != version:
            continue
        if name in files:
            msg = f"PyPI returned a duplicate file: {name}"
            raise ValueError(msg)
        if item.get("yanked"):
            msg = f"PyPI release file is yanked: {name}"
            raise ValueError(msg)
        files[name] = _file_metadata(item, name)
    return files


def _simple_index(project: str) -> list[object]:
    request = Request(
        f"https://pypi.org/simple/{quote(project)}/",
        headers={"Accept": "application/vnd.pypi.simple.v1+json", "Cache-Control": "no-cache"},
    )
    try:
        with urlopen(request, timeout=30) as response:  # ruff: ignore[suspicious-url-open-usage]  # The origin is fixed to HTTPS PyPI.
            payload: object = json.load(response)
    except HTTPError as error:
        if error.code == http.HTTPStatus.NOT_FOUND:
            return []
        raise
    if not isinstance(payload, dict) or not isinstance(payload.get("files"), list):
        msg = "PyPI returned an invalid Simple API response"
        raise TypeError(msg)
    meta = payload.get("meta")
    if (
        not isinstance(meta, dict)
        or not isinstance(meta.get("api-version"), str)
        or meta["api-version"].split(".")[0] != "1"
    ):
        msg = "unsupported PyPI Simple API version"
        raise ValueError(msg)
    return cast("list[object]", payload["files"])


def _file_metadata(item: dict[str, object], name: str) -> tuple[str, str]:
    digests = item.get("hashes")
    digest = digests.get("sha256") if isinstance(digests, dict) else None
    url = item.get("url")
    if not isinstance(digest, str) or len(digest) != hashlib.sha256().digest_size * 2 or not isinstance(url, str):
        msg = "PyPI returned an invalid filename, URL, or SHA256 digest"
        raise ValueError(msg)
    if any(character not in "0123456789abcdef" for character in digest):
        msg = "PyPI returned an invalid filename, URL, or SHA256 digest"
        raise ValueError(msg)
    try:
        parsed_url = urlsplit(url)
        valid_url = (
            parsed_url.scheme == "https"
            and parsed_url.hostname == "files.pythonhosted.org"
            and unquote(parsed_url.path.rsplit("/", 1)[-1]) == name
        )
    except ValueError as error:
        msg = "PyPI returned an invalid filename, URL, or SHA256 digest"
        raise ValueError(msg) from error
    if not valid_url:
        msg = "PyPI returned an invalid filename, URL, or SHA256 digest"
        raise ValueError(msg)
    return digest, urlunsplit(parsed_url._replace(fragment=""))


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


__all__ = [
    "verify_artifacts",
]

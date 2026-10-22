"""Stage only artifacts absent from PyPI and verify their identity."""

lazy import hashlib
lazy import http
lazy import json
lazy import shutil
lazy import time
lazy from pathlib import Path
lazy from typing import Literal
lazy from urllib.error import HTTPError
lazy from urllib.parse import quote
lazy from urllib.request import Request, urlopen

lazy from packaging.utils import (
    InvalidSdistFilename,
    InvalidWheelFilename,
    canonicalize_name,
    parse_sdist_filename,
    parse_wheel_filename,
)
lazy from packaging.version import InvalidVersion, Version


def reconcile_artifacts(
    project: str,
    version: str,
    dist: Path,
    mode: Literal["stage", "verify"],
    missing_dir: Path | None = None,
) -> int:
    """Compare local artifacts with PyPI and stage the unpublished subset.

    :param project: PyPI project name.
    :param version: Release version.
    :param dist: Directory holding the expected distribution files.
    :param mode: Whether to stage missing files or verify publication.
    :param missing_dir: New directory for files absent from PyPI.
    :returns: Number of artifacts absent from PyPI before this check.
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
    remote = _remote_files(normalized_project, version)
    if extra := remote.keys() - local.keys():
        msg = f"PyPI has unexpected files: {', '.join(sorted(extra))}"
        raise ValueError(msg)
    if mismatched := {name for name in remote if remote[name] != local[name]}:
        msg = f"PyPI has different SHA256 digests: {', '.join(sorted(mismatched))}"
        raise ValueError(msg)
    missing = sorted(local.keys() - remote.keys())
    if mode == "verify":
        if missing:
            msg = f"PyPI is missing files: {', '.join(missing)}"
            raise _IncompleteReleaseError(msg)
        return 0
    if missing_dir is None or missing_dir.resolve().is_relative_to(dist.resolve()):
        msg = "stage mode requires a fresh directory outside dist"
        raise ValueError(msg)
    missing_dir.mkdir()
    for name in missing:
        shutil.copyfile(dist / name, missing_dir / name)
        if _sha256(missing_dir / name) != local[name]:
            msg = f"artifact changed while staging: {name}"
            raise ValueError(msg)
    return len(missing)


def verify_artifacts(project: str, version: str, dist: Path, wait_seconds: int) -> None:
    """Wait only for PyPI's complete, consistent release view.

    :param project: PyPI project name.
    :param version: Release version.
    :param dist: Directory holding the expected distribution files.
    :param wait_seconds: Maximum time to wait for PyPI propagation.
    :raises ValueError: The release is incomplete at the deadline or its files differ.
    :raises _IncompleteReleaseError: PyPI has not published every expected file by the deadline.
    """
    if wait_seconds < 0:
        msg = "wait_seconds must be nonnegative"
        raise ValueError(msg)
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            reconcile_artifacts(project, version, dist, "verify")
        except _IncompleteReleaseError:
            if (remaining := deadline - time.monotonic()) <= 0:
                raise
            time.sleep(min(2, remaining))
        else:
            return


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


def _remote_files(project: str, version: str) -> dict[str, str]:
    request = Request(
        f"https://pypi.org/pypi/{quote(project)}/{quote(version, safe='')}/json",
        headers={"Accept": "application/json", "Cache-Control": "no-cache"},
    )
    try:
        with urlopen(request, timeout=30) as response:  # ruff: ignore[suspicious-url-open-usage]  # The origin is fixed to HTTPS PyPI.
            payload: object = json.load(response)
    except HTTPError as error:
        if error.code == http.HTTPStatus.NOT_FOUND:
            return {}
        raise
    if not isinstance(payload, dict) or not isinstance(payload.get("urls"), list) or not payload["urls"]:
        msg = "PyPI returned no release files or an invalid response"
        raise ValueError(msg)
    files: dict[str, str] = {}
    for item in payload["urls"]:
        if not isinstance(item, dict):
            msg = "PyPI returned an invalid release file"
            raise TypeError(msg)
        name = item.get("filename")
        digests = item.get("digests")
        digest = digests.get("sha256") if isinstance(digests, dict) else None
        if (
            not isinstance(name, str)
            or not isinstance(digest, str)
            or len(digest) != hashlib.sha256().digest_size * 2
            or any(character not in "0123456789abcdef" for character in digest)
            or name in files
        ):
            msg = "PyPI returned an invalid filename or SHA256 digest"
            raise ValueError(msg)
        if item.get("yanked"):
            msg = f"PyPI release file is yanked: {name}"
            raise ValueError(msg)
        files[name] = digest
    return files


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


__all__ = [
    "reconcile_artifacts",
    "verify_artifacts",
]

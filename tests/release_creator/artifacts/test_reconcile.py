"""Published PyPI artifact verification tests."""

from __future__ import annotations

import hashlib
import io
import json
from email.message import Message
from http import HTTPStatus
from urllib.error import HTTPError
lazy from pathlib import Path

import pytest
lazy from pytest_mock import MockerFixture

from release_creator.artifacts.reconcile import verify_artifacts


def remote_response(dist: Path, *names: str, yanked: bool = False) -> io.BytesIO:
    files = [
        {
            "filename": name,
            "hashes": {"sha256": hashlib.sha256((dist / name).read_bytes()).hexdigest()},
            "url": f"https://files.pythonhosted.org/packages/{name}",
            "yanked": yanked,
        }
        for name in names
    ]
    files.append({
        "filename": "example-0.9.0.tar.gz",
        "hashes": {"sha256": "0" * 64},
        "url": "https://files.pythonhosted.org/old",
    })
    return io.BytesIO(json.dumps({"meta": {"api-version": "1.4"}, "name": "example", "files": files}).encode())


def test_verify_complete_release_returns_published_urls(dist: Path, mocker: MockerFixture) -> None:
    names = sorted(path.name for path in dist.iterdir())
    request = mocker.patch("release_creator.artifacts.reconcile.urlopen", return_value=remote_response(dist, *names))

    assert verify_artifacts("example", "1.0.0", dist, 0) == [
        f"https://files.pythonhosted.org/packages/{name}" for name in names
    ]
    assert request.call_args.args[0].full_url == "https://pypi.org/simple/example/"
    assert request.call_args.args[0].get_header("Accept") == "application/vnd.pypi.simple.v1+json"


def test_verify_waits_for_consistent_release(dist: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "release_creator.artifacts.reconcile.urlopen",
        side_effect=[
            remote_response(dist, "example-1.0.0-py3-none-any.whl"),
            remote_response(dist, *(path.name for path in dist.iterdir())),
        ],
    )
    mocker.patch("release_creator.artifacts.reconcile.time.monotonic", side_effect=[0, 1, 1])
    sleep = mocker.patch("release_creator.artifacts.reconcile.time.sleep")

    assert len(verify_artifacts("example", "1.0.0", dist, 10)) == len(list(dist.iterdir()))
    sleep.assert_called_once_with(2)


def test_verify_stops_after_propagation_timeout(dist: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "release_creator.artifacts.reconcile.urlopen",
        return_value=remote_response(dist, "example-1.0.0-py3-none-any.whl"),
    )
    mocker.patch("release_creator.artifacts.reconcile.time.monotonic", side_effect=[0, 10])

    with pytest.raises(ValueError, match="PyPI is missing files"):
        verify_artifacts("example", "1.0.0", dist, 10)


def test_verify_rejects_negative_wait(dist: Path) -> None:
    with pytest.raises(ValueError, match="wait_seconds must be nonnegative"):
        verify_artifacts("example", "1.0.0", dist, -1)


def test_verify_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="artifact directory does not exist"):
        verify_artifacts("example", "1.0.0", tmp_path / "missing", 0)


def test_verify_rejects_empty_directory(tmp_path: Path, mocker: MockerFixture) -> None:
    request = mocker.patch("release_creator.artifacts.reconcile.urlopen")

    with pytest.raises(ValueError, match="artifact directory is empty"):
        verify_artifacts("example", "1.0.0", tmp_path, 0)

    request.assert_not_called()


@pytest.mark.parametrize(
    ("code", "message"),
    [
        pytest.param(HTTPStatus.NOT_FOUND, "PyPI is missing files", id="project-absent"),
        pytest.param(HTTPStatus.FORBIDDEN, "HTTP Error 403", id="access-denied"),
        pytest.param(HTTPStatus.SERVICE_UNAVAILABLE, "HTTP Error 503", id="server-error"),
    ],
)
def test_verify_http_failures(code: HTTPStatus, message: str, dist: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "release_creator.artifacts.reconcile.urlopen",
        side_effect=HTTPError("https://pypi.org", code, "failure", Message(), None),
    )

    with pytest.raises((ValueError, HTTPError), match=message):
        verify_artifacts("example", "1.0.0", dist, 0)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        pytest.param("digest", "0" * 64, "different SHA256 digests", id="digest"),
        pytest.param("filename", "example-1.0.0-cp315-cp315-win_amd64.whl", "unexpected files", id="extra"),
        pytest.param("yanked", True, "release file is yanked", id="yanked"),
        pytest.param("url", "http://example.invalid/file.whl", "invalid filename, URL, or SHA256", id="url"),
    ],
)
def test_verify_rejects_different_remote_file(
    dist: Path, mocker: MockerFixture, field: str, value: str | bool, message: str
) -> None:
    payload = json.loads(remote_response(dist, *(path.name for path in dist.iterdir())).getvalue())
    item = payload["files"][0]
    if field == "digest":
        item["hashes"]["sha256"] = value
    else:
        item[field] = value
    if field == "filename":
        item["url"] = f"https://files.pythonhosted.org/packages/{value}"
    mocker.patch("release_creator.artifacts.reconcile.urlopen", return_value=io.BytesIO(json.dumps(payload).encode()))

    with pytest.raises(ValueError, match=message):
        verify_artifacts("example", "1.0.0", dist, 0)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        pytest.param({}, "invalid Simple API response", id="missing-files"),
        pytest.param({"files": []}, "unsupported PyPI Simple API version", id="missing-version"),
        pytest.param(
            {"meta": {"api-version": "2.0"}, "files": []}, "unsupported PyPI Simple API version", id="future-version"
        ),
        pytest.param({"meta": {"api-version": "1.4"}, "files": [None]}, "invalid release file", id="invalid-file"),
    ],
)
def test_verify_rejects_malformed_index(
    dist: Path, mocker: MockerFixture, payload: dict[str, object], message: str
) -> None:
    mocker.patch("release_creator.artifacts.reconcile.urlopen", return_value=io.BytesIO(json.dumps(payload).encode()))

    with pytest.raises((ValueError, TypeError), match=message):
        verify_artifacts("example", "1.0.0", dist, 0)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        pytest.param("filename", None, "invalid filename", id="filename"),
        pytest.param("hashes", {}, "invalid filename, URL, or SHA256 digest", id="missing-hash"),
        pytest.param("hashes", {"sha256": "z" * 64}, "invalid filename, URL, or SHA256 digest", id="nonhex-hash"),
        pytest.param("url", "https://[invalid", "invalid filename, URL, or SHA256 digest", id="malformed-url"),
    ],
)
def test_verify_rejects_invalid_remote_metadata(
    dist: Path, mocker: MockerFixture, field: str, value: object, message: str
) -> None:
    payload = json.loads(remote_response(dist, *(path.name for path in dist.iterdir())).getvalue())
    payload["files"][0][field] = value
    mocker.patch("release_creator.artifacts.reconcile.urlopen", return_value=io.BytesIO(json.dumps(payload).encode()))

    with pytest.raises((ValueError, TypeError), match=message):
        verify_artifacts("example", "1.0.0", dist, 0)


def test_verify_rejects_duplicate_remote_file(dist: Path, mocker: MockerFixture) -> None:
    payload = json.loads(remote_response(dist, *(path.name for path in dist.iterdir())).getvalue())
    payload["files"].append(payload["files"][0])
    mocker.patch("release_creator.artifacts.reconcile.urlopen", return_value=io.BytesIO(json.dumps(payload).encode()))

    with pytest.raises(ValueError, match="duplicate file"):
        verify_artifacts("example", "1.0.0", dist, 0)


def test_verify_ignores_invalid_remote_artifact_name(dist: Path, mocker: MockerFixture) -> None:
    payload = json.loads(remote_response(dist, *(path.name for path in dist.iterdir())).getvalue())
    payload["files"].append({"filename": "README.txt"})
    mocker.patch("release_creator.artifacts.reconcile.urlopen", return_value=io.BytesIO(json.dumps(payload).encode()))

    assert len(verify_artifacts("example", "1.0.0", dist, 0)) == len(list(dist.iterdir()))


@pytest.mark.parametrize(
    ("filename", "message"),
    [
        pytest.param("notes.txt", "invalid artifact filename", id="nonartifact"),
        pytest.param("other-1.0.0.tar.gz", "another project or version", id="wrong-project"),
        pytest.param("example-2.0.0.tar.gz", "another project or version", id="wrong-version"),
    ],
)
def test_verify_rejects_invalid_local_file(filename: str, message: str, dist: Path, mocker: MockerFixture) -> None:
    (dist / filename).write_bytes(b"extra")
    request = mocker.patch("release_creator.artifacts.reconcile.urlopen")

    with pytest.raises(ValueError, match=message):
        verify_artifacts("example", "1.0.0", dist, 0)

    request.assert_not_called()


def test_verify_rejects_symlink(dist: Path, mocker: MockerFixture) -> None:
    (dist / "example-1.0.0-py3-none-any-copy.whl").symlink_to(dist / "example-1.0.0-py3-none-any.whl")
    request = mocker.patch("release_creator.artifacts.reconcile.urlopen")

    with pytest.raises(ValueError, match="invalid artifact path"):
        verify_artifacts("example", "1.0.0", dist, 0)

    request.assert_not_called()


def test_verify_ignores_hidden_build_metadata(dist: Path, mocker: MockerFixture) -> None:
    (dist / ".gitignore").write_text("*\n")
    mocker.patch(
        "release_creator.artifacts.reconcile.urlopen",
        return_value=remote_response(dist, "example-1.0.0-py3-none-any.whl", "example-1.0.0.tar.gz"),
    )

    assert len(verify_artifacts("example", "1.0.0", dist, 0)) == len([
        path for path in dist.iterdir() if not path.name.startswith(".")
    ])


@pytest.mark.parametrize(
    ("project", "version", "message"),
    [
        pytest.param("../example", "1.0.0", "invalid PyPI project or version", id="project"),
        pytest.param("example", "bad", "invalid PyPI project or version", id="version"),
    ],
)
def test_verify_rejects_invalid_target(project: str, version: str, message: str, dist: Path) -> None:
    with pytest.raises(ValueError, match=message):
        verify_artifacts(project, version, dist, 0)

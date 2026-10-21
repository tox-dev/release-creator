"""PyPI artifact identity and retry staging."""

import hashlib
import io
import json
from email.message import Message
from http import HTTPStatus
from typing import TYPE_CHECKING
from urllib.error import HTTPError

import pytest

from release_creator.artifacts.reconcile import reconcile_artifacts, verify_artifacts

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def remote_response(dist: Path, *names: str, yanked: bool = False) -> io.BytesIO:
    return io.BytesIO(
        json.dumps({
            "urls": [
                {
                    "filename": name,
                    "digests": {"sha256": hashlib.sha256((dist / name).read_bytes()).hexdigest()},
                    "yanked": yanked,
                }
                for name in names
            ]
        }).encode()
    )


def test_stage_new_release_copies_every_file(dist: Path, tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "release_creator.artifacts.reconcile.urlopen",
        side_effect=HTTPError("https://pypi.org", HTTPStatus.NOT_FOUND, "missing", Message(), None),
    )
    missing = tmp_path / "missing"

    count = reconcile_artifacts("example", "1.0.0", dist, "stage", missing)

    expected_file_count = 2
    assert count == expected_file_count
    assert {path.name: path.read_bytes() for path in missing.iterdir()} == {
        path.name: path.read_bytes() for path in dist.iterdir()
    }


def test_stage_partial_release_copies_only_missing(dist: Path, tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "release_creator.artifacts.reconcile.urlopen",
        return_value=remote_response(dist, "example-1.0.0-py3-none-any.whl"),
    )
    missing = tmp_path / "missing"

    count = reconcile_artifacts("example", "1.0.0", dist, "stage", missing)

    assert count == 1
    assert {path.name for path in missing.iterdir()} == {"example-1.0.0.tar.gz"}


def test_stage_complete_release_creates_empty_directory(dist: Path, tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "release_creator.artifacts.reconcile.urlopen",
        return_value=remote_response(dist, *(path.name for path in dist.iterdir())),
    )
    missing = tmp_path / "missing"

    count = reconcile_artifacts("example", "1.0.0", dist, "stage", missing)

    assert count == 0
    assert list(missing.iterdir()) == []


def test_verify_complete_release_accepts_exact_set(dist: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "release_creator.artifacts.reconcile.urlopen",
        return_value=remote_response(dist, *(path.name for path in dist.iterdir())),
    )

    assert reconcile_artifacts("example", "1.0.0", dist, "verify") == 0


def test_verify_partial_release_rejects_missing_file(dist: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "release_creator.artifacts.reconcile.urlopen",
        return_value=remote_response(dist, "example-1.0.0-py3-none-any.whl"),
    )

    with pytest.raises(ValueError, match=r"PyPI is missing files: example-1\.0\.0\.tar\.gz"):
        reconcile_artifacts("example", "1.0.0", dist, "verify")


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

    verify_artifacts("example", "1.0.0", dist, 10)
    sleep.assert_called_once_with(2)


def test_verify_stops_after_propagation_timeout(dist: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "release_creator.artifacts.reconcile.urlopen",
        return_value=remote_response(dist, "example-1.0.0-py3-none-any.whl"),
    )
    mocker.patch("release_creator.artifacts.reconcile.time.monotonic", side_effect=[0, 10])
    sleep = mocker.patch("release_creator.artifacts.reconcile.time.sleep")

    with pytest.raises(ValueError, match="PyPI is missing files"):
        verify_artifacts("example", "1.0.0", dist, 10)

    sleep.assert_not_called()


def test_verify_rejects_negative_wait(dist: Path, mocker: MockerFixture) -> None:
    urlopen = mocker.patch("release_creator.artifacts.reconcile.urlopen")

    with pytest.raises(ValueError, match="wait_seconds must be nonnegative"):
        verify_artifacts("example", "1.0.0", dist, -1)

    urlopen.assert_not_called()


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        pytest.param(HTTPStatus.NOT_FOUND, "PyPI is missing files", id="release-absent"),
        pytest.param(HTTPStatus.FORBIDDEN, "HTTP Error 403", id="access-denied"),
        pytest.param(HTTPStatus.SERVICE_UNAVAILABLE, "HTTP Error 503", id="server-error"),
    ],
)
def test_verify_http_failures(code: HTTPStatus, expected: str, dist: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "release_creator.artifacts.reconcile.urlopen",
        side_effect=HTTPError("https://pypi.org", code, "failure", Message(), None),
    )

    with pytest.raises((ValueError, HTTPError), match=expected):
        reconcile_artifacts("example", "1.0.0", dist, "verify")


def test_stage_rejects_different_remote_digest(dist: Path, tmp_path: Path, mocker: MockerFixture) -> None:
    response = json.loads(remote_response(dist, "example-1.0.0-py3-none-any.whl").getvalue())
    response["urls"][0]["digests"]["sha256"] = "0" * 64
    mocker.patch("release_creator.artifacts.reconcile.urlopen", return_value=io.BytesIO(json.dumps(response).encode()))

    with pytest.raises(ValueError, match="different SHA256 digests"):
        reconcile_artifacts("example", "1.0.0", dist, "stage", tmp_path / "missing")


def test_stage_rejects_unexpected_remote_file(dist: Path, tmp_path: Path, mocker: MockerFixture) -> None:
    response = json.loads(remote_response(dist, "example-1.0.0-py3-none-any.whl").getvalue())
    response["urls"][0]["filename"] = "example-1.0.0-cp315-cp315-win_amd64.whl"
    mocker.patch("release_creator.artifacts.reconcile.urlopen", return_value=io.BytesIO(json.dumps(response).encode()))

    with pytest.raises(ValueError, match="PyPI has unexpected files"):
        reconcile_artifacts("example", "1.0.0", dist, "stage", tmp_path / "missing")


def test_stage_rejects_yanked_remote_file(dist: Path, tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "release_creator.artifacts.reconcile.urlopen",
        return_value=remote_response(dist, "example-1.0.0-py3-none-any.whl", yanked=True),
    )

    with pytest.raises(ValueError, match="release file is yanked"):
        reconcile_artifacts("example", "1.0.0", dist, "stage", tmp_path / "missing")


def test_stage_rejects_empty_dist(tmp_path: Path, mocker: MockerFixture) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / ".gitignore").write_text("*\n", encoding="utf-8")
    urlopen = mocker.patch("release_creator.artifacts.reconcile.urlopen")

    with pytest.raises(ValueError, match="artifact directory is empty"):
        reconcile_artifacts("example", "1.0.0", dist, "stage", tmp_path / "missing")

    urlopen.assert_not_called()


def test_stage_ignores_hidden_build_metadata(dist: Path, tmp_path: Path, mocker: MockerFixture) -> None:
    (dist / ".gitignore").write_text("*\n", encoding="utf-8")
    mocker.patch(
        "release_creator.artifacts.reconcile.urlopen",
        side_effect=HTTPError("https://pypi.org", HTTPStatus.NOT_FOUND, "missing", Message(), None),
    )

    count = reconcile_artifacts("example", "1.0.0", dist, "stage", tmp_path / "missing")

    expected_file_count = 2
    assert count == expected_file_count
    assert not (tmp_path / "missing" / ".gitignore").exists()


@pytest.mark.parametrize(
    ("filename", "error"),
    [
        pytest.param("notes.txt", "invalid artifact filename", id="nonartifact"),
        pytest.param("other-1.0.0.tar.gz", "another project or version", id="wrong-project"),
        pytest.param("example-2.0.0.tar.gz", "another project or version", id="wrong-version"),
    ],
)
def test_stage_rejects_invalid_local_file(
    filename: str, error: str, dist: Path, tmp_path: Path, mocker: MockerFixture
) -> None:
    (dist / filename).write_bytes(b"extra")
    urlopen = mocker.patch("release_creator.artifacts.reconcile.urlopen")

    with pytest.raises(ValueError, match=error):
        reconcile_artifacts("example", "1.0.0", dist, "stage", tmp_path / "missing")

    urlopen.assert_not_called()


def test_stage_rejects_symlink(dist: Path, tmp_path: Path, mocker: MockerFixture) -> None:
    (dist / "example-1.0.0-py3-none-any-copy.whl").symlink_to(dist / "example-1.0.0-py3-none-any.whl")
    urlopen = mocker.patch("release_creator.artifacts.reconcile.urlopen")

    with pytest.raises(ValueError, match="invalid artifact path"):
        reconcile_artifacts("example", "1.0.0", dist, "stage", tmp_path / "missing")

    urlopen.assert_not_called()


def test_stage_rejects_missing_dist(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="artifact directory does not exist"):
        reconcile_artifacts("example", "1.0.0", tmp_path / "missing", "stage", tmp_path / "stage")


@pytest.mark.parametrize(
    ("project", "version"),
    [pytest.param("../example", "1.0.0", id="invalid-project"), pytest.param("example", "bad", id="invalid-version")],
)
def test_stage_rejects_invalid_target(project: str, version: str, dist: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="invalid PyPI project or version"):
        reconcile_artifacts(project, version, dist, "stage", tmp_path / "missing")


def test_stage_rejects_existing_missing_dir(dist: Path, tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "release_creator.artifacts.reconcile.urlopen",
        return_value=remote_response(dist, "example-1.0.0-py3-none-any.whl"),
    )
    missing = tmp_path / "missing"
    missing.mkdir()

    with pytest.raises(FileExistsError):
        reconcile_artifacts("example", "1.0.0", dist, "stage", missing)


def test_stage_rejects_missing_dir_inside_dist(dist: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "release_creator.artifacts.reconcile.urlopen",
        return_value=remote_response(dist, "example-1.0.0-py3-none-any.whl"),
    )

    with pytest.raises(ValueError, match="outside dist"):
        reconcile_artifacts("example", "1.0.0", dist, "stage", dist / "stage")


def test_stage_rejects_file_changed_during_copy(dist: Path, tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch(
        "release_creator.artifacts.reconcile.urlopen",
        side_effect=HTTPError("https://pypi.org", HTTPStatus.NOT_FOUND, "missing", Message(), None),
    )

    def corrupt_copy(_source: Path, target: Path) -> None:
        target.write_bytes(b"changed")

    mocker.patch("release_creator.artifacts.reconcile.shutil.copyfile", side_effect=corrupt_copy)

    with pytest.raises(ValueError, match="artifact changed while staging"):
        reconcile_artifacts("example", "1.0.0", dist, "stage", tmp_path / "missing")


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        pytest.param({}, "no release files", id="missing-urls"),
        pytest.param({"urls": []}, "no release files", id="empty-urls"),
        pytest.param({"urls": [None]}, "invalid release file", id="invalid-item"),
        pytest.param({"urls": [{"filename": "x"}]}, "invalid filename", id="missing-digest"),
        pytest.param(
            {"urls": [{"filename": "x", "digests": {"sha256": "wrong"}}]}, "invalid filename", id="bad-digest"
        ),
        pytest.param(
            {"urls": [{"filename": "x", "digests": {"sha256": "0" * 64}}] * 2},
            "invalid filename",
            id="duplicate-filename",
        ),
    ],
)
def test_stage_rejects_malformed_pypi_response(
    payload: dict[str, object], error: str, dist: Path, tmp_path: Path, mocker: MockerFixture
) -> None:
    mocker.patch("release_creator.artifacts.reconcile.urlopen", return_value=io.BytesIO(json.dumps(payload).encode()))

    with pytest.raises((ValueError, TypeError), match=error):
        reconcile_artifacts("example", "1.0.0", dist, "stage", tmp_path / "missing")

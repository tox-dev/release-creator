"""Hashed build selection behavior."""

import sys
from typing import TYPE_CHECKING

import pytest
import tomli_w

from release_creator.build_constraints.render import write_build_constraints
from release_creator.cli import main

if TYPE_CHECKING:
    from pathlib import Path


def _lock(tmp_path: Path, packages: list[dict[str, object]], *, groups: list[str] | None = None) -> Path:
    lock = tmp_path / "pylock.toml"
    lock.write_text(
        tomli_w.dumps({
            "lock-version": "1.0",
            "requires-python": ">=3.15",
            "dependency-groups": groups if groups is not None else ["build"],
            "packages": packages,
        }),
        encoding="utf-8",
    )
    return lock


def _package(name: str, version: str, digest: str, marker: str | None = None) -> dict[str, object]:
    package: dict[str, object] = {
        "name": name,
        "version": version,
        "wheels": [{"url": f"https://example.org/{name}.whl", "hashes": {"sha256": digest}}],
    }
    if marker is not None:
        package["marker"] = marker
    return package


def test_build_constraints_selects_matching_markers_and_all_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = _lock(
        tmp_path,
        [
            _package("Hatchling", "1.32.4", "a" * 64, '"build" in dependency_groups and python_version >= "3.15"'),
            _package("Hatchling", "1.32.4", "b" * 64, '"build" in dependency_groups'),
            _package("Hatchling", "1.27.0", "c" * 64, '"build" in dependency_groups and python_version < "3.15"'),
            _package("other", "1.0", "d" * 64, '"release" in dependency_groups'),
        ],
    )
    output = tmp_path / "constraints.txt"
    monkeypatch.setattr(
        sys,
        "argv",
        ["release-creator", "build-constraints", "--lock", str(lock), "--output", str(output)],
    )

    main()

    assert output.read_text() == f"hatchling==1.32.4 --hash=sha256:{'a' * 64} --hash=sha256:{'b' * 64}\n"


def test_build_constraints_includes_sdist_and_wheel_hashes(tmp_path: Path) -> None:
    package = _package("meson-python", "0.22.1", "b" * 64, '"build" in dependency_groups')
    package["sdist"] = {"url": "https://example.org/meson-python.tar.gz", "hashes": {"sha256": "a" * 64}}
    lock = _lock(tmp_path, [package])
    output = tmp_path / "constraints.txt"

    write_build_constraints(lock, output)

    assert output.read_text() == f"meson-python==0.22.1 --hash=sha256:{'a' * 64} --hash=sha256:{'b' * 64}\n"


@pytest.mark.parametrize(
    ("packages", "groups", "message"),
    [
        pytest.param([_package("hatchling", "1", "a" * 64)], ["release"], "absent", id="missing-group"),
        pytest.param(
            [_package("hatchling", "1", "a" * 64, '"release" in dependency_groups')],
            ["build"],
            "selects no packages",
            id="empty-selection",
        ),
        pytest.param(
            [
                _package("hatchling", "1", "a" * 64, '"build" in dependency_groups'),
                _package("hatchling", "2", "b" * 64, '"build" in dependency_groups'),
            ],
            ["build"],
            "conflicting build pins",
            id="conflicting-version",
        ),
        pytest.param(
            [_package("hatchling", "1", "a" * 64, "not a valid marker")],
            ["build"],
            "invalid build package marker",
            id="invalid-marker",
        ),
        pytest.param(
            [{"name": "hatchling", "version": "1", "marker": '"build" in dependency_groups'}],
            ["build"],
            "no artifacts",
            id="no-artifacts",
        ),
        pytest.param(
            [_package("hatchling", "1", "bad", '"build" in dependency_groups')],
            ["build"],
            "without a SHA256 hash",
            id="bad-hash",
        ),
    ],
)
def test_build_constraints_rejects_incomplete_selection(
    packages: list[dict[str, object]], groups: list[str], message: str, tmp_path: Path
) -> None:
    lock = _lock(tmp_path, packages, groups=groups)
    output = tmp_path / "constraints.txt"

    with pytest.raises(ValueError, match=message):
        write_build_constraints(lock, output)

    assert not output.exists()


def test_build_constraints_rejects_unsupported_python(tmp_path: Path) -> None:
    lock = _lock(tmp_path, [_package("hatchling", "1", "a" * 64)])
    lock.write_text(lock.read_text().replace('requires-python = ">=3.15"', 'requires-python = ">=3.16"'))

    with pytest.raises(ValueError, match="outside"):
        write_build_constraints(lock, tmp_path / "constraints.txt")


def test_build_constraints_rejects_missing_lock_field(tmp_path: Path) -> None:
    lock = tmp_path / "pylock.toml"
    lock.write_text('lock-version = "1.0"\n')

    with pytest.raises(ValueError, match="missing dependency-groups"):
        write_build_constraints(lock, tmp_path / "constraints.txt")


@pytest.mark.parametrize(
    ("name", "version", "message"),
    [
        pytest.param("invalid name!", "1", "name is invalid", id="invalid-name"),
        pytest.param("hatchling", "invalid version!", "Invalid version", id="invalid-version"),
    ],
)
def test_build_constraints_rejects_invalid_pin(name: str, version: str, message: str, tmp_path: Path) -> None:
    lock = _lock(tmp_path, [_package(name, version, "a" * 64)])

    with pytest.raises(ValueError, match=message):
        write_build_constraints(lock, tmp_path / "constraints.txt")

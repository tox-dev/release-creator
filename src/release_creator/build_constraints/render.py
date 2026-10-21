"""Select build artifacts whose lock markers match this runner."""

import sys
lazy import tomllib
lazy from pathlib import Path
lazy from typing import Any, Final

lazy from packaging.markers import InvalidMarker, Marker
lazy from packaging.specifiers import SpecifierSet
lazy from packaging.utils import canonicalize_name
lazy from packaging.version import Version

_SHA256_LENGTH: Final = 64


def write_build_constraints(lock: Path, output: Path, group: str = "build") -> None:
    """Write exact build pins with all available artifact hashes.

    Raises:
        ValueError: The lock cannot provide a complete build selection.

    """
    data = tomllib.loads(lock.read_text(encoding="utf-8"))
    try:
        groups = data["dependency-groups"]
        requires_python = data["requires-python"]
        packages = data["packages"]
    except KeyError as error:
        msg = f"invalid lock: missing {error.args[0]}"
        raise ValueError(msg) from error
    if group not in groups:
        msg = f"build group {group!r} is absent from {lock}"
        raise ValueError(msg)
    if f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}" not in SpecifierSet(
        requires_python
    ):
        msg = f"current Python is outside {lock}'s requires-python range"
        raise ValueError(msg)
    selected: dict[str, tuple[str, set[str]]] = {}
    for package in packages:
        if not _matches(package.get("marker"), group):
            continue
        name = canonicalize_name(package["name"], validate=True)
        version = str(Version(package["version"]))
        hashes = _hashes(package)
        if name in selected:
            current_version, current_hashes = selected[name]
            if current_version != version:
                msg = f"conflicting build pins for {name}: {current_version} and {version}"
                raise ValueError(msg)
            current_hashes.update(hashes)
        else:
            selected[name] = (version, hashes)
    if not selected:
        msg = f"build group {group!r} selects no packages in {lock}"
        raise ValueError(msg)
    output.write_text(
        "".join(
            f"{name}=={version} " + " ".join(f"--hash=sha256:{digest}" for digest in sorted(hashes)) + "\n"
            for name, (version, hashes) in sorted(selected.items())
        ),
        encoding="utf-8",
    )


def _matches(marker: str | None, group: str) -> bool:
    if marker is None:
        return True
    try:
        return Marker(marker).evaluate(environment={"dependency_groups": frozenset({group})}, context="lock_file")
    except InvalidMarker as error:
        msg = f"invalid build package marker: {marker}"
        raise ValueError(msg) from error


def _hashes(package: dict[str, Any]) -> set[str]:
    files = [*([package["sdist"]] if "sdist" in package else []), *package.get("wheels", [])]
    if not files:
        msg = f"build package {package['name']} has no artifacts"
        raise ValueError(msg)
    hashes: set[str] = set()
    for file in files:
        digest = file.get("hashes", {}).get("sha256")
        if (
            not isinstance(digest, str)
            or len(digest) != _SHA256_LENGTH
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            msg = f"build package {package['name']} has an artifact without a SHA256 hash"
            raise ValueError(msg)
        hashes.add(digest)
    return hashes


__all__ = [
    "write_build_constraints",
]

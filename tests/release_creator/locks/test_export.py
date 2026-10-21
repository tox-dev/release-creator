"""Selectable lock export behavior."""

import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Process results are uv's test boundary.
import sys
import tomllib
from typing import TYPE_CHECKING

import pytest
lazy from pytest_mock import MockerFixture

lazy from release_creator.cli import main
lazy from release_creator.locks.export import export_lock

if TYPE_CHECKING:
    from pathlib import Path


def test_export_lock_keeps_group_and_extra_membership(
    tmp_path: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(
        '[project]\nname = "demo"\nversion = "1.0"\nrequires-python = ">=3.11"\n'
        '[project.optional-dependencies]\ncli = ["shared"]\n'
        '[dependency-groups]\ntest = ["shared"]\nrelease = ["release-tool"]\n'
    )
    mocker.patch("shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "subprocess.run",
        side_effect=[
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, '[[packages]]\nname = "runtime"\nversion = "1.0"\n', ""),
            subprocess.CompletedProcess([], 0, '[[packages]]\nname = "shared"\nversion = "2.0"\n', ""),
            subprocess.CompletedProcess(
                [],
                0,
                '[[packages]]\nname = "release-tool"\nversion = "3.0"\nmarker = "python_version >= \'3.15\'"\n',
                "",
            ),
            subprocess.CompletedProcess([], 0, '[[packages]]\nname = "shared"\nversion = "2.0"\n', ""),
        ],
    )

    monkeypatch.setattr(
        sys, "argv", ["release-creator", "locks", "--project", str(project), "--output", str(tmp_path / "pylock.toml")]
    )
    main()

    lock = tomllib.loads((tmp_path / "pylock.toml").read_text())
    assert {key: lock[key] for key in ("requires-python", "dependency-groups", "default-groups", "extras")} == {
        "requires-python": ">=3.11",
        "dependency-groups": ["project-runtime", "test", "release"],
        "default-groups": [],
        "extras": ["cli"],
    }
    assert [(package["name"], package["marker"]) for package in lock["packages"]] == [
        ("release-tool", "(\"release\" in dependency_groups and (python_version >= '3.15'))"),
        ("runtime", '"project-runtime" in dependency_groups'),
        ("shared", '"cli" in extras or "test" in dependency_groups'),
    ]


def test_export_lock_adds_marker_scoped_build_requirements(
    tmp_path: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(
        '[build-system]\nrequires = ["meson-python>=0.22"]\nbuild-backend = "mesonpy"\n'
        '[project]\nname = "demo"\nversion = "1.0"\nrequires-python = ">=3.11"\n'
    )
    mocker.patch("shutil.which", return_value="/usr/bin/uv")
    run = mocker.patch(
        "subprocess.run",
        side_effect=[
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, "packages = []\n", ""),
            subprocess.CompletedProcess(
                [],
                0,
                '[[packages]]\nname = "meson-python"\nversion = "0.22.1"\n'
                '[[packages]]\nname = "patchelf"\nversion = "0.17.2"\nmarker = "sys_platform == \'linux\'"\n',
                "",
            ),
        ],
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release-creator",
            "locks",
            "--project",
            str(project),
            "--output",
            str(tmp_path / "pylock.toml"),
            "--build-requirement",
            'patchelf>=0.11; sys_platform == "linux"',
            "--exclude-newer-package",
            "release-creator=2026-10-21T00:00:00Z",
            "--exclude-newer-package",
            "pytest-mock=2026-10-21T00:00:00Z",
        ],
    )
    main()

    lock = tomllib.loads((tmp_path / "pylock.toml").read_text())
    assert lock["dependency-groups"] == ["project-runtime", "build"]
    assert [(package["name"], package["marker"]) for package in lock["packages"]] == [
        ("meson-python", '"build" in dependency_groups'),
        ("patchelf", "(\"build\" in dependency_groups and (sys_platform == 'linux'))"),
    ]
    assert run.call_args_list[2].args[0] == [
        "/usr/bin/uv",
        "pip",
        "compile",
        "-",
        "--universal",
        "--python-version",
        "3.11",
        "--format",
        "pylock.toml",
        "--exclude-newer-package",
        "release-creator=2026-10-21T00:00:00Z",
        "--exclude-newer-package",
        "pytest-mock=2026-10-21T00:00:00Z",
    ]
    assert run.call_args_list[2].kwargs["input"] == ('meson-python>=0.22\npatchelf>=0.11; sys_platform == "linux"\n')
    assert run.call_args_list[0].args[0] == [
        "/usr/bin/uv",
        "lock",
        "--upgrade",
        "--exclude-newer-package",
        "release-creator=2026-10-21T00:00:00Z",
        "--exclude-newer-package",
        "pytest-mock=2026-10-21T00:00:00Z",
    ]
    assert run.call_args_list[1].args[0][-4:] == [
        "--exclude-newer-package",
        "release-creator=2026-10-21T00:00:00Z",
        "--exclude-newer-package",
        "pytest-mock=2026-10-21T00:00:00Z",
    ]


def test_export_lock_merges_default_index_build_overlap(
    tmp_path: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(
        '[build-system]\nrequires = ["packaging"]\nbuild-backend = "hatchling.build"\n'
        '[project]\nname = "demo"\nversion = "1.0"\nrequires-python = ">=3.15"\n'
        'dependencies = ["packaging"]\n',
        encoding="utf-8",
    )
    mocker.patch("shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "subprocess.run",
        side_effect=[
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess(
                [], 0, '[[packages]]\nname = "packaging"\nversion = "26.3"\nindex = "https://pypi.org/simple"\n', ""
            ),
            subprocess.CompletedProcess([], 0, '[[packages]]\nname = "packaging"\nversion = "26.3"\n', ""),
        ],
    )

    monkeypatch.setattr(
        sys, "argv", ["release-creator", "locks", "--project", str(project), "--output", str(tmp_path / "pylock.toml")]
    )
    main()

    assert tomllib.loads((tmp_path / "pylock.toml").read_text())["packages"] == [
        {
            "name": "packaging",
            "version": "26.3",
            "index": "https://pypi.org/simple",
            "marker": '"build" in dependency_groups or "project-runtime" in dependency_groups',
        }
    ]


def test_export_lock_removes_generated_uv_lock(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text("[project]\nname = 'demo'\nversion = '1.0'\nrequires-python = '>=3.15'\n")

    export_lock(project, tmp_path / "pylock.toml")

    assert (tmp_path / "pylock.toml").exists()
    assert not (tmp_path / "uv.lock").exists()


def test_export_lock_accepts_tool_only_project(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text("[dependency-groups]\nrelease = []\n")

    export_lock(project, tmp_path / "pylock.toml", ">=3.15")

    lock = tomllib.loads((tmp_path / "pylock.toml").read_text())
    assert (lock["requires-python"], lock["dependency-groups"]) == (">=3.15", ["project-runtime", "release"])


def test_export_lock_includes_workspace_groups(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[tool.uv.workspace]\nmembers = ["one", "two"]\n')
    for name, group in (("one", "test"), ("two", "release")):
        directory = tmp_path / name
        directory.mkdir()
        (directory / "pyproject.toml").write_text(
            f"[project]\nname = '{name}'\nversion = '1.0'\nrequires-python = '>=3.11'\n"
            f"[dependency-groups]\n{group} = []\n"
        )

    export_lock(project, tmp_path / "pylock.toml")

    lock = tomllib.loads((tmp_path / "pylock.toml").read_text())
    assert (lock["requires-python"], lock["dependency-groups"]) == (">=3.11", ["project-runtime", "test", "release"])


def test_export_lock_rejects_workspace_python_mismatch(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[tool.uv.workspace]\nmembers = ["one", "two"]\n')
    for name, python in (("one", ">=3.11"), ("two", ">=3.12")):
        directory = tmp_path / name
        directory.mkdir()
        (directory / "pyproject.toml").write_text(
            f"[project]\nname = '{name}'\nversion = '1.0'\nrequires-python = '{python}'\n"
        )

    with pytest.raises(ValueError, match="workspace members must share"):
        export_lock(project, tmp_path / "pylock.toml")


@pytest.mark.parametrize(
    ("project_text", "message"),
    [
        pytest.param("[project]\nname = 'demo'\n", "requires-python", id="missing-python-range"),
        pytest.param(
            "[project]\nname = 'demo'\nrequires-python = '>=3.11'\n[dependency-groups]\nproject-runtime = []\n",
            "project-runtime is reserved",
            id="reserved-group",
        ),
        pytest.param(
            "[build-system]\nrequires = ['hatchling']\n[project]\nname = 'demo'\nrequires-python = '>=3.11'\n"
            "[dependency-groups]\nbuild = []\n",
            "build is reserved",
            id="reserved-build-group",
        ),
        pytest.param(
            "[build-system]\nrequires = ['invalid requirement!']\n"
            "[project]\nname = 'demo'\nrequires-python = '>=3.11'\n",
            "invalid build requirement",
            id="invalid-build-requirement",
        ),
    ],
)
def test_export_lock_rejects_invalid_project(
    project_text: str, message: str, tmp_path: Path, mocker: MockerFixture
) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(project_text)
    process = mocker.patch("subprocess.run")

    with pytest.raises(ValueError, match=message):
        export_lock(project, tmp_path / "pylock.toml")

    process.assert_not_called()


def test_export_lock_requires_uv(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text("[project]\nname = 'demo'\nrequires-python = '>=3.11'\n")
    mocker.patch("shutil.which", return_value=None)

    with pytest.raises(FileNotFoundError, match="uv is required"):
        export_lock(project, tmp_path / "pylock.toml")


def test_export_lock_keeps_existing_uv_lock(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text("[project]\nname = 'demo'\nrequires-python = '>=3.11'\n")
    (tmp_path / "uv.lock").write_text("existing")
    mocker.patch("shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "subprocess.run",
        side_effect=[
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, "packages = []\n", ""),
        ],
    )

    export_lock(project, tmp_path / "pylock.toml")

    assert (tmp_path / "uv.lock").read_text() == "existing"


def test_export_lock_restores_existing_uv_lock_after_later_failure(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(
        "[build-system]\nrequires = ['hatchling']\n"
        "[project]\nname = 'demo'\nversion = '1.0'\nrequires-python = '>=3.15'\n"
    )
    lock_path = tmp_path / "uv.lock"
    lock_path.write_text("reviewed lock")
    output = tmp_path / "pylock.toml"
    output.write_text("reviewed export")
    mocker.patch("shutil.which", return_value="/usr/bin/uv")

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if command[1] == "lock":
            lock_path.write_text("unreviewed upgrade")
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[1] == "export":
            return subprocess.CompletedProcess(command, 0, "packages = []\n", "")
        return subprocess.CompletedProcess(command, 1, "", "build resolver failed")

    mocker.patch("subprocess.run", side_effect=run)

    with pytest.raises(ValueError, match="build resolver failed"):
        export_lock(project, output)

    assert (lock_path.read_text(), output.read_text()) == ("reviewed lock", "reviewed export")


def test_export_lock_reports_uv_failure(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text("[project]\nname = 'demo'\nrequires-python = '>=3.11'\n")
    mocker.patch("shutil.which", return_value="/usr/bin/uv")
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", "invalid project"))

    with pytest.raises(ValueError, match="invalid project"):
        export_lock(project, tmp_path / "pylock.toml")

    assert not (tmp_path / "uv.lock").exists()


def test_export_lock_rejects_unbounded_build_python(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(
        "[build-system]\nrequires = ['hatchling']\n[project]\nname = 'demo'\nrequires-python = '<3.16'\n"
    )
    mocker.patch("shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "subprocess.run",
        side_effect=[
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, "packages = []\n", ""),
        ],
    )

    with pytest.raises(ValueError, match="cannot infer the minimum Python version"):
        export_lock(project, tmp_path / "pylock.toml")

    assert not (tmp_path / "pylock.toml").exists()

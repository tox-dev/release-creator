"""Selectable lock export behavior."""

import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Process results are uv's test boundary.
import sys
import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

import pytest
import tomli_w
lazy from pytest_mock import MockerFixture
lazy from yaml import safe_load

lazy from release_creator.cli import main
lazy from release_creator.locks.export import export_lock


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
            _UV_VERSION,
            subprocess.CompletedProcess([], 0, _dated('[[packages]]\nname = "runtime"\nversion = "1.0"\n'), ""),
            subprocess.CompletedProcess([], 0, _dated('[[packages]]\nname = "shared"\nversion = "2.0"\n'), ""),
            subprocess.CompletedProcess(
                [],
                0,
                _dated('[[packages]]\nname = "release-tool"\nversion = "3.0"\nmarker = "python_version >= \'3.15\'"\n'),
                "",
            ),
            subprocess.CompletedProcess([], 0, _dated('[[packages]]\nname = "shared"\nversion = "2.0"\n'), ""),
        ],
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["release-creator", "locks"])
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


def test_export_lock_isolates_uv_resolution_settings(
    tmp_path: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n')
    monkeypatch.setenv("UV_INDEX_URL", "https://unapproved.invalid/simple/")
    monkeypatch.setenv("PIP_INDEX_URL", "https://unapproved.invalid/simple/")
    mocker.patch("shutil.which", return_value="uv")
    run = mocker.patch(
        "subprocess.run",
        autospec=True,
        side_effect=[
            _UV_VERSION,
            subprocess.CompletedProcess([], 0, "packages = []\n", ""),
        ],
    )

    export_lock(tmp_path)

    assert all(
        {"--no-config", "--no-sources", "--default-index"} <= set(call.args[0])
        and call.args[0][call.args[0].index("--default-index") + 1] == "https://pypi.org/simple/"
        and all("unapproved.invalid" not in value for value in call.kwargs["env"].values())
        for call in run.call_args_list[1:]
    )


@pytest.mark.parametrize("field", ["dependencies", "optional-dependencies"])
def test_export_lock_rejects_dynamic_dependency_metadata(tmp_path: Path, field: str) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(
        '[build-system]\nrequires = ["setuptools"]\nbuild-backend = "setuptools.build_meta"\n'
        '[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n'
        f'dynamic = ["{field}"]\n'
        '[tool.setuptools.dynamic]\ndependencies = {file = ["requirements.txt"]}\n'
    )
    (tmp_path / "requirements.txt").write_text("packaging>=24\n")

    with pytest.raises(ValueError, match="dynamic project dependencies"):
        export_lock(tmp_path)

    assert not (tmp_path / "pylock.toml").exists()


def test_export_lock_rejects_legacy_uv_dev_dependencies(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(
        '[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n'
        '[tool.uv]\ndev-dependencies = ["pytest>=9"]\n'
    )

    with pytest.raises(ValueError, match=r"legacy tool\.uv\.dev-dependencies"):
        export_lock(tmp_path)

    assert not (tmp_path / "pylock.toml").exists()


def test_export_lock_rejects_workspace_source_without_member(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(
        '[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n'
        'dependencies = ["packaging>=24"]\n'
        "[tool.uv.sources]\npackaging = {workspace = true}\n"
    )

    with pytest.raises(ValueError, match="declared workspace members"):
        export_lock(tmp_path)

    assert not (tmp_path / "pylock.toml").exists()


def test_export_lock_selects_extra_marker_without_losing_platform_marker(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(
        '[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n'
        "[project.optional-dependencies]\n"
        "cli = [\"packaging==24.2; extra == 'cli'\", "
        "\"colorama==0.4.6; extra == 'cli' and sys_platform == 'win32'\"]\n"
    )

    output = tmp_path / "pylock.toml"
    export_lock(tmp_path)
    packages = {package["name"]: package for package in tomllib.loads(output.read_text())["packages"]}

    assert '"cli" in extras' in packages["packaging"]["marker"]
    assert '"cli" in extras' in packages["colorama"]["marker"]
    assert "win32" in packages["colorama"]["marker"]
    assert all('"project-runtime" in dependency_groups' not in package["marker"] for package in packages.values())


@pytest.mark.parametrize("pattern", ["../external", "members/external"])
def test_export_lock_rejects_workspace_member_outside_project(tmp_path: Path, pattern: str) -> None:
    root = tmp_path / "project"
    root.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    (external / "pyproject.toml").write_text('[project]\nname = "external"\nrequires-python = ">=3.15"\n')
    if pattern.startswith("members/"):
        (root / "members").mkdir()
        (root / "members" / "external").symlink_to(external, target_is_directory=True)
    project = root / "pyproject.toml"
    project.write_text(f'[tool.uv.workspace]\nmembers = ["{pattern}"]\n')

    with pytest.raises(ValueError, match="workspace path is outside the project"):
        export_lock(root)

    assert not (root / "pylock.toml").exists()


def test_export_lock_rejects_non_pypi_source(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n')
    mocker.patch("shutil.which", return_value="uv")
    mocker.patch(
        "subprocess.run",
        autospec=True,
        side_effect=[
            _UV_VERSION,
            subprocess.CompletedProcess(
                [],
                0,
                '[[packages]]\nname = "source-package"\nversion = "1"\n'
                '[packages.archive]\nurl = "https://unapproved.invalid/package.whl"\n',
                "",
            ),
        ],
    )

    with pytest.raises(ValueError, match="non-PyPI package source"):
        export_lock(tmp_path)

    assert not (tmp_path / "pylock.toml").exists()


def test_export_lock_rejects_package_without_artifacts(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n')
    mocker.patch("shutil.which", return_value="uv")
    mocker.patch(
        "subprocess.run",
        autospec=True,
        side_effect=[
            _UV_VERSION,
            subprocess.CompletedProcess([], 0, '[[packages]]\nname = "source-package"\nversion = "1"\n', ""),
        ],
    )

    with pytest.raises(ValueError, match="no dated artifacts"):
        export_lock(tmp_path)


@pytest.mark.parametrize(
    ("invalid", "message"),
    [
        pytest.param("url", "non-PyPI artifact", id="artifact-host"),
        pytest.param("upload-time", "no upload time", id="missing-upload-time"),
        pytest.param("sha256", "no SHA-256", id="missing-hash"),
        pytest.param("index", "unapproved index", id="index"),
    ],
)
def test_export_lock_rejects_untrusted_package_record(
    tmp_path: Path, mocker: MockerFixture, invalid: str, message: str
) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n')
    data = tomllib.loads(_dated('[[packages]]\nname = "six"\nversion = "1.17.0"\n'))
    package = data["packages"][0]
    if invalid == "index":
        package["index"] = "https://unapproved.invalid/simple/"
    elif invalid == "sha256":
        del package["sdist"]["hashes"]["sha256"]
    elif invalid == "upload-time":
        del package["sdist"]["upload-time"]
    else:
        package["sdist"]["url"] = "https://unapproved.invalid/six.tar.gz"
    mocker.patch("shutil.which", return_value="uv")
    mocker.patch(
        "subprocess.run",
        autospec=True,
        side_effect=[
            _UV_VERSION,
            subprocess.CompletedProcess([], 0, tomli_w.dumps(data), ""),
        ],
    )

    with pytest.raises(ValueError, match=message):
        export_lock(tmp_path)


def test_export_lock_selects_all_workspace_runtime_dependencies(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(
        '[project]\nname = "bare"\nversion = "1"\nrequires-python = ">=3.15"\n[tool.uv.workspace]\nmembers = ["meta"]\n'
    )
    member = tmp_path / "meta"
    member.mkdir()
    (member / "pyproject.toml").write_text(
        '[project]\nname = "meta"\nversion = "1"\nrequires-python = ">=3.15"\n'
        'dependencies = ["bare==1", "packaging==24.2"]\n'
        "[tool.uv.sources]\nbare = { workspace = true }\n"
    )
    mocker.patch("shutil.which", return_value="uv")
    run = mocker.patch(
        "subprocess.run",
        autospec=True,
        side_effect=[
            _UV_VERSION,
            subprocess.CompletedProcess(
                [],
                0,
                _dated(
                    '[[packages]]\nname = "bare"\nversion = "1.0"\n[[packages]]\nname = "packaging"\nversion = "24.2"\n'
                ),
                "",
            ),
        ],
    )

    export_lock(tmp_path)

    assert [
        (package["name"], package["marker"])
        for package in tomllib.loads((tmp_path / "pylock.toml").read_text())["packages"]
    ] == [
        ("bare", '"project-runtime" in dependency_groups'),
        ("packaging", '"project-runtime" in dependency_groups'),
    ]
    assert {"pip", "compile", "--no-sources"} <= set(run.call_args_list[1].args[0])
    assert run.call_args_list[1].kwargs["input"] == "bare==1\npackaging==24.2\n"


def test_export_lock_keeps_published_self_dependency_in_group(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(
        '[project]\nname = "virtualenv"\nversion = "1"\nrequires-python = ">=3.15"\n'
        '[dependency-groups]\nrelease-build = ["tox==4.66.0"]\n'
    )
    mocker.patch("shutil.which", return_value="/usr/bin/uv")
    run = mocker.patch(
        "subprocess.run",
        autospec=True,
        side_effect=[
            _UV_VERSION,
            subprocess.CompletedProcess([], 0, "packages = []\n", ""),
            subprocess.CompletedProcess(
                [],
                0,
                _dated(
                    '[[packages]]\nname = "tox"\nversion = "4.66.0"\n'
                    '[[packages]]\nname = "virtualenv"\nversion = "21.14.8"\n'
                ),
                "",
            ),
        ],
    )

    export_lock(tmp_path)

    assert [
        (package["name"], package["marker"])
        for package in tomllib.loads((tmp_path / "pylock.toml").read_text())["packages"]
    ] == [
        ("tox", '"release-build" in dependency_groups'),
        ("virtualenv", '"release-build" in dependency_groups'),
    ]
    assert run.call_args_list[2].args[0][:3] == ["/usr/bin/uv", "pip", "compile"]
    assert run.call_args_list[2].args[0][3:5] == ["--group", f"{project}:release-build"]


def test_export_lock_adds_marker_scoped_build_requirements(
    tmp_path: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(
        '[build-system]\nrequires = ["meson-python>=0.22", \'patchelf>=0.11; sys_platform == "linux"\']\n'
        'build-backend = "mesonpy"\n'
        '[project]\nname = "demo"\nversion = "1.0"\nrequires-python = ">=3.11"\n'
        "[tool.release-creator.locks.exclude-newer-package]\n"
        'release-creator = "2026-10-21T00:00:00Z"\npytest-mock = "2026-10-21T00:00:00Z"\n'
    )
    mocker.patch("shutil.which", return_value="/usr/bin/uv")
    run = mocker.patch(
        "subprocess.run",
        side_effect=[
            _UV_VERSION,
            subprocess.CompletedProcess([], 0, "packages = []\n", ""),
            subprocess.CompletedProcess(
                [],
                0,
                _dated(
                    '[[packages]]\nname = "meson-python"\nversion = "0.22.1"\n'
                    '[[packages]]\nname = "patchelf"\nversion = "0.17.2"\nmarker = "sys_platform == \'linux\'"\n'
                ),
                "",
            ),
        ],
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["release-creator", "locks"])
    main()

    lock = tomllib.loads((tmp_path / "pylock.toml").read_text())
    assert lock["dependency-groups"] == ["project-runtime", "build"]
    assert [(package["name"], package["marker"]) for package in lock["packages"]] == [
        ("meson-python", '"build" in dependency_groups'),
        ("patchelf", "(\"build\" in dependency_groups and (sys_platform == 'linux'))"),
    ]
    assert run.call_args_list[2].args[0][:9] == [
        "/usr/bin/uv",
        "pip",
        "compile",
        "-",
        "--universal",
        "--python-version",
        "3.11",
        "--format",
        "pylock.toml",
    ]
    assert run.call_args_list[2].args[0][-4:] == [
        "--exclude-newer-package",
        "release-creator=2026-10-21T00:00:00Z",
        "--exclude-newer-package",
        "pytest-mock=2026-10-21T00:00:00Z",
    ]
    assert run.call_args_list[2].kwargs["input"] == ('meson-python>=0.22\npatchelf>=0.11; sys_platform == "linux"\n')
    assert run.call_args_list[1].args[0][:3] == ["/usr/bin/uv", "pip", "compile"]
    assert "--exclude-newer" in run.call_args_list[1].args[0]
    assert "--no-sources" in run.call_args_list[1].args[0]
    assert run.call_args_list[1].args[0][-4:] == [
        "--exclude-newer-package",
        "release-creator=2026-10-21T00:00:00Z",
        "--exclude-newer-package",
        "pytest-mock=2026-10-21T00:00:00Z",
    ]


def test_export_lock_preserves_opposite_build_python_markers(tmp_path: Path, mocker: MockerFixture) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[build-system]\n"
        "requires = ['six==1.17.0; python_version < \"3.12\"', 'packaging==24.2; python_version >= \"3.12\"']\n"
        '[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.11"\n'
    )
    mocker.patch("shutil.which", return_value="uv")
    mocker.patch(
        "subprocess.run",
        autospec=True,
        side_effect=[
            _UV_VERSION,
            subprocess.CompletedProcess([], 0, "packages = []\n", ""),
            subprocess.CompletedProcess(
                [],
                0,
                _dated(
                    '[[packages]]\nname = "six"\nversion = "1.17.0"\nmarker = "python_full_version < \'3.12\'"\n'
                    '[[packages]]\nname = "packaging"\nversion = "24.2"\n'
                    "marker = \"python_full_version >= '3.12'\"\n"
                ),
                "",
            ),
        ],
    )

    export_lock(tmp_path)

    assert [
        (package["name"], package["marker"])
        for package in tomllib.loads((tmp_path / "pylock.toml").read_text())["packages"]
    ] == [
        ("packaging", "(\"build\" in dependency_groups and (python_full_version >= '3.12'))"),
        ("six", "(\"build\" in dependency_groups and (python_full_version < '3.12'))"),
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
            _UV_VERSION,
            subprocess.CompletedProcess(
                [],
                0,
                _dated('[[packages]]\nname = "packaging"\nversion = "26.3"\nindex = "https://pypi.org/simple"\n'),
                "",
            ),
            subprocess.CompletedProcess([], 0, _dated('[[packages]]\nname = "packaging"\nversion = "26.3"\n'), ""),
        ],
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["release-creator", "locks"])
    main()

    assert [
        (package["name"], package["index"], package["marker"])
        for package in tomllib.loads((tmp_path / "pylock.toml").read_text())["packages"]
    ] == [
        (
            "packaging",
            "https://pypi.org/simple/",
            '"build" in dependency_groups or "project-runtime" in dependency_groups',
        )
    ]


def test_export_lock_merges_declared_build_group(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(
        '[build-system]\nrequires = ["packaging"]\nbuild-backend = "hatchling.build"\n'
        '[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n'
        '[dependency-groups]\nbuild = ["packaging"]\n'
    )
    mocker.patch("shutil.which", return_value="/usr/bin/uv")
    package = _dated('[[packages]]\nname = "packaging"\nversion = "26.3"\n')
    run = mocker.patch(
        "subprocess.run",
        autospec=True,
        side_effect=[
            _UV_VERSION,
            subprocess.CompletedProcess([], 0, "packages = []\n", ""),
            subprocess.CompletedProcess([], 0, package, ""),
        ],
    )

    export_lock(tmp_path)

    lock = tomllib.loads((tmp_path / "pylock.toml").read_text())
    assert lock["dependency-groups"] == ["project-runtime", "build"]
    assert [(package["name"], package["marker"]) for package in lock["packages"]] == [
        ("packaging", '"build" in dependency_groups')
    ]
    assert run.call_args_list[2].kwargs["input"] == "packaging\n"
    assert run.call_args_list[2].args[0][4:6] == ["--group", f"{project}:build"]


def test_export_lock_rejects_incompatible_build_requirements(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(
        '[build-system]\nrequires = ["packaging==26.3"]\nbuild-backend = "hatchling.build"\n'
        '[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n'
        '[dependency-groups]\nbuild = ["packaging==24.2"]\n'
    )

    with pytest.raises(ValueError, match="No solution found"):
        export_lock(tmp_path)

    assert not (tmp_path / "pylock.toml").exists()


def test_export_lock_records_cooling_metadata(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n')
    mocker.patch("shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "subprocess.run",
        side_effect=[
            _UV_VERSION,
            subprocess.CompletedProcess(
                [],
                0,
                '[[packages]]\nname = "six"\nversion = "1.17.0"\n'
                '[packages.sdist]\nurl = "https://files.pythonhosted.org/six-1.17.0.tar.gz"\n'
                'upload-time = 2024-12-04T10:00:00Z\n[packages.sdist.hashes]\nsha256 = "abc"\n',
                "",
            ),
        ],
    )

    export_lock(tmp_path)

    lock = tomllib.loads((tmp_path / "pylock.toml").read_text())
    assert lock["packages"][0] == {
        "name": "six",
        "version": "1.17.0",
        "index": "https://pypi.org/simple/",
        "marker": '"project-runtime" in dependency_groups',
        "sdist": {
            "url": "https://files.pythonhosted.org/six-1.17.0.tar.gz",
            "upload-time": datetime(2024, 12, 4, 10, tzinfo=UTC),
            "hashes": {"sha256": "abc"},
        },
    }
    assert lock["tool"] == {
        "release-creator": {"created-at": lock["tool"]["release-creator"]["created-at"], "uv-version": "0.13.5"}
    }


@pytest.mark.parametrize(
    ("recorded", "message"),
    [
        pytest.param('uv-version = "0.13.0"\n', "was resolved with uv 0.13.0, but uv 0.13.5 is running", id="other"),
        pytest.param("", "records no uv version, but uv 0.13.5 is running", id="absent"),
    ],
)
def test_export_lock_check_reports_uv_version_mismatch(
    tmp_path: Path, mocker: MockerFixture, recorded: str, message: str
) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n')
    (tmp_path / "pylock.toml").write_text(
        f'lock-version = "1.0"\n[tool.release-creator]\ncreated-at = 2026-10-01T00:00:00Z\n{recorded}'
    )
    mocker.patch("shutil.which", return_value="uv")
    run = mocker.patch("subprocess.run", autospec=True, side_effect=[_UV_VERSION])

    with pytest.raises(ValueError, match=message):
        export_lock(tmp_path, check=True)

    assert [call.args[0] for call in run.call_args_list] == [["uv", "--version"]]


@pytest.mark.parametrize("artifact", [pytest.param("sdist", id="sdist"), pytest.param("wheels", id="wheel")])
def test_export_lock_rejects_uncool_artifact(tmp_path: Path, mocker: MockerFixture, artifact: str) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n')
    mocker.patch("shutil.which", return_value="/usr/bin/uv")
    artifact_table = "[packages.sdist]" if artifact == "sdist" else "[[packages.wheels]]"
    mocker.patch(
        "subprocess.run",
        side_effect=[
            _UV_VERSION,
            subprocess.CompletedProcess(
                [],
                0,
                '[[packages]]\nname = "six"\nversion = "1.17.0"\n'
                f'{artifact_table}\nurl = "https://files.pythonhosted.org/six-1.17.0.tar.gz"\n'
                'upload-time = 2099-01-01T00:00:00Z\n[packages.sdist.hashes]\nsha256 = "abc"\n'
                if artifact == "sdist"
                else '[[packages]]\nname = "six"\nversion = "1.17.0"\n'
                f'{artifact_table}\nurl = "https://files.pythonhosted.org/six-1.17.0-py3-none-any.whl"\n'
                'upload-time = 2099-01-01T00:00:00Z\n[packages.wheels.hashes]\nsha256 = "abc"\n',
                "",
            ),
        ],
    )

    with pytest.raises(ValueError, match="uncooled artifact"):
        export_lock(tmp_path)

    assert not (tmp_path / "pylock.toml").exists()


def test_export_lock_honors_reviewed_package_cutoff(tmp_path: Path, mocker: MockerFixture) -> None:
    reviewed = datetime.now(tz=UTC) - timedelta(days=1)
    project = tmp_path / "pyproject.toml"
    project.write_text(
        '[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n'
        f'[tool.release-creator.locks.exclude-newer-package]\nsix = "{reviewed.isoformat()}"\n'
    )
    mocker.patch("shutil.which", return_value="/usr/bin/uv")
    run = mocker.patch(
        "subprocess.run",
        side_effect=[
            _UV_VERSION,
            subprocess.CompletedProcess(
                [],
                0,
                '[[packages]]\nname = "six"\nversion = "1.17.0"\n'
                '[packages.sdist]\nurl = "https://files.pythonhosted.org/six-1.17.0.tar.gz"\n'
                f'upload-time = {reviewed.isoformat()}\n[packages.sdist.hashes]\nsha256 = "abc"\n',
                "",
            ),
        ],
    )

    export_lock(tmp_path)

    assert run.call_args_list[1].args[0][-2:] == ["--exclude-newer-package", f"six={reviewed.isoformat()}"]


def test_export_lock_rejects_invalid_package_cutoff(tmp_path: Path, mocker: MockerFixture) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n'
        '[tool.release-creator.locks]\nexclude-newer-package = "invalid"\n'
    )
    run = mocker.patch("subprocess.run", autospec=True)

    with pytest.raises(TypeError, match="must map package names"):
        export_lock(tmp_path)

    run.assert_not_called()


def test_export_lock_rejects_future_reviewed_cutoff(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(
        '[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n'
        '[tool.release-creator.locks.exclude-newer-package]\nsix = "2099-01-01T00:00:00Z"\n'
    )
    mocker.patch("shutil.which", return_value="uv")
    mocker.patch(
        "subprocess.run",
        autospec=True,
        side_effect=[
            _UV_VERSION,
            subprocess.CompletedProcess([], 0, _dated('[[packages]]\nname = "six"\nversion = "1.17.0"\n'), ""),
        ],
    )

    with pytest.raises(ValueError, match="invalid reviewed cutoff"):
        export_lock(tmp_path)


def test_export_lock_check_detects_stale_selection(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n')
    output = tmp_path / "pylock.toml"
    export_lock(tmp_path)
    original = output.read_bytes()
    project.write_text(project.read_text() + "[dependency-groups]\nrelease = []\n")

    with pytest.raises(ValueError, match="project lock is stale"):
        export_lock(tmp_path, check=True)

    assert output.read_bytes() == original
    assert not (tmp_path / "uv.lock").exists()


def test_export_lock_check_accepts_current_selection(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n')
    output = tmp_path / "pylock.toml"
    export_lock(tmp_path)
    original = output.read_bytes()
    uv_lock = tmp_path / "uv.lock"
    uv_lock.write_text("existing native lock")
    uv_mtime = uv_lock.stat().st_mtime_ns
    output_mtime = output.stat().st_mtime_ns

    export_lock(tmp_path, check=True)

    assert output.read_bytes() == original
    assert output.stat().st_mtime_ns == output_mtime
    assert uv_lock.read_text() == "existing native lock"
    assert uv_lock.stat().st_mtime_ns == uv_mtime


def test_export_lock_check_rejects_stale_native_uv_lock(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n')
    output = tmp_path / "pylock.toml"
    export_lock(tmp_path)
    original = output.read_bytes()
    uv_lock = tmp_path / "uv.lock"
    uv_lock.write_bytes(b"stale native lock")
    mocker.patch("shutil.which", return_value="uv")

    def check_native(command: list[str], **_options: object) -> subprocess.CompletedProcess[str]:
        if command[1] == "--version":
            return _UV_VERSION
        assert command[1:] == ["lock", "--check", "--no-config"]
        return subprocess.CompletedProcess(command, 1, "", "native lock is stale")

    mocker.patch("subprocess.run", autospec=True, side_effect=check_native)

    with pytest.raises(ValueError, match="native lock is stale"):
        export_lock(tmp_path, check=True, keep_uv_lock=True)

    assert output.read_bytes() == original
    assert uv_lock.read_bytes() == b"stale native lock"


def test_export_lock_restores_output_after_partial_write(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n')
    output = tmp_path / "pylock.toml"
    output.write_bytes(b"previous lock")

    def partial_write(path: Path, _content: str, **_options: object) -> int:
        path.write_bytes(b"partial lock")
        msg = "disk write failed"
        raise OSError(msg)

    mocker.patch.object(Path, "write_text", autospec=True, side_effect=partial_write)

    with pytest.raises(OSError, match="disk write failed"):
        export_lock(tmp_path)

    assert output.read_bytes() == b"previous lock"


@pytest.mark.parametrize(
    "created_at",
    [
        pytest.param("absent", id="absent"),
        pytest.param("naive", id="naive"),
        pytest.param("future", id="future"),
    ],
)
def test_export_lock_check_rejects_invalid_creation_time(tmp_path: Path, created_at: str) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n')
    output = tmp_path / "pylock.toml"
    export_lock(tmp_path)
    data = tomllib.loads(output.read_text())
    if created_at == "absent":
        del data["tool"]["release-creator"]["created-at"]
    elif created_at == "naive":
        data["tool"]["release-creator"]["created-at"] = datetime.fromisoformat("2020-01-01")
    else:
        data["tool"]["release-creator"]["created-at"] = datetime.now(tz=UTC) + timedelta(days=1)
    output.write_text(tomli_w.dumps(data))

    with pytest.raises(ValueError, match="no valid creation time"):
        export_lock(tmp_path, check=True)


def test_export_lock_removes_generated_uv_lock(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text("[project]\nname = 'demo'\nversion = '1.0'\nrequires-python = '>=3.15'\n")

    export_lock(tmp_path)

    assert (tmp_path / "pylock.toml").exists()
    assert not (tmp_path / "uv.lock").exists()


def test_export_lock_preserves_group_includes(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(
        '[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n'
        '[dependency-groups]\ntest = []\ndev = [{ include-group = "test" }]\n'
    )

    export_lock(tmp_path)

    assert tomllib.loads((tmp_path / "pylock.toml").read_text())["dependency-groups"] == [
        "project-runtime",
        "test",
        "dev",
    ]


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

    export_lock(tmp_path)

    lock = tomllib.loads((tmp_path / "pylock.toml").read_text())
    assert (lock["requires-python"], lock["dependency-groups"]) == (">=3.11", ["project-runtime", "test", "release"])


def test_export_lock_expands_workspace_globs_and_excludes(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[tool.uv.workspace]\nmembers = ["packages/*"]\nexclude = ["packages/seeds"]\n')
    for name, configuration in (
        (
            "one",
            (
                '[project]\nname = "one"\nversion = "1"\nrequires-python = ">=3.15"\n'
                'dependencies = ["six"]\n[project.optional-dependencies]\ncli = ["click"]\n'
                '[dependency-groups]\ndocs = ["sphinx"]\n'
            ),
        ),
        (
            "two",
            (
                '[project]\nname = "two"\nversion = "1"\nrequires-python = ">=3.15"\n'
                '[dependency-groups]\ntest = ["pytest"]\n'
            ),
        ),
        ("seeds", '[project]\nname = "seeds"\nversion = "1"\nrequires-python = ">=3.15"\n'),
    ):
        member = tmp_path / "packages" / name
        member.mkdir(parents=True)
        (member / "pyproject.toml").write_text(configuration)
    mocker.patch("shutil.which", return_value="/usr/bin/uv")
    run = mocker.patch(
        "subprocess.run",
        autospec=True,
        side_effect=[
            _UV_VERSION,
            subprocess.CompletedProcess([], 0, _dated('[[packages]]\nname = "six"\nversion = "1.17.0"\n'), ""),
            subprocess.CompletedProcess([], 0, _dated('[[packages]]\nname = "sphinx"\nversion = "9.1.0"\n'), ""),
            subprocess.CompletedProcess([], 0, _dated('[[packages]]\nname = "pytest"\nversion = "9.1.1"\n'), ""),
            subprocess.CompletedProcess(
                [],
                0,
                _dated(
                    '[[packages]]\nname = "six"\nversion = "1.17.0"\n[[packages]]\nname = "click"\nversion = "8.3.1"\n'
                ),
                "",
            ),
        ],
    )

    export_lock(tmp_path)

    lock = tomllib.loads((tmp_path / "pylock.toml").read_text())
    assert (lock["dependency-groups"], lock["extras"]) == (["project-runtime", "docs", "test"], ["cli"])
    assert {package["name"] for package in lock["packages"]} == {"six", "sphinx", "pytest", "click"}
    assert [call.kwargs["input"] for call in run.call_args_list if call.kwargs["input"] is not None] == ["six\n"]
    assert any("--extra" in call.args[0] and "cli" in call.args[0] for call in run.call_args_list)
    assert [call.args[0][4] for call in run.call_args_list[2:4]] == [
        f"{tmp_path / 'packages/one/pyproject.toml'}:docs",
        f"{tmp_path / 'packages/two/pyproject.toml'}:test",
    ]


def test_export_lock_combines_workspace_build_requirements(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[tool.uv.workspace]\nmembers = ["packages/*"]\n')
    for name, backend in (("one", "hatchling"), ("two", "uv-build")):
        member = tmp_path / "packages" / name
        member.mkdir(parents=True)
        (member / "pyproject.toml").write_text(
            f'[build-system]\nrequires = ["{backend}"]\nbuild-backend = "build"\n'
            f'[project]\nname = "{name}"\nversion = "1"\nrequires-python = ">=3.15"\n'
            + ('[dependency-groups]\nbuild = ["maturin"]\n' if name == "one" else "")
        )
    mocker.patch("shutil.which", return_value="/usr/bin/uv")
    run = mocker.patch(
        "subprocess.run",
        autospec=True,
        side_effect=[
            _UV_VERSION,
            subprocess.CompletedProcess([], 0, "packages = []\n", ""),
            subprocess.CompletedProcess(
                [],
                0,
                _dated(
                    '[[packages]]\nname = "hatchling"\nversion = "1.32.4"\n'
                    '[[packages]]\nname = "uv-build"\nversion = "0.13.5"\n'
                    '[[packages]]\nname = "maturin"\nversion = "1.15.0"\n'
                ),
                "",
            ),
        ],
    )

    export_lock(tmp_path)

    lock = tomllib.loads((tmp_path / "pylock.toml").read_text())
    assert lock["dependency-groups"] == ["project-runtime", "build"]
    assert {package["name"] for package in lock["packages"]} == {"hatchling", "uv-build", "maturin"}
    assert run.call_args_list[2].kwargs["input"] == "hatchling\nuv-build\n"
    assert run.call_args_list[2].args[0][4:6] == ["--group", f"{tmp_path / 'packages/one/pyproject.toml'}:build"]


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
        export_lock(tmp_path)


def test_export_lock_rejects_workspace_member_url_before_uv(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[tool.uv.workspace]\nmembers = ["meta"]\n')
    member = tmp_path / "meta"
    member.mkdir()
    (member / "pyproject.toml").write_text(
        '[project]\nname = "meta"\nversion = "1"\nrequires-python = ">=3.11"\n'
        '[project.optional-dependencies]\ncli = ["six @ https://example.invalid/six.whl"]\n'
    )
    run = mocker.patch("subprocess.run", autospec=True)

    with pytest.raises(ValueError, match="direct dependency source"):
        export_lock(tmp_path)

    run.assert_not_called()


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
            "[build-system]\nrequires = ['invalid requirement!']\n"
            "[project]\nname = 'demo'\nrequires-python = '>=3.11'\n",
            "invalid requirement",
            id="invalid-build-requirement",
        ),
        pytest.param(
            "[project]\nname = 'demo'\nrequires-python = '>=3.11'\n"
            "dependencies = ['six @ https://example.invalid/six.whl']\n",
            "direct dependency source",
            id="runtime-url",
        ),
        pytest.param(
            "[project]\nname = 'demo'\nrequires-python = '>=3.11'\n"
            "[project.optional-dependencies]\ncli = ['six @ https://example.invalid/six.whl']\n",
            "direct dependency source",
            id="extra-url",
        ),
        pytest.param(
            "[project]\nname = 'demo'\nrequires-python = '>=3.11'\n"
            "[dependency-groups]\ntest = ['six @ https://example.invalid/six.whl']\n",
            "direct dependency source",
            id="group-url",
        ),
        pytest.param(
            "[build-system]\nrequires = ['six @ https://example.invalid/six.whl']\n"
            "[project]\nname = 'demo'\nrequires-python = '>=3.11'\n",
            "direct dependency source",
            id="build-url",
        ),
        pytest.param(
            "[project]\nname = 'demo'\nrequires-python = '>=3.11'\n"
            "[tool.uv.sources]\nsix = { git = 'https://example.invalid/six.git' }\n",
            "sources must be PyPI",
            id="source-override",
        ),
        pytest.param(
            "[project]\nname = 'demo'\nrequires-python = '>=3.11'\n"
            "[[tool.uv.index]]\nurl = 'https://example.invalid/simple/'\n",
            "sources must be PyPI",
            id="custom-index",
        ),
    ],
)
def test_export_lock_rejects_invalid_project(
    project_text: str, message: str, tmp_path: Path, mocker: MockerFixture
) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(project_text)
    process = mocker.patch("subprocess.run", autospec=True)

    with pytest.raises(ValueError, match=message):
        export_lock(tmp_path)

    process.assert_not_called()


def test_export_lock_requires_uv(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text("[project]\nname = 'demo'\nrequires-python = '>=3.11'\n")
    mocker.patch("shutil.which", return_value=None)

    with pytest.raises(FileNotFoundError, match="uv is required"):
        export_lock(tmp_path)


def test_export_lock_keeps_existing_uv_lock(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text("[project]\nname = 'demo'\nrequires-python = '>=3.11'\n")
    (tmp_path / "uv.lock").write_text("existing")
    mocker.patch("shutil.which", return_value="/usr/bin/uv")

    mocker.patch(
        "subprocess.run", autospec=True, return_value=subprocess.CompletedProcess([], 0, "packages = []\n", "")
    )

    export_lock(tmp_path)

    assert (tmp_path / "uv.lock").read_text() == "existing"


def test_export_lock_can_keep_updated_uv_lock(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text("[project]\nname = 'demo'\nrequires-python = '>=3.11'\n")
    (tmp_path / "uv.lock").write_text("existing")
    mocker.patch("shutil.which", return_value="/usr/bin/uv")
    native = (
        '[[package]]\nname = "demo"\nsource = { editable = "." }\n'
        '[[package]]\nname = "prek"\nversion = "0.5.5"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'wheels = [{ url = "https://files.pythonhosted.org/prek.whl", '
        f'hash = "sha256:{"0" * 64}", upload-time = "2020-01-01T00:00:00Z" }}]\n'
        'sdist = { url = "https://files.pythonhosted.org/prek.tar.gz", '
        f'hash = "sha256:{"0" * 64}", upload-time = "2020-01-01T00:00:00Z" }}\n'
    )
    resolved = tomli_w.dumps({
        "packages": [
            {
                "name": "prek",
                "version": "0.5.5",
                "index": "https://pypi.org/simple/",
                "wheels": [
                    {
                        "url": "https://files.pythonhosted.org/prek.whl",
                        "hashes": {"sha256": "0" * 64},
                        "upload-time": datetime(2020, 1, 1, tzinfo=UTC),
                    }
                ],
                "sdist": {
                    "url": "https://files.pythonhosted.org/prek.tar.gz",
                    "hashes": {"sha256": "0" * 64},
                    "upload-time": datetime(2020, 1, 1, tzinfo=UTC),
                },
            }
        ]
    })

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if command[1] == "--version":
            return _UV_VERSION
        if command[1] == "lock":
            (tmp_path / "uv.lock").write_text(native)
        return subprocess.CompletedProcess(command, 0, resolved, "")

    process = mocker.patch("subprocess.run", autospec=True, side_effect=run)

    export_lock(tmp_path, keep_uv_lock=True)

    assert (tmp_path / "uv.lock").read_text() == native
    native_commands = [call.args[0] for call in process.call_args_list if call.args[0][1] == "lock"]
    upgrade, normalize = native_commands
    assert upgrade[2] == "--upgrade"
    assert "--exclude-newer" in upgrade
    assert normalize == ["/usr/bin/uv", "lock", "--no-config"]


def test_export_lock_rejects_recent_native_artifact(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n')
    lock_path = tmp_path / "uv.lock"
    lock_path.write_text("existing")
    recent = datetime.now(tz=UTC) - timedelta(days=1)
    mocker.patch("shutil.which", return_value="uv")

    def run(command: list[str], **_options: object) -> subprocess.CompletedProcess[str]:
        if command[1] == "--version":
            return _UV_VERSION
        if command[1] == "lock":
            lock_path.write_text(
                '[[package]]\nname = "demo"\nsource = { editable = "." }\n'
                '[[package]]\nname = "prek"\nversion = "0.5.7"\n'
                'source = { registry = "https://pypi.org/simple" }\n'
                'wheels = [{ url = "https://files.pythonhosted.org/prek.whl", '
                f'hash = "sha256:abc", upload-time = "{recent.isoformat()}" }}]\n'
            )
        return subprocess.CompletedProcess(command, 0, "packages = []\n", "")

    mocker.patch("subprocess.run", autospec=True, side_effect=run)

    with pytest.raises(ValueError, match=r"uncooled artifact: prek\.whl"):
        export_lock(tmp_path, keep_uv_lock=True)

    assert lock_path.read_text() == "existing"
    assert not (tmp_path / "pylock.toml").exists()


def test_export_lock_rejects_forged_native_upload_time(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(
        '[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\ndependencies = ["prek>=0.4"]\n'
    )
    native = (
        '[[package]]\nname = "demo"\nsource = { editable = "." }\n'
        '[[package]]\nname = "prek"\nversion = "0.5.7"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'wheels = [{ url = "https://files.pythonhosted.org/prek-0.5.7.whl", '
        f'hash = "sha256:{"0" * 64}", upload-time = "2020-01-01T00:00:00Z" }}]\n'
    )
    (tmp_path / "uv.lock").write_text("reviewed native lock")
    resolved = tomli_w.dumps({
        "packages": [
            {
                "name": "prek",
                "version": "0.5.5",
                "index": "https://pypi.org/simple/",
                "wheels": [
                    {
                        "url": "https://files.pythonhosted.org/prek-0.5.5.whl",
                        "hashes": {"sha256": "1" * 64},
                        "upload-time": datetime(2020, 1, 1, tzinfo=UTC),
                    }
                ],
            }
        ]
    })

    def run(command: list[str], **_options: object) -> subprocess.CompletedProcess[str]:
        if command[1] == "--version":
            return _UV_VERSION
        if command[1] == "lock":
            (tmp_path / "uv.lock").write_text(native)
        return subprocess.CompletedProcess(command, 0, resolved, "")

    mocker.patch("shutil.which", return_value="uv")
    mocker.patch("subprocess.run", autospec=True, side_effect=run)

    with pytest.raises(ValueError, match="differs from cooled project lock"):
        export_lock(tmp_path, keep_uv_lock=True)

    assert (tmp_path / "uv.lock").read_text() == "reviewed native lock"
    assert not (tmp_path / "pylock.toml").exists()


@pytest.mark.parametrize(
    ("case", "error", "message"),
    [
        pytest.param("no-artifacts", ValueError, "no dated artifacts", id="no-artifacts"),
        pytest.param("source", ValueError, "non-PyPI package source", id="non-pypi-source"),
        pytest.param("url", ValueError, "non-PyPI artifact", id="non-pypi-url"),
        pytest.param("upload-time", TypeError, "no upload time", id="no-upload-time"),
        pytest.param("invalid-time", ValueError, "invalid upload time", id="invalid-upload-time"),
        pytest.param("hash", ValueError, "no SHA-256", id="no-hash"),
        pytest.param("short-hash", ValueError, "no SHA-256", id="short-hash"),
        pytest.param("wrong-hash", ValueError, "no SHA-256", id="wrong-hash-kind"),
        pytest.param("nonhex-hash", ValueError, "no SHA-256", id="nonhex-hash"),
    ],
)
def test_export_lock_rejects_invalid_native_artifact(
    tmp_path: Path, mocker: MockerFixture, case: str, error: type[Exception], message: str
) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname = "demo"\nversion = "1"\nrequires-python = ">=3.15"\n')
    artifact = {
        "url": "https://files.pythonhosted.org/prek.whl",
        "hash": f"sha256:{'0' * 64}",
        "upload-time": "2020-01-01T00:00:00Z",
    }
    if case in {"url", "invalid-time", "short-hash", "wrong-hash", "nonhex-hash"}:
        field, value = {
            "url": ("url", "https://example.invalid/prek.whl"),
            "invalid-time": ("upload-time", "not-a-date"),
            "short-hash": ("hash", "sha256:abc"),
            "wrong-hash": ("hash", f"sha512:{'0' * 64}"),
            "nonhex-hash": ("hash", f"sha256:{'z' * 64}"),
        }[case]
        artifact[field] = value
    elif case in {"upload-time", "hash"}:
        artifact.pop(case)
    package: dict[str, object] = {
        "name": "prek",
        "version": "0.5.5",
        "source": {"registry": "https://pypi.org/simple"},
        "wheels": [artifact],
    }
    if case == "no-artifacts":
        package.pop("wheels")
    elif case == "source":
        package["source"] = {"git": "https://example.invalid/prek"}
    native = tomli_w.dumps({"package": [{"name": "demo", "source": {"editable": "."}}, package]})

    def run(command: list[str], **_options: object) -> subprocess.CompletedProcess[str]:
        if command[1] == "--version":
            return _UV_VERSION
        if command[1] == "lock":
            (tmp_path / "uv.lock").write_text(native)
        return subprocess.CompletedProcess(command, 0, "packages = []\n", "")

    mocker.patch("shutil.which", return_value="uv")
    mocker.patch("subprocess.run", autospec=True, side_effect=run)

    with pytest.raises(error, match=message):
        export_lock(tmp_path, keep_uv_lock=True)

    assert not (tmp_path / "pylock.toml").exists()


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
        if command[1] == "--version":
            return _UV_VERSION
        if command[1] == "lock":
            lock_path.write_text('[[package]]\nname = "demo"\nsource = { editable = "." }\n')
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 1, "", "build resolver failed")

    mocker.patch("subprocess.run", autospec=True, side_effect=run)

    with pytest.raises(ValueError, match="build resolver failed"):
        export_lock(tmp_path, keep_uv_lock=True)

    assert (lock_path.read_text(), output.read_text()) == ("reviewed lock", "reviewed export")


def test_export_lock_reports_uv_failure(tmp_path: Path, mocker: MockerFixture) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text("[project]\nname = 'demo'\nrequires-python = '>=3.11'\n")
    mocker.patch("shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "subprocess.run", autospec=True, return_value=subprocess.CompletedProcess([], 1, "", "invalid project")
    )

    with pytest.raises(ValueError, match="invalid project"):
        export_lock(tmp_path)

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
            _UV_VERSION,
            subprocess.CompletedProcess([], 0, "packages = []\n", ""),
        ],
    )

    with pytest.raises(ValueError, match="cannot infer the minimum Python version"):
        export_lock(tmp_path)

    assert not (tmp_path / "pylock.toml").exists()


def test_ci_resolves_test_type_and_docs_groups_without_the_lock() -> None:
    root = Path(__file__).resolve().parents[3]
    workflow = safe_load((root / ".github/workflows/check.yaml").read_text(encoding="utf-8"))
    tox = tomllib.loads((root / "tox.toml").read_text(encoding="utf-8"))

    assert {
        "test": tox["env_run_base"]["dependency_groups"],
        "type": tox["env"]["type"]["dependency_groups"],
        "docs": tox["env"]["docs"]["dependency_groups"],
    } == {"test": ["test"], "type": ["type"], "docs": ["docs"]}
    commands = "\n".join(
        str(step.get("run", "")) for job in ("test", "check") for step in workflow["jobs"][job]["steps"]
    )
    assert "tox run -vv --notest" in commands
    assert "pylock.toml" not in commands


_UV_VERSION: Final = subprocess.CompletedProcess(["uv", "--version"], 0, "uv 0.13.5 (abc123 2026-10-21)\n", "")


def _dated(text: str) -> str:
    data = tomllib.loads(text)
    for package in data["packages"]:
        package["sdist"] = {
            "url": f"https://files.pythonhosted.org/{package['name']}-{package['version']}.tar.gz",
            "upload-time": datetime(2020, 1, 1, tzinfo=UTC),
            "hashes": {"sha256": "a" * 64},
        }
    return tomli_w.dumps(data)

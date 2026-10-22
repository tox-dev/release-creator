"""Behavioral tests for pre-commit dependency updates."""

import subprocess  # ruff: ignore[suspicious-subprocess-import]  # CompletedProcess models the uv boundary.
from typing import TYPE_CHECKING
from zipfile import ZipFile

import pytest
from yaml import safe_load

lazy from release_creator.hooks.update import update_pins

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def test_updates_each_hook_with_its_universal_closure(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: format\n"
        "        additional_dependencies: ['MDFormat_GFM==1.0.0', sphinx>=9] # keep\n"
        "      - id: docs\n"
        "        additional_dependencies:\n"
        "          - sphinx==9.0.0 # chosen\n",
        encoding="utf-8",
    )
    mocker.patch("release_creator.hooks.update.shutil.which", return_value="/usr/bin/uv")
    responses = {
        "sphinx\n": "sphinx==9.1.1\ncolorama==0.4.6 ; sys_platform == 'win32'\n",
        "MDFormat_GFM\n": "mdformat-gfm==1.1.0\nmdformat==1.0.0\n",
    }

    def resolve(command: list[str], *, stdin: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        assert cwd == tmp_path
        return subprocess.CompletedProcess(command, 0, responses[stdin], "")

    run = mocker.patch("release_creator.hooks.update.run_text", side_effect=resolve)

    update_pins(config, "2026-10-14T00:00:00Z", "3.15")

    assert config.read_text(encoding="utf-8") == (
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: format\n"
        "        additional_dependencies: # keep\n"
        "          - 'MDFormat_GFM==1.1.0'\n"
        "          - sphinx>=9\n"
        '          - "mdformat==1.0.0" # release-creator managed\n'
        "      - id: docs\n"
        "        additional_dependencies:\n"
        "          - sphinx==9.1.1 # chosen\n"
        '          - "colorama==0.4.6; sys_platform == \\"win32\\"" # release-creator managed\n'
    )
    assert len(run.call_args_list) == len({"format", "docs"})
    assert {call.kwargs["stdin"] for call in run.call_args_list} == set(responses)
    assert all("--universal" in call.args[0] for call in run.call_args_list)
    assert all("--no-deps" not in call.args[0] for call in run.call_args_list)


def test_resolves_real_universal_closure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    for name, version, requirements in (
        ("closure_root", "1.0.0", ("closure-child>=1",)),
        ("closure_child", "2.0.0", ("closure-color==0.4.6; sys_platform == 'win32'",)),
        ("closure_color", "0.4.6", ()),
    ):
        _write_wheel(wheels, name, version, requirements)
    monkeypatch.setenv("UV_NO_INDEX", "1")
    monkeypatch.setenv("UV_FIND_LINKS", str(wheels))
    monkeypatch.setenv("UV_OFFLINE", "1")
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text("additional_dependencies: [closure-root==0.1.0]\n", encoding="utf-8")

    update_pins(config, "2099-01-01T00:00:00Z", "3.15")

    assert safe_load(config.read_text(encoding="utf-8"))["additional_dependencies"] == [
        "closure-root==1.0.0",
        "closure-child==2.0.0",
        'closure-color==0.4.6; sys_platform == "win32"',
    ]


def _write_wheel(directory: Path, name: str, version: str, requirements: tuple[str, ...]) -> None:
    metadata = f"{name}-{version}.dist-info"
    with ZipFile(directory / f"{name}-{version}-py3-none-any.whl", "w") as wheel:
        wheel.writestr(
            f"{metadata}/METADATA",
            f"Metadata-Version: 2.4\nName: {name.replace('_', '-')}\nVersion: {version}\n"
            + "".join(f"Requires-Dist: {requirement}\n" for requirement in requirements),
        )
        wheel.writestr(
            f"{metadata}/WHEEL", "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
        )
        wheel.writestr(f"{metadata}/RECORD", "")


def test_replaces_managed_closure_on_rerun(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text("additional_dependencies: [black==1]\n", encoding="utf-8")
    mocker.patch("release_creator.hooks.update.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        side_effect=[
            subprocess.CompletedProcess([], 0, "black==2\nclick==8\npathspec==1\n", ""),
            subprocess.CompletedProcess([], 0, "black==3\nclick==9\n", ""),
        ],
    )

    update_pins(config, "2026-10-14T00:00:00Z", "3.15")
    update_pins(config, "2026-10-14T00:00:00Z", "3.15")

    assert config.read_text(encoding="utf-8") == (
        'additional_dependencies:\n  - black==3\n  - "click==9" # release-creator managed\n'
    )


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("additional_dependencies: [black==1]", id="flow"),
        pytest.param("additional_dependencies:\n  - black==1", id="block"),
    ],
)
def test_extends_list_without_final_newline(source: str, tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(source, encoding="utf-8")
    mocker.patch("release_creator.hooks.update.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, "black==2\nclick==8\n", ""),
    )

    update_pins(config, "2026-10-14T00:00:00Z", "3.15")

    assert config.read_text(encoding="utf-8") == (
        'additional_dependencies:\n  - black==2\n  - "click==8" # release-creator managed\n'
    )


def test_removes_managed_closure_after_root_is_removed(tmp_path: Path) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        'additional_dependencies:\n  - "click==9" # release-creator managed\n',
        encoding="utf-8",
    )

    update_pins(config, "2026-10-14T00:00:00Z", "3.15")

    assert config.read_text(encoding="utf-8") == "additional_dependencies: []\n"


def test_keeps_comment_on_empty_dependency_list(tmp_path: Path) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    source = "additional_dependencies: [] # keep\n"
    config.write_text(source, encoding="utf-8")

    update_pins(config, "2026-10-14T00:00:00Z", "3.15")

    assert config.read_text(encoding="utf-8") == source


def test_keeps_nonexact_dependency_when_root_is_removed(tmp_path: Path) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        'additional_dependencies:\n  - sphinx>=9\n  - "click==9" # release-creator managed\n',
        encoding="utf-8",
    )

    update_pins(config, "2026-10-14T00:00:00Z", "3.15")

    assert config.read_text(encoding="utf-8") == "additional_dependencies:\n  - sphinx>=9\n"


def test_skips_ranges_and_unpinned(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    source = "repos: [{hooks: [{additional_dependencies: [sphinx>=9, mdformat-gfm]}]}]\n"
    config.write_text(source, encoding="utf-8")
    run = mocker.patch("release_creator.process.subprocess.run")

    update_pins(config, "2026-10-14T00:00:00Z", "3.15")

    assert config.read_text(encoding="utf-8") == source
    run.assert_not_called()


@pytest.mark.parametrize(
    ("output", "message"),
    [
        pytest.param("", "different hook dependencies", id="missing"),
        pytest.param("other==1.0\n", "different hook dependencies", id="unexpected"),
        pytest.param("mdformat-gfm>=1\n", "expected an exact pin", id="range"),
        pytest.param("mdformat-gfm==1\nmdformat-gfm==2\n", "different hook dependencies", id="forked-root"),
        pytest.param("garbage!\n", "invalid package from uv", id="malformed"),
        pytest.param("mdformat-gfm==1\nclick==1\nclick==2\n", "duplicate hook dependencies", id="duplicate"),
    ],
)
def test_rejects_bad_resolver_output(output: str, message: str, tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    source = "repos: [{hooks: [{additional_dependencies: [mdformat-gfm==1.0.0]}]}]\n"
    config.write_text(source, encoding="utf-8")
    mocker.patch("release_creator.hooks.update.shutil.which", return_value="/usr/bin/uv")
    mocker.patch("release_creator.process.subprocess.run", return_value=subprocess.CompletedProcess([], 0, output, ""))

    with pytest.raises(ValueError, match=message):
        update_pins(config, "2026-10-14T00:00:00Z", "3.15")

    assert config.read_text(encoding="utf-8") == source


def test_rejects_resolver_failure(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text("additional_dependencies: [mdformat-gfm==1.0.0]\n", encoding="utf-8")
    mocker.patch("release_creator.hooks.update.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        return_value=subprocess.CompletedProcess([], 1, "", "index unavailable"),
    )

    with pytest.raises(ValueError, match="index unavailable"):
        update_pins(config, "2026-10-14T00:00:00Z", "3.15")


def test_reports_missing_uv(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text("additional_dependencies: [mdformat-gfm==1.0.0]\n", encoding="utf-8")
    mocker.patch("release_creator.hooks.update.shutil.which", return_value=None)

    with pytest.raises(FileNotFoundError, match="uv is required"):
        update_pins(config, "2026-10-14T00:00:00Z", "3.15")


@pytest.mark.parametrize(
    ("source", "error"),
    [
        pytest.param("repos: [\n", ValueError, id="invalid-yaml"),
        pytest.param("[]\n", TypeError, id="not-mapping"),
        pytest.param("additional_dependencies: invalid\n", TypeError, id="not-list"),
        pytest.param("additional_dependencies: [not a requirement!]\n", ValueError, id="invalid-package"),
    ],
)
def test_rejects_bad_config(source: str, error: type[Exception], tmp_path: Path) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(source, encoding="utf-8")

    with pytest.raises(error):
        update_pins(config, "2026-10-14T00:00:00Z", "3.15")


def test_leaves_current_pin_untouched(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    source = "additional_dependencies: [mdformat-gfm==1.0.0]\n"
    config.write_text(source, encoding="utf-8")
    mocker.patch("release_creator.hooks.update.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, "mdformat-gfm==1.0.0\n", ""),
    )

    update_pins(config, "2026-10-14T00:00:00Z", "3.15")

    assert config.read_text(encoding="utf-8") == source

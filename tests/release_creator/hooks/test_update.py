"""Behavioral tests for pre-commit dependency updates."""

import subprocess  # ruff: ignore[suspicious-subprocess-import]  # CompletedProcess models the uv boundary.
from textwrap import dedent
from typing import TYPE_CHECKING
from zipfile import ZipFile
lazy from unittest.mock import MagicMock

import pytest
from yaml import safe_load

lazy from release_creator.hooks.update import update_pins
lazy from release_creator.process import run_text

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
        "        language: python\n"
        "        additional_dependencies: ['MDFormat_GFM==1.0.0', sphinx>=9] # keep\n"
        "      - id: docs\n"
        "        language: python\n"
        "        additional_dependencies:\n"
        "          - sphinx==9.0.0 # chosen\n",
        encoding="utf-8",
    )
    mocker.patch("release_creator.hooks.update.shutil.which", return_value="/usr/bin/uv")
    responses = {
        "sphinx\n": "sphinx==9.1.1\ncolorama==0.4.6 ; sys_platform == 'win32'\n",
        "MDFormat_GFM\nsphinx>=9\n": "mdformat-gfm==1.1.0\nsphinx==9.1.1\nmdformat==1.0.0\n",
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
        "        language: python\n"
        "        additional_dependencies: # keep\n"
        "          - 'MDFormat_GFM==1.1.0'\n"
        "          - sphinx>=9\n"
        '          - "mdformat==1.0.0" # release-creator managed\n'
        "      - id: docs\n"
        "        language: python\n"
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
    config.write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: closure\n"
        "        language: python\n        additional_dependencies: [closure-root==0.1.0]\n",
        encoding="utf-8",
    )

    update_pins(config, "2099-01-01T00:00:00Z", "3.15")

    assert safe_load(config.read_text(encoding="utf-8"))["repos"][0]["hooks"][0]["additional_dependencies"] == [
        "closure-root==1.0.0",
        "closure-child==2.0.0",
        'closure-color==0.4.6; sys_platform == "win32"',
    ]


def test_block_closure_stays_with_its_hook(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        dedent("""\
        repos:
          - repo: local
            hooks:
              - id: first
                language: python
                additional_dependencies:
                  - black==1
              - id: second
                language: system
        """),
        encoding="utf-8",
    )
    mocker.patch("release_creator.hooks.update.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.hooks.update.run_text",
        return_value=subprocess.CompletedProcess([], 0, "black==2\nclick==8\n", ""),
    )

    update_pins(config, "2026-10-14T00:00:00Z", "3.15")
    updated = config.read_text(encoding="utf-8")
    update_pins(config, "2026-10-14T00:00:00Z", "3.15")

    assert config.read_text(encoding="utf-8") == updated
    assert safe_load(updated)["repos"][0]["hooks"] == [
        {"id": "first", "language": "python", "additional_dependencies": ["black==2", "click==8"]},
        {"id": "second", "language": "system"},
    ]


def test_flow_hook_keeps_its_mapping(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        "repos:\n  - repo: local\n    hooks:\n"
        "      - {id: first, language: python, additional_dependencies: [black==1]}\n"
        "      - {id: second, language: system}\n",
        encoding="utf-8",
    )
    mocker.patch("release_creator.hooks.update.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.hooks.update.run_text",
        return_value=subprocess.CompletedProcess([], 0, "black==2\nclick==8\n", ""),
    )

    update_pins(config, "2026-10-14T00:00:00Z", "3.15")

    assert safe_load(config.read_text(encoding="utf-8"))["repos"][0]["hooks"] == [
        {"id": "first", "language": "python", "additional_dependencies": ["black==2", "click==8"]},
        {"id": "second", "language": "system"},
    ]


@pytest.mark.parametrize(
    ("last_field", "last_value"),
    [
        pytest.param("", None, id="scalar"),
        pytest.param("        args:\n          - check\n", ["check"], id="sequence"),
        pytest.param("        types:\n          primary: python\n", {"primary": "python"}, id="mapping"),
    ],
)
def test_new_group_stays_with_its_hook(
    tmp_path: Path,
    mocker: MockerFixture,
    upstream_python_hook: tuple[Path, str],
    last_field: str,
    last_value: list[str] | dict[str, str] | None,
) -> None:
    upstream, revision = upstream_python_hook
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        f"repos:\n  - repo: {upstream.as_uri()}\n    rev: {revision}\n    hooks:\n"
        f"      - id: lint\n{last_field}"
        "      - id: other\n        language: system\n",
        encoding="utf-8",
    )
    mocker.patch("release_creator.hooks.update.shutil.which", side_effect=lambda name: name)
    _mock_hook_compiler(mocker, "-e file:///checkout\nclick==8.1\n")

    update_pins(config, "7 days", "3.15")

    expected = {"id": "lint", "additional_dependencies": ["click==8.1"]}
    if last_value is not None:
        expected["args" if isinstance(last_value, list) else "types"] = last_value
    assert safe_load(config.read_text(encoding="utf-8"))["repos"][0]["hooks"] == [
        expected,
        {"id": "other", "language": "system"},
    ]


def test_rejects_direct_url_root(tmp_path: Path) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text('additional_dependencies: ["example @ https://example.org/example.whl"]\n', encoding="utf-8")

    with pytest.raises(ValueError, match="bypasses the package cooldown"):
        update_pins(config, "2026-10-14T00:00:00Z", "3.15")

    assert (
        config.read_text(encoding="utf-8") == 'additional_dependencies: ["example @ https://example.org/example.whl"]\n'
    )


@pytest.fixture
def upstream_python_hook(tmp_path: Path) -> tuple[Path, str]:
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    (upstream / ".pre-commit-hooks.yaml").write_text(
        "- id: lint\n  name: lint\n  entry: lint\n  language: python\n", encoding="utf-8"
    )
    (upstream / "pyproject.toml").write_text(
        '[project]\nname = "fixture-lint"\nversion = "1.0"\ndependencies = ["click>=8"]\n', encoding="utf-8"
    )
    assert run_text(["git", "init", "-q", str(upstream)]).returncode == 0
    assert run_text(["git", "-C", str(upstream), "add", "."]).returncode == 0
    assert (
        run_text(
            [
                "git",
                "-C",
                str(upstream),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.org",
                "commit",
                "-qm",
                "Init",
            ],
        ).returncode
        == 0
    )
    return upstream, run_text(["git", "-C", str(upstream), "rev-parse", "HEAD"]).stdout.strip()


@pytest.mark.parametrize("existing", [pytest.param(False, id="new-list"), pytest.param(True, id="existing-list")])
@pytest.mark.parametrize(
    "trailing_newline", [pytest.param(False, id="no-final-newline"), pytest.param(True, id="final-newline")]
)
def test_pins_python_hook_package_dependencies(
    tmp_path: Path,
    mocker: MockerFixture,
    upstream_python_hook: tuple[Path, str],
    existing: bool,
    trailing_newline: bool,
) -> None:
    upstream, revision = upstream_python_hook
    config = tmp_path / ".pre-commit-config.yaml"
    dependencies = "        additional_dependencies: [colorama==0.4.6]\n" if existing else ""
    source = f"repos:\n  - repo: {upstream.as_uri()}\n    rev: {revision}\n    hooks:\n      - id: lint\n{dependencies}"
    config.write_text(
        source if trailing_newline else source.rstrip("\n"),
        encoding="utf-8",
    )
    mocker.patch("release_creator.hooks.update.shutil.which", side_effect=lambda name: name)
    colorama = "colorama==0.4.6\n" if existing else ""
    commands = _mock_hook_compiler(mocker, f"-e file:///checkout\nclick==8.1\n{colorama}")

    update_pins(config, "7 days", "3.15")

    parsed = safe_load(config.read_text(encoding="utf-8"))
    assert parsed["repos"][0]["hooks"][0]["additional_dependencies"] == (
        ["colorama==0.4.6", "click==8.1"] if existing else ["click==8.1"]
    )
    assert any(
        call.args[0][0] == "uv" and ("colorama\n" in call.kwargs["stdin"]) == existing
        for call in commands.call_args_list
    )
    assert any("--" in call.args[0] and call.args[0][0:2] == ["git", "clone"] for call in commands.call_args_list)
    assert "# release-creator managed" in config.read_text(encoding="utf-8")
    first = config.read_text(encoding="utf-8")

    update_pins(config, "7 days", "3.15")

    assert config.read_text(encoding="utf-8") == first


def test_preserves_system_hook_dependencies(
    tmp_path: Path, mocker: MockerFixture, upstream_python_hook: tuple[Path, str]
) -> None:
    upstream, _ = upstream_python_hook
    (upstream / ".pre-commit-hooks.yaml").write_text(
        "- id: lint\n  name: lint\n  entry: lint\n  language: system\n", encoding="utf-8"
    )
    assert run_text(["git", "-C", str(upstream), "add", "."]).returncode == 0
    assert (
        run_text([
            "git",
            "-C",
            str(upstream),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.org",
            "commit",
            "-qm",
            "System",
        ]).returncode
        == 0
    )
    revision = run_text(["git", "-C", str(upstream), "rev-parse", "HEAD"]).stdout.strip()
    config = tmp_path / ".pre-commit-config.yaml"
    source = (
        f"repos:\n  - repo: {upstream.as_uri()}\n    rev: {revision}\n    hooks:\n      - id: lint\n"
        '        additional_dependencies:\n          - "click==8" # release-creator managed\n'
    )
    config.write_text(source, encoding="utf-8")
    command = mocker.patch("release_creator.hooks.update.run_text", wraps=run_text)

    update_pins(config, "7 days", "3.15")

    assert config.read_text(encoding="utf-8") == source
    assert all(call.args[0][0] != "uv" for call in command.call_args_list)


def test_ignores_non_python_hook_dependencies(tmp_path: Path) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    source = (
        "repos:\n  - repo: local\n    hooks:\n      - id: xml\n"
        "        language: node\n        additional_dependencies: ['@prettier/plugin-xml@3.4.1']\n"
    )
    config.write_text(source, encoding="utf-8")

    update_pins(config, "7 days", "3.15")

    assert config.read_text(encoding="utf-8") == source


def test_updates_python_hook_without_adding_dependencies_to_other_local_hook(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: shell\n        language: system\n"
        "      - id: python-empty\n        language: python\n"
        "      - id: python\n        language: python\n        additional_dependencies: [black==1]\n",
        encoding="utf-8",
    )
    mocker.patch("release_creator.hooks.update.shutil.which", return_value="uv")
    mocker.patch(
        "release_creator.hooks.update.run_text",
        return_value=subprocess.CompletedProcess([], 0, "black==2\n", ""),
    )

    update_pins(config, "2026-10-14T00:00:00Z", "3.15")

    hooks = safe_load(config.read_text(encoding="utf-8"))["repos"][0]["hooks"]
    assert hooks == [
        {"id": "shell", "language": "system"},
        {"id": "python-empty", "language": "python"},
        {"id": "python", "language": "python", "additional_dependencies": ["black==2"]},
    ]


@pytest.mark.parametrize(
    ("revision", "error", "message"),
    [
        pytest.param(None, TypeError, "missing frozen revision", id="missing"),
        pytest.param("v1.0.0", ValueError, "must use a frozen commit", id="moving-tag"),
    ],
)
def test_rejects_unfrozen_hook_repository(
    tmp_path: Path, revision: str | None, error: type[Exception], message: str
) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    revision_line = f"    rev: {revision}\n" if revision is not None else ""
    source = f"repos:\n  - repo: https://example.org/hooks.git\n{revision_line}    hooks:\n      - id: lint\n"
    config.write_text(source, encoding="utf-8")

    with pytest.raises(error) as caught:
        update_pins(config, "7 days", "3.15")

    assert message in str(caught.value)
    assert config.read_text(encoding="utf-8") == source


def test_python_hook_without_dependencies_does_not_add_a_list(
    tmp_path: Path, mocker: MockerFixture, upstream_python_hook: tuple[Path, str]
) -> None:
    upstream, revision = upstream_python_hook
    config = tmp_path / ".pre-commit-config.yaml"
    source = f"repos:\n  - repo: {upstream.as_uri()}\n    rev: {revision}\n    hooks:\n      - id: lint\n"
    config.write_text(source, encoding="utf-8")
    commands = _mock_hook_compiler(mocker, "-e file:///checkout\n")

    update_pins(config, "7 days", "3.15")

    assert config.read_text(encoding="utf-8") == source
    assert any(call.args[0][0] == "uv" for call in commands.call_args_list)


@pytest.mark.parametrize(
    "hook", [pytest.param("invalid", id="not-mapping"), pytest.param("{name: lint}", id="missing-id")]
)
def test_rejects_invalid_hook_entry(tmp_path: Path, upstream_python_hook: tuple[Path, str], hook: str) -> None:
    upstream, revision = upstream_python_hook
    config = tmp_path / ".pre-commit-config.yaml"
    source = f"repos:\n  - repo: {upstream.as_uri()}\n    rev: {revision}\n    hooks:\n      - {hook}\n"
    config.write_text(source, encoding="utf-8")

    with pytest.raises(TypeError) as caught:
        update_pins(config, "7 days", "3.15")

    assert "selected hook must be a mapping with an id" in str(caught.value)
    assert config.read_text(encoding="utf-8") == source


@pytest.mark.parametrize(
    "failure", [pytest.param("git-missing", id="git-missing"), pytest.param("clone-failed", id="clone-failed")]
)
def test_rejects_unavailable_hook_repository(tmp_path: Path, mocker: MockerFixture, failure: str) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    source = f"repos:\n  - repo: file:///missing\n    rev: {'a' * 40}\n    hooks:\n      - id: lint\n"
    config.write_text(source, encoding="utf-8")
    if failure == "git-missing":
        mocker.patch(
            "release_creator.hooks.update.shutil.which", side_effect=lambda name: None if name == "git" else name
        )
        expected = "git is required"
    else:
        mocker.patch(
            "release_creator.hooks.update.run_text",
            return_value=subprocess.CompletedProcess([], 1, "", "repository not found"),
        )
        expected = "cannot read hook repository"

    with pytest.raises(FileNotFoundError if failure == "git-missing" else ValueError) as caught:
        update_pins(config, "7 days", "3.15")

    assert expected in str(caught.value)
    assert config.read_text(encoding="utf-8") == source


def test_rejects_flow_style_hook_when_package_dependencies_need_a_list(
    tmp_path: Path, mocker: MockerFixture, upstream_python_hook: tuple[Path, str]
) -> None:
    upstream, revision = upstream_python_hook
    config = tmp_path / ".pre-commit-config.yaml"
    source = f"repos:\n  - repo: {upstream.as_uri()}\n    rev: {revision}\n    hooks: [{{id: lint}}]\n"
    config.write_text(source, encoding="utf-8")
    _mock_hook_compiler(mocker, "-e file:///checkout\nclick==8.1\n")

    with pytest.raises(ValueError, match="flow-style hook"):
        update_pins(config, "7 days", "3.15")

    assert config.read_text(encoding="utf-8") == source


def _mock_hook_compiler(mocker: MockerFixture, output: str) -> MagicMock:
    original = run_text

    def resolve(
        command: list[str], *, stdin: str | None = None, cwd: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        if command[0] == "uv":
            assert stdin is not None
            assert stdin.startswith("-e file://")
            return subprocess.CompletedProcess(command, 0, output, "")
        return original(command, cwd=cwd, stdin=stdin)

    mocker.patch("release_creator.hooks.update.shutil.which", side_effect=lambda name: name)
    patched = mocker.patch("release_creator.hooks.update.run_text", side_effect=resolve)
    assert isinstance(patched, MagicMock)
    return patched


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


def test_keeps_nonexact_dependency_when_root_is_removed(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        'additional_dependencies:\n  - sphinx>=9\n  - "click==9" # release-creator managed\n',
        encoding="utf-8",
    )
    mocker.patch("release_creator.hooks.update.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.hooks.update.run_text",
        return_value=subprocess.CompletedProcess([], 0, "sphinx==9.1\n", ""),
    )

    update_pins(config, "2026-10-14T00:00:00Z", "3.15")

    assert config.read_text(encoding="utf-8") == "additional_dependencies:\n  - sphinx>=9\n"


def test_resolves_ranges_and_unpinned_roots(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    source = "additional_dependencies: [sphinx>=9, mdformat-gfm]\n"
    config.write_text(source, encoding="utf-8")
    mocker.patch("release_creator.hooks.update.shutil.which", return_value="/usr/bin/uv")
    run = mocker.patch(
        "release_creator.hooks.update.run_text",
        return_value=subprocess.CompletedProcess([], 0, "sphinx==9.1\nmdformat-gfm==1.2\ncolorama==0.4.6\n", ""),
    )

    update_pins(config, "2026-10-14T00:00:00Z", "3.15")

    assert safe_load(config.read_text(encoding="utf-8"))["additional_dependencies"] == [
        "sphinx>=9",
        "mdformat-gfm",
        "colorama==0.4.6",
    ]
    assert run.call_args.kwargs["stdin"] == "sphinx>=9\nmdformat-gfm\n"


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
        pytest.param("repos: [invalid]\n", TypeError, id="invalid-repository"),
        pytest.param("repos: [{repo: local}]\n", TypeError, id="missing-hooks"),
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

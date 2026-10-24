"""Behavioral tests for pre-commit dependency updates."""

import json
import os
import subprocess  # ruff: ignore[suspicious-subprocess-import]  # CompletedProcess models the uv boundary.
import sys
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, cast
from zipfile import ZipFile
lazy from unittest.mock import MagicMock

import pytest
from yaml import safe_load

lazy from release_creator import process
lazy from release_creator.cli import main
lazy from release_creator.hooks.update import check_pins, update_pins
lazy from release_creator.process import run_text

if TYPE_CHECKING:
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
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    responses = {
        "sphinx\n": "sphinx==9.1.1\ncolorama==0.4.6 ; sys_platform == 'win32'\n",
        "MDFormat_GFM\nsphinx>=9\n": "mdformat-gfm==1.1.0\nsphinx==9.1.1\nmdformat==1.0.0\n",
    }

    def resolve(
        command: list[str], *, cwd: Path, env: dict[str, str], **options: object
    ) -> subprocess.CompletedProcess[str]:
        assert cwd == tmp_path
        assert "UV_INDEX_URL" not in env
        return subprocess.CompletedProcess(command, 0, responses[cast("str", options["input"])], "")

    run = mocker.patch("release_creator.process.subprocess.run", autospec=True, side_effect=resolve)

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
        '          - "sphinx==9.1.1" # release-creator managed\n'
        '          - "mdformat==1.0.0" # release-creator managed\n'
        "      - id: docs\n"
        "        language: python\n"
        "        additional_dependencies:\n"
        "          - sphinx==9.1.1 # chosen\n"
        '          - "colorama==0.4.6; sys_platform == \\"win32\\"" # release-creator managed\n'
    )
    assert len(run.call_args_list) == len({"format", "docs"})
    assert {call.kwargs["input"] for call in run.call_args_list} == set(responses)
    assert all("--universal" in call.args[0] for call in run.call_args_list)
    assert all("--no-config" in call.args[0] for call in run.call_args_list)
    assert all("--no-sources" in call.args[0] for call in run.call_args_list)
    assert all(
        call.args[0][call.args[0].index("--exclude-newer") + 1] == "2026-10-14T00:00:00Z" for call in run.call_args_list
    )
    assert all("--no-deps" not in call.args[0] for call in run.call_args_list)


def test_updates_platform_disjoint_direct_pins(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: format\n"
        "        language: python\n        additional_dependencies:\n"
        "          - \"packaging==24.1; sys_platform == 'win32'\"\n"
        "          - \"packaging==24.2; sys_platform != 'win32'\"\n",
        encoding="utf-8",
    )
    mocker.patch("release_creator.process.shutil.which", return_value="uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess(
            [], 0, "packaging==24.3 ; sys_platform == 'win32'\npackaging==24.4 ; sys_platform != 'win32'\n", ""
        ),
    )

    update_pins(config, "7 days", "3.15")

    assert safe_load(config.read_text(encoding="utf-8"))["repos"][0]["hooks"][0]["additional_dependencies"] == [
        "packaging==24.3; sys_platform == 'win32'",
        "packaging==24.4; sys_platform != 'win32'",
    ]


def test_checks_platform_disjoint_direct_pins(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    source = (
        "repos:\n  - repo: local\n    hooks:\n      - id: format\n"
        "        language: python\n        additional_dependencies:\n"
        "          - \"packaging==24.1; sys_platform == 'win32'\"\n"
        "          - \"packaging==24.2; sys_platform != 'win32'\"\n"
    )
    config.write_text(source, encoding="utf-8")
    mocker.patch("release_creator.process.shutil.which", return_value="uv")
    run = mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess(
            [], 0, "packaging==24.1 ; sys_platform == 'win32'\npackaging==24.2 ; sys_platform != 'win32'\n", ""
        ),
    )

    check_pins(config, "7 days", "3.15")

    assert config.read_text(encoding="utf-8") == source
    expected = 'packaging==24.1; sys_platform == "win32"\npackaging==24.2; sys_platform != "win32"\n'
    assert [call.kwargs["input"] for call in run.call_args_list] == [expected, expected]


def test_resolves_real_universal_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
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
    compiled = run_text(
        ["uv", "pip", "compile", "-", "--universal", "--no-config", "--no-sources", "--no-header", "--no-annotate"],
        stdin="closure-root\n",
        cwd=tmp_path,
    )
    assert compiled.returncode == 0
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: closure\n"
        "        language: python\n        additional_dependencies: [closure-root==0.1.0]\n",
        encoding="utf-8",
    )

    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        side_effect=lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, compiled.stdout, ""),
    )
    update_pins(config, "2099-01-01T00:00:00Z", "3.15")

    assert safe_load(config.read_text(encoding="utf-8"))["repos"][0]["hooks"][0]["additional_dependencies"] == [
        "closure-root==1.0.0",
        "closure-child==2.0.0",
        'closure-color==0.4.6; sys_platform == "win32"',
    ]


def test_hooks_update_runs_isolated_resolver(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = tmp_path / "resolver.py"
    script.write_text(
        dedent("""\
            import json
            import os
            import sys
            from pathlib import Path

            Path(os.environ["RESOLVER_LOG"]).write_text(json.dumps({
                "arguments": sys.argv[1:],
                "input": sys.stdin.read(),
                "index": os.environ.get("UV_INDEX_URL"),
                "pip_index": os.environ.get("PIP_INDEX_URL"),
                "certificate": os.environ.get("SSL_CERT_FILE"),
            }))
            print("packaging==26.1")
            """),
        encoding="utf-8",
    )
    executable = tmp_path / ("uv.cmd" if sys.platform == "win32" else "uv")
    executable.write_text(
        f'@echo off\n"{sys.executable}" "{script}" %*\n'
        if sys.platform == "win32"
        else f"#!{sys.executable}\n{script.read_text(encoding='utf-8')}",
        encoding="utf-8",
    )
    if sys.platform != "win32":
        executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("RESOLVER_LOG", str(tmp_path / "resolver.json"))
    monkeypatch.setenv("UV_INDEX_URL", "https://evil.invalid/simple/")
    monkeypatch.setenv("PIP_INDEX_URL", "https://evil.invalid/simple/")
    monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "untrusted.pem"))
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: format\n"
        "        language: python\n        additional_dependencies: [packaging>=26]\n",
        encoding="utf-8",
    )

    update_pins(config, "7 days", "3.15")

    assert safe_load(config.read_text(encoding="utf-8"))["repos"][0]["hooks"][0]["additional_dependencies"] == [
        "packaging>=26",
        "packaging==26.1",
    ]
    invocation = json.loads((tmp_path / "resolver.json").read_text(encoding="utf-8"))
    assert invocation == {
        "arguments": [
            "pip",
            "compile",
            "-",
            "--universal",
            "--quiet",
            "--no-header",
            "--no-annotate",
            "--no-config",
            "--no-sources",
            "--default-index",
            "https://pypi.org/simple/",
            "--exclude-newer",
            "7 days",
            "--python-version",
            "3.15",
        ],
        "input": "packaging>=26\n",
        "index": None,
        "pip_index": None,
        "certificate": None,
    }


def test_ignores_ambient_uv_resolution_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: format\n"
        "        language: python\n        additional_dependencies: [packaging==26.0]\n",
        encoding="utf-8",
    )
    for name in (
        "UV_INDEX",
        "UV_INDEX_URL",
        "UV_EXTRA_INDEX_URL",
        "UV_DEFAULT_INDEX",
        "UV_FIND_LINKS",
        "UV_CONSTRAINT",
        "UV_OVERRIDE",
        "UV_INSECURE_HOST",
        "PIP_INDEX_URL",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "SSL_CLIENT_CERT",
    ):
        monkeypatch.setenv(name, "https://evil.invalid/simple/")
    mocker.patch("release_creator.process.shutil.which", return_value="uv")
    execute = mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "packaging==26.1\n", ""),
    )

    update_pins(config, "7 days", "3.15")

    assert safe_load(config.read_text(encoding="utf-8"))["repos"][0]["hooks"][0]["additional_dependencies"] == [
        "packaging==26.1"
    ]
    assert execute.call_args.args[0][execute.call_args.args[0].index("--default-index") + 1] == (
        "https://pypi.org/simple/"
    )
    assert all("evil.invalid" not in value for value in execute.call_args.kwargs["env"].values())


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
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
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
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
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
    mocker.patch("release_creator.process.shutil.which", side_effect=lambda name: name)
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


@pytest.mark.parametrize(
    ("output", "message"),
    [
        pytest.param("example @ https://example.org/example.whl\n", "exact index pin", id="direct-url"),
        pytest.param("example>=1\n", "exact index pin", id="range"),
        pytest.param("other==1\n", "omitted direct packages", id="missing-root"),
    ],
)
def test_rejects_unpinned_hook_resolution(tmp_path: Path, mocker: MockerFixture, output: str, message: str) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    source = 'additional_dependencies: ["example==1"]\n'
    config.write_text(source, encoding="utf-8")
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, output, ""),
    )

    with pytest.raises(ValueError, match=message):
        update_pins(config, "7 days", "3.15")

    assert config.read_text(encoding="utf-8") == source


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


@pytest.mark.parametrize(
    ("compiled", "missing"),
    [
        pytest.param("-e file:///checkout\nclick==8.1\n", True, id="required-dependency"),
        pytest.param("-e file:///checkout\n", False, id="no-dependencies"),
    ],
)
def test_check_external_hook_closure(
    tmp_path: Path, mocker: MockerFixture, upstream_python_hook: tuple[Path, str], compiled: str, missing: bool
) -> None:
    upstream, revision = upstream_python_hook
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        f"repos:\n  - repo: {upstream.as_uri()}\n    rev: {revision}\n    hooks:\n      - id: lint\n",
        encoding="utf-8",
    )
    mocker.patch("release_creator.process.shutil.which", side_effect=lambda name: name)
    _mock_hook_compiler(mocker, compiled)

    if missing:
        with pytest.raises(ValueError, match="hook is missing managed dependencies: lint"):
            check_pins(config, "7 days", "3.15")
    else:
        check_pins(config, "7 days", "3.15")


def test_hooks_check_and_update_manifest_default_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture, upstream_python_hook: tuple[Path, str]
) -> None:
    upstream, _ = upstream_python_hook
    (upstream / ".pre-commit-hooks.yaml").write_text(
        "- id: lint\n  name: lint\n  entry: lint\n  language: python\n  additional_dependencies: [packaging==24.2]\n",
        encoding="utf-8",
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
            "Set manifest dependencies",
        ]).returncode
        == 0
    )
    revision = run_text(["git", "-C", str(upstream), "rev-parse", "HEAD"]).stdout.strip()
    monkeypatch.chdir(tmp_path)
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(f"repos:\n  - repo: {upstream.as_uri()}\n    rev: {revision}\n    hooks:\n      - id: lint\n")
    run = _mock_hook_compiler(mocker, "-e file:///checkout\nclick==8.1\npackaging==26.3\n")
    monkeypatch.setattr(sys, "argv", ["release-creator", "hooks", "--check"])

    with pytest.raises(SystemExit, match="2"):
        main()

    monkeypatch.setattr(sys, "argv", ["release-creator", "hooks"])
    main()
    monkeypatch.setattr(sys, "argv", ["release-creator", "hooks", "--check"])
    main()
    updated = config.read_text()
    monkeypatch.setattr(sys, "argv", ["release-creator", "hooks"])
    main()
    monkeypatch.setattr(sys, "argv", ["release-creator", "hooks", "--check"])
    main()

    assert config.read_text() == updated
    assert "packaging==26.3" in safe_load(updated)["repos"][0]["hooks"][0]["additional_dependencies"]
    assert any("packaging==24.2\n" in call.kwargs["input"] for call in run.call_args_list if call.args[0][0] == "uv")


def test_hooks_override_replaces_manifest_default_dependencies(
    tmp_path: Path, mocker: MockerFixture, upstream_python_hook: tuple[Path, str]
) -> None:
    upstream, _ = upstream_python_hook
    (upstream / ".pre-commit-hooks.yaml").write_text(
        "- id: lint\n  name: lint\n  entry: lint\n  language: python\n  additional_dependencies: [packaging==24.2]\n",
        encoding="utf-8",
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
            "Set manifest dependencies",
        ]).returncode
        == 0
    )
    revision = run_text(["git", "-C", str(upstream), "rev-parse", "HEAD"]).stdout.strip()
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        f"repos:\n  - repo: {upstream.as_uri()}\n    rev: {revision}\n    hooks:\n"
        "      - id: lint\n        additional_dependencies: [colorama==0.4.6]\n"
    )
    run = _mock_hook_compiler(mocker, "-e file:///checkout\nclick==8.1\ncolorama==0.4.6\n")

    update_pins(config, "7 days", "3.15")

    assert "packaging==24.2" not in config.read_text()
    assert all("packaging==24.2" not in call.kwargs["input"] for call in run.call_args_list if call.args[0][0] == "uv")


@pytest.mark.parametrize(
    ("dependencies", "error", "message"),
    [
        pytest.param("packaging==24.2", TypeError, "requirement strings", id="not-list"),
        pytest.param("[not a requirement!]", ValueError, "invalid additional dependency", id="invalid"),
        pytest.param("[pkg @ https://example.org/pkg.whl]", ValueError, "direct URLs", id="direct-url"),
    ],
)
def test_hooks_check_rejects_invalid_manifest_dependencies(
    tmp_path: Path,
    upstream_python_hook: tuple[Path, str],
    dependencies: str,
    error: type[Exception],
    message: str,
) -> None:
    upstream, _ = upstream_python_hook
    (upstream / ".pre-commit-hooks.yaml").write_text(
        f"- id: lint\n  name: lint\n  entry: lint\n  language: python\n  additional_dependencies: {dependencies}\n",
        encoding="utf-8",
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
            "Set manifest dependencies",
        ]).returncode
        == 0
    )
    revision = run_text(["git", "-C", str(upstream), "rev-parse", "HEAD"]).stdout.strip()
    config = tmp_path / ".pre-commit-config.yaml"
    source = f"repos:\n  - repo: {upstream.as_uri()}\n    rev: {revision}\n    hooks:\n      - id: lint\n"
    config.write_text(source, encoding="utf-8")

    with pytest.raises(error, match=message):
        check_pins(config, "7 days", "3.15")

    assert config.read_text(encoding="utf-8") == source


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
    mocker.patch("release_creator.process.shutil.which", side_effect=lambda name: name)
    colorama = "colorama==0.4.6\n" if existing else ""
    commands = _mock_hook_compiler(mocker, f"-e file:///checkout\nclick==8.1\n{colorama}")

    update_pins(config, "7 days", "3.15")

    parsed = safe_load(config.read_text(encoding="utf-8"))
    assert parsed["repos"][0]["hooks"][0]["additional_dependencies"] == (
        ["colorama==0.4.6", "click==8.1"] if existing else ["click==8.1"]
    )
    assert any(
        call.args[0][0] == "uv" and ("colorama\n" in call.kwargs["input"]) == existing
        for call in commands.call_args_list
    )
    assert any("--" in call.args[0] and call.args[0][0:2] == ["git", "clone"] for call in commands.call_args_list)
    assert "# release-creator managed" in config.read_text(encoding="utf-8")
    first = config.read_text(encoding="utf-8")

    update_pins(config, "7 days", "3.15")

    assert config.read_text(encoding="utf-8") == first


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        pytest.param("", "3.12", id="manifest-version"),
        pytest.param("        language_version: python3.13\n", "3.13", id="configuration-override"),
    ],
)
def test_resolves_hook_with_effective_python_version(
    tmp_path: Path, mocker: MockerFixture, upstream_python_hook: tuple[Path, str], override: str, expected: str
) -> None:
    upstream, _ = upstream_python_hook
    (upstream / ".pre-commit-hooks.yaml").write_text(
        "- id: lint\n  name: lint\n  entry: lint\n  language: python\n  language_version: python3.12\n",
        encoding="utf-8",
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
            "Set Python version",
        ]).returncode
        == 0
    )
    revision = run_text(["git", "-C", str(upstream), "rev-parse", "HEAD"]).stdout.strip()
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        f"repos:\n  - repo: {upstream.as_uri()}\n    rev: {revision}\n    hooks:\n      - id: lint\n{override}",
        encoding="utf-8",
    )
    commands = _mock_hook_compiler(mocker, "-e file:///checkout\nclick==8.1\n")

    update_pins(config, "7 days", "3.15")

    assert [
        call.args[0][call.args[0].index("--python-version") + 1]
        for call in commands.call_args_list
        if call.args[0][0] == "uv"
    ] == [expected]


@pytest.mark.parametrize("style", [pytest.param("|", id="literal"), pytest.param(">+", id="folded")])
def test_adds_hook_dependencies_after_block_scalar(
    tmp_path: Path, mocker: MockerFixture, upstream_python_hook: tuple[Path, str], style: str
) -> None:
    upstream, revision = upstream_python_hook
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        f"repos:\n  - repo: {upstream.as_uri()}\n    rev: {revision}\n    hooks:\n"
        f"      - id: lint\n        entry: {style}\n          python -m fixture_lint\n"
        "      - id: other\n        language: system\n",
        encoding="utf-8",
    )
    _mock_hook_compiler(mocker, "-e file:///checkout\nclick==8.1\n")

    update_pins(config, "7 days", "3.15")
    first = config.read_text(encoding="utf-8")
    update_pins(config, "7 days", "3.15")

    assert safe_load(first)["repos"][0]["hooks"] == [
        {"id": "lint", "entry": "python -m fixture_lint\n", "additional_dependencies": ["click==8.1"]},
        {"id": "other", "language": "system"},
    ]
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
    command = mocker.spy(process.subprocess, "run")

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
    mocker.patch("release_creator.process.shutil.which", return_value="uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
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


def test_rejects_unavailable_hook_repository(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    source = f"repos:\n  - repo: file:///missing\n    rev: {'a' * 40}\n    hooks:\n      - id: lint\n"
    config.write_text(source, encoding="utf-8")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 1, "", "repository not found"),
    )

    with pytest.raises(ValueError, match="cannot read hook repository"):
        update_pins(config, "7 days", "3.15")
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
    original = process.subprocess.run

    def resolve(
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        stdin: int | None = None,
        **options: object,
    ) -> subprocess.CompletedProcess[str]:
        stdin_text = cast("str | None", options["input"])
        if command[0] == "uv":
            assert stdin_text is not None
            assert stdin_text.startswith("-e file://")
            return subprocess.CompletedProcess(command, 0, output, "")
        return original(
            command,
            cwd=cwd,
            env=env,
            input=stdin_text,
            stdin=stdin,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            timeout=300,
        )

    mocker.patch("release_creator.process.shutil.which", side_effect=lambda name: name)
    return cast("MagicMock", mocker.patch("release_creator.process.subprocess.run", autospec=True, side_effect=resolve))


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
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
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
        pytest.param("additional_dependencies:\n  -   black==1\n", id="spaced-bullet"),
        pytest.param("additional_dependencies: [\n  black==1,\n]\n", id="multiline-flow"),
    ],
)
def test_preserves_dependency_list_on_rerun(tmp_path: Path, mocker: MockerFixture, source: str) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(source, encoding="utf-8")
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "black==2\nclick==8\n", ""),
    )

    update_pins(config, "7 days", "3.15")
    first = config.read_text(encoding="utf-8")
    update_pins(config, "7 days", "3.15")

    assert safe_load(first)["additional_dependencies"] == ["black==2", "click==8"]
    assert config.read_text(encoding="utf-8") == first


def test_adds_managed_dependency_after_folded_root(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text("additional_dependencies:\n  - >-\n    black==1\nnext: value\n", encoding="utf-8")
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "black==2\nclick==8\n", ""),
    )

    update_pins(config, "7 days", "3.15")

    assert safe_load(config.read_text(encoding="utf-8")) == {
        "additional_dependencies": ["black==2", "click==8"],
        "next": "value",
    }


def test_folded_root_stays_when_managed_pin_follows(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        'additional_dependencies:\n  - >-\n    sphinx>=9\n  - "sphinx==9.1" # release-creator managed\n',
        encoding="utf-8",
    )
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "sphinx==9.1\n", ""),
    )

    update_pins(config, "7 days", "3.15")

    assert safe_load(config.read_text(encoding="utf-8"))["additional_dependencies"] == [
        "sphinx>=9",
        "sphinx==9.1",
    ]


def test_updates_multiline_flow_hook_without_stale_pins(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: format\n"
        "        language: python\n        additional_dependencies: [\n"
        '          black==1,\n          "click==7", # release-creator managed\n        ]\n',
        encoding="utf-8",
    )
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "black==2\nclick==8\n", ""),
    )

    update_pins(config, "7 days", "3.15")
    first = config.read_text(encoding="utf-8")
    update_pins(config, "7 days", "3.15")

    assert safe_load(first)["repos"][0]["hooks"][0]["additional_dependencies"] == ["black==2", "click==8"]
    assert first.count("# release-creator managed") == 1
    assert config.read_text(encoding="utf-8") == first


@pytest.mark.parametrize(
    "trailing_newline", [pytest.param(False, id="no-final-newline"), pytest.param(True, id="final-newline")]
)
def test_flow_mapping_marks_transitive_dependencies(
    tmp_path: Path, mocker: MockerFixture, trailing_newline: bool
) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    source = (
        "repos:\n  - repo: local\n    hooks:\n"
        "      - {id: format, language: python, additional_dependencies: [black==1]}"
    )
    config.write_text(f"{source}{'\n' if trailing_newline else ''}", encoding="utf-8")
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "black==2\nclick==8\n", ""),
    )

    update_pins(config, "7 days", "3.15")
    first = config.read_text(encoding="utf-8")
    update_pins(config, "7 days", "3.15")

    assert safe_load(first)["repos"][0]["hooks"][0]["additional_dependencies"] == ["black==2", "click==8"]
    assert first.count("# release-creator managed") == 1
    assert config.read_text(encoding="utf-8") == first


def test_flow_mapping_keeps_direct_dependency_comment(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        "repos:\n  - repo: local\n    hooks:\n"
        "      - {id: format, language: python, additional_dependencies: [\n"
        "          black==1, # keep human note\n        ]}\n",
        encoding="utf-8",
    )
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "black==2\nclick==8\n", ""),
    )

    update_pins(config, "7 days", "3.15")

    updated = config.read_text(encoding="utf-8")
    assert "black==2, # keep human note\n" in updated
    assert safe_load(updated)["repos"][0]["hooks"][0]["additional_dependencies"] == ["black==2", "click==8"]


def test_flow_mapping_removes_orphaned_managed_dependency(tmp_path: Path) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        "repos:\n  - repo: local\n    hooks:\n"
        "      - {id: format, language: python, additional_dependencies: [\n"
        '          "click==8" # release-creator managed\n'
        "        ]}\n",
        encoding="utf-8",
    )

    update_pins(config, "7 days", "3.15")

    assert safe_load(config.read_text(encoding="utf-8"))["repos"][0]["hooks"][0]["additional_dependencies"] == []


def test_flow_sequence_replaces_managed_dependency(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        'additional_dependencies: [\n  black==1,\n  "click==8", # release-creator managed\n]\n', encoding="utf-8"
    )
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "black==2\nclick==9\n", ""),
    )

    update_pins(config, "7 days", "3.15")

    assert safe_load(config.read_text(encoding="utf-8"))["additional_dependencies"] == ["black==2", "click==9"]


def test_preserves_crlf_in_hook_config(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_bytes(b"additional_dependencies: [black==1]\r\n")
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "black==2\nclick==8\n", ""),
    )

    update_pins(config, "7 days", "3.15")

    result = config.read_bytes()
    assert b"\r\n" in result
    assert result.count(b"\n") == result.count(b"\r\n")
    assert safe_load(result)["additional_dependencies"] == ["black==2", "click==8"]


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
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
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


def test_pins_nonexact_dependency_when_root_is_removed(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        'additional_dependencies:\n  - sphinx>=9\n  - "click==9" # release-creator managed\n',
        encoding="utf-8",
    )
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "sphinx==9.1\n", ""),
    )

    update_pins(config, "2026-10-14T00:00:00Z", "3.15")

    assert config.read_text(encoding="utf-8") == (
        'additional_dependencies:\n  - sphinx>=9\n  - "sphinx==9.1" # release-creator managed\n'
    )


def test_resolves_ranges_and_unpinned_roots(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    source = "additional_dependencies: [sphinx>=9, mdformat-gfm]\n"
    config.write_text(source, encoding="utf-8")
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    run = mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "sphinx==9.1\nmdformat-gfm==1.2\ncolorama==0.4.6\n", ""),
    )

    update_pins(config, "2026-10-14T00:00:00Z", "3.15")

    assert safe_load(config.read_text(encoding="utf-8"))["additional_dependencies"] == [
        "sphinx>=9",
        "mdformat-gfm",
        "sphinx==9.1",
        "mdformat-gfm==1.2",
        "colorama==0.4.6",
    ]
    assert run.call_args.kwargs["input"] == "sphinx>=9\nmdformat-gfm\n"


def test_preserves_upper_bound_on_next_hook_update(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text("additional_dependencies:\n  - toml-fmt-common<1.3.3,>=1.3.2\n", encoding="utf-8")
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    run = mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "toml-fmt-common==1.3.2\n", ""),
    )

    update_pins(config, "7 days", "3.15")
    first = config.read_text(encoding="utf-8")
    update_pins(config, "7 days", "3.15")

    assert first == (
        "additional_dependencies:\n  - toml-fmt-common<1.3.3,>=1.3.2\n"
        '  - "toml-fmt-common==1.3.2" # release-creator managed\n'
    )
    assert config.read_text(encoding="utf-8") == first
    assert all(call.kwargs["input"] == "toml-fmt-common<1.3.3,>=1.3.2\n" for call in run.call_args_list)


def test_preserves_wildcard_cap_on_next_hook_update(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text("additional_dependencies: [example==1.*]\n", encoding="utf-8")
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    run = mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "example==1.9\n", ""),
    )

    update_pins(config, "7 days", "3.15")
    first = config.read_text(encoding="utf-8")
    update_pins(config, "7 days", "3.15")

    assert safe_load(first)["additional_dependencies"] == ["example==1.*", "example==1.9"]
    assert config.read_text(encoding="utf-8") == first
    assert all(call.kwargs["input"] == "example==1.*\n" for call in run.call_args_list)


def test_resolves_each_hook_with_its_python_version(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        "default_language_version:\n  python: python3.14\n"
        "repos:\n  - repo: local\n    hooks:\n"
        "      - id: default\n        language: python\n        additional_dependencies: [sphinx>=9]\n"
        "      - id: override\n        language: python\n        language_version: python3.15\n"
        "        additional_dependencies: [sphinx>=9]\n"
    )
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    run = mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "sphinx==9.1\n", ""),
    )

    update_pins(config, "7 days", "3.15")

    assert {call.args[0][call.args[0].index("--python-version") + 1] for call in run.call_args_list} == {"3.14", "3.15"}


def test_explicit_python3_uses_runner_version(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        "default_language_version:\n  python: python3.14\n"
        "repos:\n  - repo: local\n    hooks:\n"
        "      - id: hook\n        language: python\n        language_version: python3\n"
        "        additional_dependencies: [sphinx>=9]\n"
    )
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    run = mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "sphinx==9.1\n", ""),
    )

    update_pins(config, "7 days", "3.15")

    assert run.call_args.args[0][run.call_args.args[0].index("--python-version") + 1] == "3.15"


@pytest.mark.parametrize(
    ("language_version", "expected"),
    [
        pytest.param("python3", "3.15", id="interpreter-major"),
        pytest.param("default", "3.15", id="default"),
    ],
)
def test_resolves_generic_python_hook_version(
    tmp_path: Path, mocker: MockerFixture, language_version: str, expected: str
) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        f"default_language_version:\n  python: {language_version}\nadditional_dependencies: [sphinx>=9]\n"
    )
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    run = mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "sphinx==9.1\n", ""),
    )

    update_pins(config, "7 days", "3.15")

    assert run.call_args.args[0][run.call_args.args[0].index("--python-version") + 1] == expected


def test_rejects_unsupported_hook_python_version(tmp_path: Path) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text("default_language_version:\n  python: python2.7\nadditional_dependencies: [sphinx>=9]\n")

    with pytest.raises(ValueError, match="unsupported Python hook language_version"):
        update_pins(config, "7 days", "3.15")


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            "repos:\n  - repo: local\n    hooks:\n"
            "      - id: first\n        language: python\n        additional_dependencies: &deps [black==1]\n"
            "      - id: second\n        language: python\n        additional_dependencies: *deps\n",
            id="shared-dependency-list",
        ),
        pytest.param(
            "repos:\n  - repo: local\n    hooks:\n"
            "      - id: first\n        language: python\n        args: &deps [black==1]\n"
            "        additional_dependencies: *deps\n",
            id="unrelated-anchored-list",
        ),
        pytest.param(
            "repos:\n  - repo: local\n    hooks:\n"
            "      - id: first\n        language: python\n        args: &deps\n"
            "          - black==1\n        additional_dependencies: *deps\n",
            id="unrelated-anchored-block-list",
        ),
        pytest.param(
            "repos:\n  - repo: local\n    hooks:\n"
            "      - id: first\n        language: python\n        additional_dependencies: [&dep black==1]\n"
            "      - id: second\n        language: python\n        additional_dependencies: [*dep]\n",
            id="shared-scalar",
        ),
    ],
)
def test_rejects_aliased_hook_configuration(tmp_path: Path, mocker: MockerFixture, source: str) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(source, encoding="utf-8")
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "black==2\n", ""),
    )

    with pytest.raises(ValueError, match="YAML aliases cannot be updated safely"):
        update_pins(config, "7 days", "3.15")

    assert config.read_text(encoding="utf-8") == source


def test_updates_hook_with_unrelated_yaml_alias(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        "ci:\n  label: &label dependencies\n  body: *label\nadditional_dependencies: [sphinx>=9]\n",
        encoding="utf-8",
    )
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "sphinx==9.1\n", ""),
    )

    update_pins(config, "7 days", "3.15")

    assert config.read_text(encoding="utf-8").startswith("ci:\n  label: &label dependencies\n  body: *label\n")
    assert safe_load(config.read_text(encoding="utf-8"))["additional_dependencies"] == ["sphinx>=9", "sphinx==9.1"]


def test_rejects_hook_merge_with_hidden_dependencies(tmp_path: Path) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    source = (
        "repos:\n  - repo: local\n    hooks:\n"
        "      - &base\n        id: source\n        name: source\n        entry: true\n"
        "        language: system\n        additional_dependencies: [sphinx>=9]\n"
        "      - <<: *base\n        id: docs\n        name: docs\n"
        "        entry: python -m sphinx\n        language: python\n"
    )
    config.write_text(source, encoding="utf-8")
    assert safe_load(source)["repos"][0]["hooks"][1]["additional_dependencies"] == ["sphinx>=9"]

    with pytest.raises(ValueError, match="YAML merge keys in hook definitions"):
        update_pins(config, "7 days", "3.15")

    assert config.read_text(encoding="utf-8") == source


def test_rejects_repository_merge_with_hidden_source(tmp_path: Path, upstream_python_hook: tuple[Path, str]) -> None:
    upstream, revision = upstream_python_hook
    config = tmp_path / ".pre-commit-config.yaml"
    source = (
        f"repos:\n  - &remote\n    repo: {upstream.as_uri()}\n    rev: {revision}\n    hooks: []\n"
        "  - <<: *remote\n    hooks:\n      - id: lint\n        additional_dependencies: [click==8]\n"
    )
    config.write_text(source, encoding="utf-8")
    assert safe_load(source)["repos"][1]["repo"] == upstream.as_uri()

    with pytest.raises(ValueError, match="YAML merge keys in repository definitions"):
        update_pins(config, "7 days", "3.15")

    assert config.read_text(encoding="utf-8") == source


def test_keeps_flow_dependencies_with_a_trailing_managed_comment(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text("additional_dependencies: [packaging==26, click==8] # release-creator managed\n")
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "packaging==26\nclick==8\n", ""),
    )

    update_pins(config, "7 days", "3.15")

    assert safe_load(config.read_text(encoding="utf-8"))["additional_dependencies"] == ["packaging==26", "click==8"]


@pytest.mark.parametrize(
    "duplicate",
    [
        pytest.param(
            "additional_dependencies: [safe==1]\n        additional_dependencies: [untrusted]", id="dependencies"
        ),
        pytest.param("language: system\n        language: python", id="language"),
    ],
)
def test_rejects_duplicate_hook_keys(tmp_path: Path, mocker: MockerFixture, duplicate: str) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    source = f"repos:\n  - repo: local\n    hooks:\n      - id: check\n        {duplicate}\n"
    config.write_text(source, encoding="utf-8")
    run = mocker.patch("release_creator.process.subprocess.run", autospec=True)

    with pytest.raises(ValueError, match="duplicate YAML key"):
        update_pins(config, "7 days", "3.15")

    assert config.read_text(encoding="utf-8") == source
    run.assert_not_called()


def test_rejects_non_scalar_yaml_key(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    source = "? [unsafe, key]\n: value\nadditional_dependencies: [black==1]\n"
    config.write_text(source, encoding="utf-8")
    run = mocker.patch("release_creator.process.subprocess.run", autospec=True)

    with pytest.raises(TypeError, match="keys must be YAML scalars"):
        update_pins(config, "7 days", "3.15")

    assert config.read_text(encoding="utf-8") == source
    run.assert_not_called()


def test_rejects_resolver_failure(tmp_path: Path, mocker: MockerFixture) -> None:
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text("additional_dependencies: [mdformat-gfm==1.0.0]\n", encoding="utf-8")
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 1, "", "index unavailable"),
    )

    with pytest.raises(ValueError, match="index unavailable"):
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
    mocker.patch("release_creator.process.shutil.which", return_value="/usr/bin/uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "mdformat-gfm==1.0.0\n", ""),
    )

    update_pins(config, "2026-10-14T00:00:00Z", "3.15")

    assert config.read_text(encoding="utf-8") == source


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(("hook-root==1.0", "", "hook-root==1.0\n", True), id="removed-unneeded-pin"),
        pytest.param(("hook-root==1.0", "", "hook-root==1.0\nhook-child==2.0\n", False), id="missing-needed-pin"),
        pytest.param(
            (
                "hook-root==1.0",
                "hook-child==2.0",
                "hook-root==1.0\nhook-child==2.0\n",
                True,
            ),
            id="complete-older-exact-revision",
        ),
        pytest.param(
            ("hook-root==1.0", "hook-child==2.0", "hook-root==1.0\n", False),
            id="stale-managed-pin",
        ),
        pytest.param(
            ("hook-root>=1", "hook-root==1.0", "hook-root==1.0\n", True),
            id="range-keeps-declared-constraint",
        ),
    ],
)
def test_hooks_check_compares_complete_proposed_closure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    case: tuple[str, str, str, bool],
) -> None:
    monkeypatch.chdir(tmp_path)
    direct, managed, resolved, passes = case
    managed_line = f"          - {managed} # release-creator managed\n" if managed else ""
    source = (
        "repos:\n  - repo: local\n    hooks:\n      - id: lint\n"
        "        language: python\n        additional_dependencies:\n"
        f"          - {direct}\n"
        f"{managed_line}"
    )
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(source, encoding="utf-8")
    mocker.patch("release_creator.process.shutil.which", return_value="uv")
    constraints: list[str] = []

    def compile_hooks(command: list[str], **options: object) -> subprocess.CompletedProcess[str]:
        assert options["input"] == f"{direct}\n"
        assert "--no-config" in command
        assert "--no-sources" in command
        assert command[command.index("--exclude-newer") + 1] == "7 days"
        if "--constraint" in command:
            constraints.append(Path(command[command.index("--constraint") + 1]).read_text(encoding="utf-8"))
        return subprocess.CompletedProcess(command, 0, resolved, "")

    mocker.patch("release_creator.process.subprocess.run", autospec=True, side_effect=compile_hooks)
    monkeypatch.setattr(sys, "argv", ["release-creator", "hooks", "--check"])

    if passes:
        main()
    else:
        with pytest.raises(SystemExit, match="2"):
            main()

    assert config.read_text(encoding="utf-8") == source
    assert constraints == ([f"{managed}\n"] if managed else [])


@pytest.mark.parametrize(
    "managed",
    [
        pytest.param("not a requirement", id="invalid-requirement"),
        pytest.param("hook-child>=2", id="not-exact"),
        pytest.param("hook-child @ https://example.invalid/child.whl", id="direct-url"),
    ],
)
def test_hooks_check_rejects_invalid_managed_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture, managed: str
) -> None:
    monkeypatch.chdir(tmp_path)
    source = (
        "repos:\n  - repo: local\n    hooks:\n      - id: lint\n"
        "        language: python\n        additional_dependencies:\n"
        "          - hook-root==1.0\n"
        f"          - '{managed}' # release-creator managed\n"
    )
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(source, encoding="utf-8")
    run = mocker.patch("release_creator.process.subprocess.run", autospec=True)
    monkeypatch.setattr(sys, "argv", ["release-creator", "hooks", "--check"])

    with pytest.raises(SystemExit, match="2"):
        main()

    assert config.read_text(encoding="utf-8") == source
    run.assert_not_called()


def test_hooks_check_rejects_conflicting_proposed_pins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    config = tmp_path / ".pre-commit-config.yaml"
    config.write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: lint\n"
        "        language: python\n        additional_dependencies:\n"
        "          - hook-root==1.0\n"
        "          - hook-root==2.0 # release-creator managed\n",
        encoding="utf-8",
    )
    mocker.patch("release_creator.process.shutil.which", return_value="uv")
    mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        return_value=subprocess.CompletedProcess([], 0, "hook-root==1.0\n", ""),
    )
    monkeypatch.setattr(sys, "argv", ["release-creator", "hooks", "--check"])

    with pytest.raises(SystemExit, match="2"):
        main()


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(("python3.15", "packaging==24.2; python_version < '3.12'", "", "", True), id="inactive-root"),
        pytest.param(
            ("python3.15", "packaging==24.2; python_version >= '3.15'", "packaging==24.2\n", "packaging==24.2\n", True),
            id="active-root",
        ),
        pytest.param(
            (
                "python3.15",
                "packaging==24.2",
                "colorama==0.4.6; python_version < '3.12'",
                "packaging==24.2\n",
                True,
            ),
            id="inactive-managed",
        ),
        pytest.param(
            (
                "python3.11",
                "packaging==24.2; python_version < '3.12'",
                "",
                "packaging==24.2 ; python_full_version < '3.12'\n",
                True,
            ),
            id="alternate-python",
        ),
        pytest.param(
            (
                "python3.15",
                "packaging==24.2",
                "colorama==0.4.6; python_version >= '3.15'",
                "packaging==24.2\n",
                False,
            ),
            id="missing-active-managed",
        ),
    ],
)
def test_hooks_check_uses_active_marker_selections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    case: tuple[str, str, str, str, bool],
) -> None:
    language_version, direct, managed, resolved, passes = case
    monkeypatch.chdir(tmp_path)
    config = tmp_path / ".pre-commit-config.yaml"
    managed_line = f'          - "{managed}" # release-creator managed\n' if managed else ""
    config.write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: lint\n"
        f"        language: python\n        language_version: {language_version}\n"
        "        additional_dependencies:\n"
        f'          - "{direct}"\n{managed_line}',
        encoding="utf-8",
    )
    mocker.patch("release_creator.process.shutil.which", return_value="uv")
    commands: list[list[str]] = []

    def compile_hooks(command: list[str], **_options: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        assert command[command.index("--python-version") + 1] == language_version.removeprefix("python")
        output = (resolved if passes else f"{resolved}colorama==0.4.6\n") if "--no-deps" in command else resolved
        return subprocess.CompletedProcess(command, 0, output, "")

    mocker.patch("release_creator.process.subprocess.run", autospec=True, side_effect=compile_hooks)
    monkeypatch.setattr(sys, "argv", ["release-creator", "hooks", "--check"])

    if passes:
        main()
    else:
        with pytest.raises(SystemExit, match="2"):
            main()

    assert ["--no-deps" in command for command in commands] == [False, True]


def test_hooks_update_preserves_inactive_direct_marker_then_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    config = tmp_path / ".pre-commit-config.yaml"
    source = (
        "repos:\n  - repo: local\n    hooks:\n      - id: lint\n"
        "        language: python\n        language_version: python3.15\n"
        "        additional_dependencies:\n"
        "          - \"packaging==24.2; python_version < '3.12'\"\n"
    )
    config.write_text(source, encoding="utf-8")
    mocker.patch("release_creator.process.shutil.which", return_value="uv")
    run = mocker.patch(
        "release_creator.process.subprocess.run",
        autospec=True,
        side_effect=lambda command, **_options: subprocess.CompletedProcess(command, 0, "", ""),
    )

    monkeypatch.setattr(sys, "argv", ["release-creator", "hooks"])
    main()
    monkeypatch.setattr(sys, "argv", ["release-creator", "hooks", "--check"])
    main()

    assert config.read_text(encoding="utf-8") == source
    assert any("--no-deps" in call.args[0] for call in run.call_args_list)


def test_hooks_check_honors_minimum_days(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: lint\n"
        "        language: python\n        additional_dependencies: [packaging==24.2]\n"
    )
    mocker.patch("release_creator.process.shutil.which", return_value="uv")

    def resolve(command: list[str], **_options: object) -> subprocess.CompletedProcess[str]:
        assert command[command.index("--exclude-newer") + 1] == "14 days"
        return subprocess.CompletedProcess(command, 0, "packaging==24.2\n", "")

    run = mocker.patch("release_creator.process.subprocess.run", autospec=True, side_effect=resolve)
    monkeypatch.setattr(sys, "argv", ["release-creator", "hooks", "--check", "--minimum-days", "14"])

    main()

    assert run.call_count == 1


def test_hooks_rejects_short_minimum_days(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["release-creator", "hooks", "--check", "--minimum-days", "6"])

    with pytest.raises(SystemExit, match="2"):
        main()

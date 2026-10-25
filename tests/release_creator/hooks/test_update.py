"""Behavioral tests for pre-commit dependency pins."""

import re
import subprocess  # ruff: ignore[suspicious-subprocess-import]  # CompletedProcess models the uv boundary.
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from yaml import safe_load

lazy from release_creator.hooks.update import check_pins, update_pins
lazy from release_creator.process import run_text

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture

type _Uv = Callable[..., MagicMock]
type _Upstream = Callable[[str], str]

_PYTHON_HOOK = "- id: lint\n  name: lint\n  entry: lint\n  language: python\n"


@pytest.fixture
def uv(mocker: MockerFixture) -> _Uv:
    """Replace uv with canned compile outputs, one per call, and let every other command run."""
    real = subprocess.run

    def install(*outputs: str, returncode: int = 0) -> MagicMock:
        pending = list(outputs)

        def run(
            command: list[str], *, cwd: Path | None = None, **_: str | int | bool | Mapping[str, str] | None
        ) -> subprocess.CompletedProcess[str]:
            if command[0] != "uv":
                return real(command, cwd=cwd, capture_output=True, check=False, text=True)
            return subprocess.CompletedProcess(command, returncode, pending.pop(0), "resolver failed")

        return cast("MagicMock", mocker.patch("release_creator.process.subprocess.run", autospec=True, side_effect=run))

    return install


@pytest.fixture
def config(tmp_path: Path) -> Path:
    return tmp_path / ".pre-commit-config.yaml"


@pytest.fixture
def upstream(tmp_path: Path) -> _Upstream:
    """Commit a hook repository with the given manifest and return the configuration up to its hooks."""
    repository = tmp_path / "upstream"

    def create(manifest: str) -> str:
        repository.mkdir()
        (repository / ".pre-commit-hooks.yaml").write_text(manifest, encoding="utf-8")
        for command in (
            ["init", "-q"],
            ["add", "."],
            ["-c", "user.name=Test", "-c", "user.email=test@example.org", "commit", "-qm", "Init"],
        ):
            _git(repository, *command)
        return (
            f"repos:\n  - repo: {repository.as_uri()}\n    rev: {_git(repository, 'rev-parse', 'HEAD')}\n    hooks:\n"
        )

    return create


def _git(repository: Path, *arguments: str) -> str:
    result = run_text(["git", "-C", str(repository), *arguments])
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _local(dependencies: str, extra: str = "") -> str:
    return f"repos:\n  - repo: local\n    hooks:\n      - id: lint\n        language: python\n{extra}{dependencies}"


def test_update_pins_local_hook_closure(config: Path, uv: _Uv) -> None:
    config.write_text(
        _local(
            "        additional_dependencies: # keep\n"
            "          - Sphinx==9.0.0 # chosen\n"
            "          - mdformat>=1\n"
            '          - "stale==1" # release-creator managed\n'
        ),
        encoding="utf-8",
    )
    run = uv("sphinx==9.1.1\nmdformat==1.0.0\ncolorama==0.4.6 ; sys_platform == 'win32'\n")

    update_pins(config, "7 days", "3.15")

    assert (config.read_text(encoding="utf-8"), run.call_args.kwargs["input"]) == (
        _local(
            "        additional_dependencies: # keep\n"
            "          - Sphinx==9.1.1 # chosen\n"
            "          - mdformat>=1\n"
            '          - "mdformat==1.0.0" # release-creator managed\n'
            '          - "colorama==0.4.6; sys_platform == \\"win32\\"" # release-creator managed\n'
        ),
        "Sphinx\nmdformat>=1\n",
    )


def test_update_pins_runs_isolated_universal_resolution(config: Path, uv: _Uv, monkeypatch: pytest.MonkeyPatch) -> None:
    config.write_text(_local("        additional_dependencies: [packaging==26.0]\n"), encoding="utf-8")
    monkeypatch.setenv("UV_INDEX_URL", "https://evil.invalid/simple/")
    run = uv("packaging==26.0\n")

    update_pins(config, "7 days", "3.12")

    assert (run.call_args.args[0], "UV_INDEX_URL" in run.call_args.kwargs["env"]) == (
        [
            "uv",
            "pip",
            "compile",
            "-",
            "--universal",
            "--quiet",
            "--no-header",
            "--no-annotate",
            "--no-config",
            "--no-sources",
            "--exclude-newer",
            "7 days",
            "--python-version",
            "3.12",
        ],
        False,
    )


def test_update_pins_repins_flow_list_in_place(config: Path, uv: _Uv) -> None:
    config.write_text(_local("        additional_dependencies: [rust-just==1.59.0]\n"), encoding="utf-8")
    uv("rust-just==1.60.0\n")

    update_pins(config, "7 days", "3.15")

    assert config.read_text(encoding="utf-8") == _local("        additional_dependencies: [rust-just==1.60.0]\n")


@pytest.mark.parametrize(
    "dependencies",
    [
        pytest.param("[black>=26]", id="range"),
        pytest.param(
            '[\n          black==26.1.0,\n          "click==8.1", # release-creator managed\n        ]', id="managed"
        ),
    ],
)
def test_update_pins_rejects_flow_list_with_managed_pins(config: Path, uv: _Uv, dependencies: str) -> None:
    config.write_text(_local(f"        additional_dependencies: {dependencies}\n"), encoding="utf-8")
    uv("black==26.1.0\nclick==8.1\n")

    with pytest.raises(ValueError, match="write additional_dependencies on line 6 as a block list"):
        update_pins(config, "7 days", "3.15")


def test_update_pins_empties_list_without_closure(config: Path, uv: _Uv) -> None:
    other = "      - id: other\n        language: system\n"
    config.write_text(
        _local('        additional_dependencies:\n          - "click==8.1" # release-creator managed\n') + other,
        encoding="utf-8",
    )
    run = uv()

    update_pins(config, "7 days", "3.15")

    assert (config.read_text(encoding="utf-8"), run.call_count) == (
        _local("        additional_dependencies: []\n") + other,
        0,
    )


def test_update_pins_leaves_current_config_untouched(config: Path, uv: _Uv) -> None:
    source = (
        _local("        additional_dependencies:\n          - black==26.1.0\n")
        + "      - id: empty\n        language: python\n"
    )
    config.write_text(source, encoding="utf-8")
    run = uv("black==26.1.0\n")

    update_pins(config, "7 days", "3.15")

    assert (config.read_text(encoding="utf-8"), run.call_count) == (source, 1)


def test_update_pins_appends_to_list_without_final_newline(config: Path, uv: _Uv) -> None:
    config.write_text(_local("        additional_dependencies:\n          - black==26.1.0"), encoding="utf-8")
    uv("black==26.1.0\nclick==8.1\n")

    update_pins(config, "7 days", "3.15")

    assert config.read_text(encoding="utf-8") == _local(
        "        additional_dependencies:\n"
        "          - black==26.1.0\n"
        '          - "click==8.1" # release-creator managed\n'
    )


@pytest.mark.parametrize(
    "last",
    [
        pytest.param("        entry: |\n          lint --fix\n", id="block-scalar"),
        pytest.param("        entry: |\n          lint --fix", id="block-scalar-without-final-newline"),
        pytest.param("        args:\n          - --fix\n", id="block-sequence"),
        pytest.param("        env:\n          KEEP: x\n", id="block-mapping"),
    ],
)
def test_update_pins_adds_list_to_remote_hook(config: Path, uv: _Uv, upstream: _Upstream, last: str) -> None:
    header = upstream(f"{_PYTHON_HOOK}  additional_dependencies: [tomli==2.0.0]\n")
    config.write_text(f"{header}      - id: lint\n{last}", encoding="utf-8")
    run = uv("-e file:///checkout\nclick==8.1\ntomli==2.2.1\n")

    update_pins(config, "7 days", "3.15")

    assert config.read_text(encoding="utf-8") == (
        f"{header}      - id: lint\n{last.rstrip()}\n"
        '        additional_dependencies:\n          - "tomli==2.2.1"\n'
        '          - "click==8.1" # release-creator managed\n'
    )
    assert re.fullmatch(r"-e file://\S+/0\ntomli\n", run.call_args.kwargs["input"])


def test_update_pins_rejects_flow_style_remote_hook(config: Path, uv: _Uv, upstream: _Upstream) -> None:
    config.write_text(f"{upstream(_PYTHON_HOOK)}      - {{id: lint}}\n", encoding="utf-8")
    uv("-e file:///checkout\nclick==8.1\n")

    with pytest.raises(ValueError, match="cannot add managed dependencies to a flow-style hook: lint"):
        update_pins(config, "7 days", "3.15")


@pytest.mark.parametrize(
    ("hook", "expected"),
    [
        pytest.param("", "3.12", id="manifest"),
        pytest.param("        language_version: python3.13t\n", "3.13", id="configured-free-threaded"),
        pytest.param("        language_version: python3\n", "3.15", id="system"),
        pytest.param("        language_version: default\n", "3.11", id="default"),
    ],
)
def test_update_pins_selects_hook_python_version(
    config: Path, uv: _Uv, upstream: _Upstream, hook: str, expected: str
) -> None:
    header = upstream(f"{_PYTHON_HOOK}  language_version: python3.12\n")
    config.write_text(
        f"default_language_version:\n  python: python3.11\n{header}      - id: lint\n{hook}", encoding="utf-8"
    )
    run = uv("-e file:///checkout\n")

    update_pins(config, "7 days", "3.15")

    assert run.call_args.args[0][-1] == expected


def test_update_pins_skips_hooks_of_other_languages(config: Path, uv: _Uv, upstream: _Upstream) -> None:
    source = f"{upstream('- id: lint\n  name: lint\n  entry: lint\n  language: node\n')}      - id: lint\n"
    config.write_text(f"{source}  - repo: meta\n    hooks:\n      - id: check-hooks-apply\n", encoding="utf-8")
    run = uv()

    update_pins(config, "7 days", "3.15")

    assert [call for call in run.call_args_list if call.args[0][0] == "uv"] == []


def test_check_pins_accepts_resolved_closure(config: Path, uv: _Uv) -> None:
    managed = '          - "click==8.1" # release-creator managed\n'
    config.write_text(
        _local(f"        additional_dependencies:\n          - black==26.1.0\n{managed}"), encoding="utf-8"
    )
    run = uv("black==26.1.0\nclick==8.1\n")

    check_pins(config, "7 days", "3.15")

    assert (run.call_args.kwargs["input"], Path(run.call_args.args[0][-1]).name) == (
        "black==26.1.0\n",
        "constraints.txt",
    )


@pytest.mark.parametrize(
    ("dependencies", "output"),
    [
        pytest.param("          - black==26.1.0\n", "black==26.1.0\nclick==8.1\n", id="missing-pin"),
        pytest.param('          - "click==8.1" # release-creator managed\n', "", id="stale-pin"),
    ],
)
def test_check_pins_rejects_other_closure(config: Path, uv: _Uv, dependencies: str, output: str) -> None:
    config.write_text(_local(f"        additional_dependencies:\n{dependencies}"), encoding="utf-8")
    uv(output)

    with pytest.raises(ValueError, match="hook dependency pins do not match the resolved closure: lint"):
        check_pins(config, "7 days", "3.15")


@pytest.mark.parametrize(
    ("output", "missing"),
    [
        pytest.param("-e file:///checkout\nclick==8.1\n", True, id="required-dependency"),
        pytest.param("-e file:///checkout\n", False, id="no-dependencies"),
    ],
)
def test_check_pins_requires_list_for_remote_dependencies(
    config: Path, uv: _Uv, upstream: _Upstream, output: str, missing: bool
) -> None:
    config.write_text(f"{upstream(_PYTHON_HOOK)}      - id: lint\n", encoding="utf-8")
    uv(output)

    if missing:
        with pytest.raises(ValueError, match="hook is missing managed dependencies: lint"):
            check_pins(config, "7 days", "3.15")
    else:
        check_pins(config, "7 days", "3.15")


@pytest.mark.parametrize("check", [pytest.param(False, id="update"), pytest.param(True, id="check")])
def test_pins_skip_hook_without_roots(config: Path, uv: _Uv, check: bool) -> None:
    source = _local("        additional_dependencies: []\n")
    config.write_text(source, encoding="utf-8")
    run = uv()

    (check_pins if check else update_pins)(config, "7 days", "3.15")

    assert (config.read_text(encoding="utf-8"), run.call_count) == (source, 0)


@pytest.mark.parametrize(
    "dependency",
    [
        pytest.param("--index-url=https://evil.invalid", id="option"),
        pytest.param("-e .", id="editable"),
        pytest.param("black @ https://evil.invalid/black.whl", id="direct-url"),
        pytest.param("git+https://evil.invalid/black", id="vcs-url"),
        pytest.param("file:black", id="file"),
        pytest.param("./black", id="relative-path"),
        pytest.param("vendor/black", id="path"),
        pytest.param("C:\\\\black", id="windows-path"),
        pytest.param("black-26.1.0-py3-none-any.whl", id="wheel-file"),
        pytest.param("black.tar.gz", id="sdist-file"),
    ],
)
def test_update_pins_rejects_non_index_dependency(config: Path, uv: _Uv, dependency: str) -> None:
    config.write_text(_local(f'        additional_dependencies: ["{dependency}"]\n'), encoding="utf-8")
    run = uv()

    with pytest.raises(ValueError, match="must be a package requirement, not an option, URL, or path"):
        update_pins(config, "7 days", "3.15")

    assert run.call_count == 0


def test_update_pins_rejects_non_index_manifest_dependency(config: Path, uv: _Uv, upstream: _Upstream) -> None:
    config.write_text(
        f"{upstream(f'{_PYTHON_HOOK}  additional_dependencies: [--extra-index-url=https://evil.invalid]\n')}"
        "      - id: lint\n",
        encoding="utf-8",
    )
    uv()

    with pytest.raises(ValueError, match="must be a package requirement"):
        update_pins(config, "7 days", "3.15")


@pytest.mark.parametrize(
    ("source", "message"),
    [
        pytest.param("default_env:\n  UV_INDEX_URL: x\nrepos: []\n", "default_env must not set UV_INDEX_URL", id="uv"),
        pytest.param(
            _local("", "        env:\n          pip_index_url: x\n          PYTHONPATH: x\n          KEEP: x\n"),
            "hook lint env must not set PYTHONPATH, pip_index_url",
            id="hook",
        ),
    ],
)
def test_update_pins_rejects_installer_env(config: Path, source: str, message: str) -> None:
    config.write_text(source, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        update_pins(config, "7 days", "3.15")


@pytest.mark.parametrize(
    ("dependency", "message"),
    [
        pytest.param(
            "'black==26; python_version < \"3.14\"'", "hook dependency markers are not supported", id="marker"
        ),
        pytest.param(
            '"click>=8" # release-creator managed', "managed hook dependency must be an exact pin", id="range"
        ),
        pytest.param(
            '"click[x]==8" # release-creator managed', "managed hook dependency must be an exact pin", id="extra"
        ),
        pytest.param("'black=='", "invalid hook dependency 'black=='", id="invalid"),
    ],
)
def test_update_pins_rejects_unsupported_requirement(config: Path, dependency: str, message: str) -> None:
    config.write_text(_local(f"        additional_dependencies:\n          - {dependency}\n"), encoding="utf-8")

    with pytest.raises(ValueError, match=re.escape(message)):
        update_pins(config, "7 days", "3.15")


@pytest.mark.parametrize(
    ("source", "error", "message"),
    [
        pytest.param("repos: [", ValueError, "invalid pre-commit YAML", id="invalid-yaml"),
        pytest.param("- repo: local\n", TypeError, "must be a YAML mapping", id="list-root"),
        pytest.param("default_install_hook_types: []\n", TypeError, "must list repos", id="no-repos"),
        pytest.param("repos: [local]\n", TypeError, "must be a mapping with a list of hooks", id="repository"),
        pytest.param(
            "repos:\n  - repo: local\n    hooks: [lint]\n", TypeError, "must be a mapping with an id", id="hook"
        ),
        pytest.param(
            "x: &deps [black]\n" + _local("        additional_dependencies: *deps\n"),
            ValueError,
            "YAML aliases are not supported",
            id="alias",
        ),
        pytest.param(
            _local("", "        <<: {additional_dependencies: [black]}\n"),
            ValueError,
            "unique scalars without merge keys",
            id="merge-key",
        ),
        pytest.param(_local("", "        language: system\n"), ValueError, "unique scalars", id="duplicate-key"),
        pytest.param("? [a]\n: b\nrepos: []\n", ValueError, "unique scalars", id="non-scalar-key"),
        pytest.param(_local("        additional_dependencies: black\n"), TypeError, "must be a list", id="scalar-list"),
        pytest.param(
            _local("", "        language_version: pypy3\n"),
            ValueError,
            "unsupported Python hook",
            id="language-version",
        ),
        pytest.param(
            "repos:\n  - repo: local\n    hooks:\n      - id: lint\n        language: node\n"
            "        additional_dependencies: [prettier]\n",
            ValueError,
            "only supported for Python hooks: lint",
            id="node-dependencies",
        ),
        pytest.param(
            "repos:\n  - repo: https://example.org/hooks\n    rev: v1.0.0\n    hooks: []\n",
            ValueError,
            "must use a frozen commit",
            id="tag-revision",
        ),
    ],
)
def test_update_pins_rejects_bad_config(config: Path, source: str, error: type[Exception], message: str) -> None:
    config.write_text(source, encoding="utf-8")

    with pytest.raises(error, match=message):
        update_pins(config, "7 days", "3.15")


def test_update_pins_rejects_non_string_manifest_dependencies(config: Path, upstream: _Upstream) -> None:
    header = upstream(f"{_PYTHON_HOOK}  additional_dependencies: [1]\n")
    config.write_text(f"{header}      - id: lint\n", encoding="utf-8")

    with pytest.raises(TypeError, match="manifest additional_dependencies must be requirement strings: lint"):
        update_pins(config, "7 days", "3.15")


def test_update_pins_reports_unavailable_repository(config: Path, tmp_path: Path) -> None:
    config.write_text(
        f"repos:\n  - repo: {(tmp_path / 'missing').as_uri()}\n    rev: {'a' * 40}\n    hooks: []\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=f"cannot read hook repository .*missing@{'a' * 40}"):
        update_pins(config, "7 days", "3.15")


@pytest.mark.parametrize(
    ("dependencies", "resolution", "message"),
    [
        pytest.param("[black]", ("", 1), "cannot resolve hook dependencies: resolver failed", id="failure"),
        pytest.param("[black]", ("black>=26\n", 0), "did not return exact index pins: black>=26", id="unpinned"),
        pytest.param("[black==26.1.0]", ("click==8.1\n", 0), "omitted direct packages: black", id="omitted"),
        pytest.param(
            "\n          - black>=26",
            ("black==26.1.0\nblack==26.2.0\n", 0),
            "conflicting hook dependency pins for black",
            id="conflict",
        ),
    ],
)
def test_update_pins_rejects_bad_resolution(
    config: Path, uv: _Uv, dependencies: str, resolution: tuple[str, int], message: str
) -> None:
    config.write_text(_local(f"        additional_dependencies: {dependencies}\n"), encoding="utf-8")
    uv(resolution[0], returncode=resolution[1])

    with pytest.raises(ValueError, match=message):
        update_pins(config, "7 days", "3.15")


def test_update_and_check_pins_with_real_uv(config: Path) -> None:
    config.write_text(_local('        additional_dependencies:\n          - "packaging>=24,<24.3"\n'), encoding="utf-8")

    update_pins(config, "7 days", "3.15")
    check_pins(config, "7 days", "3.15")

    assert safe_load(config.read_text(encoding="utf-8"))["repos"][0]["hooks"][0]["additional_dependencies"] == [
        "packaging>=24,<24.3",
        "packaging==24.2",
    ]

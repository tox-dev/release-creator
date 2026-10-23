"""Fragment command tests against a Git checkout."""

from __future__ import annotations

import json
import os
import sys
lazy from pathlib import Path

import pytest

from release_creator.cli import main
from release_creator.process import run_text


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            (
                "+topic.feature.md",
                "Add a feature.\n",
                "towncrier",
                "Add a feature ([#3](https://github.com/tox-dev/example/pull/3)) by [@alice](https://github.com/alice).\n",
            ),
            id="towncrier",
        ),
        pytest.param(
            (
                "trust-roots.md",
                "---\ndefault: security\n---\n\n# Remove a distrusted root\n",
                "knope",
                (
                    "---\ndefault: security\n---\n\n# Remove a distrusted root "
                    "([#3](https://github.com/tox-dev/example/pull/3)) by [@alice](https://github.com/alice)\n"
                ),
            ),
            id="knope",
        ),
    ],
)
def test_fragments_cli_links_merged_pull_request(
    git_repository: tuple[Path, str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    case: tuple[str, str, str, str],
) -> None:
    name, content, format_name, expected = case
    checkout, git = git_repository
    directory = checkout / (".changeset" if format_name == "knope" else "changelog.d")
    directory.mkdir()
    fragment = directory / name
    fragment.write_text(content)
    assert run_text([git, "add", str(directory)]).returncode == 0
    assert run_text([git, "commit", "-qm", "A subject without a PR number"]).returncode == 0
    commit = run_text([git, "rev-parse", "HEAD"]).stdout.strip()
    query = _fake_github_pull(tmp_path, monkeypatch, commit, numbered=False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["release-creator", "fragments", "--format", format_name, "--repository", "tox-dev/example"],
    )

    main()

    assert fragment.read_text() == expected
    assert "c0: object" in query.read_text()


def test_fragments_cli_uses_numbered_prs(
    git_repository: tuple[Path, str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    checkout, git = git_repository
    directory = checkout / "changelog.d"
    directory.mkdir()
    fragment = directory / "3.feature.md"
    fragment.write_text("Add a feature.\n")
    assert run_text([git, "add", str(directory)]).returncode == 0
    assert run_text([git, "commit", "-qm", "Backfill"]).returncode == 0
    commit = run_text([git, "rev-parse", "HEAD"]).stdout.strip()
    query = _fake_github_pull(tmp_path, monkeypatch, commit, numbered=True)
    monkeypatch.setattr(
        sys,
        "argv",
        ["release-creator", "fragments", "--repository", "tox-dev/example", "--numbered-prs"],
    )

    main()

    assert fragment.read_text() == (
        "Add a feature ([#3](https://github.com/tox-dev/example/pull/3)) by [@alice](https://github.com/alice).\n"
    )
    assert "p0: pullRequest(number: 3)" in query.read_text()


def _fake_github_pull(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, commit: str, *, numbered: bool) -> Path:
    response = {
        "data": {
            "repository": {
                ("p0" if numbered else "c0"): (
                    {
                        "number": 3,
                        "mergedAt": "2026-10-22T00:00:00Z",
                        "author": {"login": "alice", "__typename": "User"},
                    }
                    if numbered
                    else {
                        "associatedPullRequests": {
                            "nodes": [
                                {
                                    "number": 3,
                                    "mergedAt": "2026-10-22T00:00:00Z",
                                    "mergeCommit": {"oid": commit},
                                    "author": {"login": "alice", "__typename": "User"},
                                }
                            ]
                        }
                    }
                )
            }
        }
    }
    executable = tmp_path / "bin" / "gh"
    executable.parent.mkdir(exist_ok=True)
    executable.write_text(
        "#!/usr/bin/env bash\n"
        "[[ $1 == api && $2 == graphql && $3 == -F && $4 == query=@- ]] || exit 1\n"
        'cat >"$GH_QUERY_FILE"\n'
        'printf "%s" "$GH_TEST_RESPONSE"\n',
        encoding="utf-8",
    )
    executable.chmod(0o755)
    query = tmp_path / "query.graphql"
    monkeypatch.setenv("PATH", f"{executable.parent}:{os.environ['PATH']}")
    monkeypatch.setenv("GH_QUERY_FILE", str(query))
    monkeypatch.setenv("GH_TEST_RESPONSE", json.dumps(response))
    return query


def test_fragments_cli_rejects_numbered_prs_for_knope(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["release-creator", "fragments", "--format", "knope", "--numbered-prs", "--repository", "tox-dev/example"],
    )

    with pytest.raises(SystemExit, match="2"):
        main()

    assert "--numbered-prs applies only to Towncrier" in capsys.readouterr().err


def test_fragments_cli_rejects_unsupported_name(
    git_repository: tuple[Path, str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = git_repository[0] / "changelog.d"
    directory.mkdir()
    (directory / "topic.feature.md").write_text("Add a feature.\n")
    monkeypatch.setattr(sys, "argv", ["release-creator", "fragments", "--repository", "tox-dev/example"])

    with pytest.raises(SystemExit, match="2"):
        main()

    assert "unsupported changelog fragment name" in capsys.readouterr().err


def test_fragments_cli_reports_missing_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    (directory / "+topic.feature.md").write_text("Add a feature.\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["release-creator", "fragments", "--repository", "tox-dev/example"])

    with pytest.raises(SystemExit, match="2"):
        main()

    assert "not a git repository" in capsys.readouterr().err

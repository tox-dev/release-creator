"""Named fragment tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from release_creator.fragments.links import add_pull_request_links

if TYPE_CHECKING:
    from pathlib import Path


def test_add_pull_request_links_for_multiple_fragments(tmp_path: Path) -> None:
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    first = directory / "+first.feature.md"
    first.write_text("Add a feature by [@alice](https://github.com/alice).\n")
    second = directory / "+second.bugfix.md"
    second.write_text("Fix a bug.\n")

    add_pull_request_links(
        directory, "tox-dev/example", {first.name: "Add release notes (#42)", second.name: "Add release notes (#42)"}
    )

    assert first.read_text() == (
        "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n"
    )
    assert second.read_text() == "Fix a bug ([#42](https://github.com/tox-dev/example/pull/42)).\n"


def test_add_pull_request_links_removes_credit_comma(tmp_path: Path) -> None:
    fragment = tmp_path / "+fix.bugfix.md"
    fragment.write_text("Fix a bug, by [@alice](https://github.com/alice).\n")

    add_pull_request_links(tmp_path, "tox-dev/example", {fragment.name: "Fix a bug (#42)"})

    assert fragment.read_text() == (
        "Fix a bug ([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n"
    )


@pytest.mark.parametrize(
    ("repository_name", "subject", "content", "message"),
    [
        pytest.param("bad", "Add news (#42)", "Fix a bug.\n", "invalid repository", id="repository"),
        pytest.param("tox-dev/example", "Add news", "Fix a bug.\n", "no squash pull request number", id="commit"),
        pytest.param(
            "tox-dev/example",
            "Add news (#42)",
            "Fix a bug ([#42](https://github.com/tox-dev/example/pull/42)).\n",
            "already linked",
            id="existing-link",
        ),
    ],
)
def test_add_pull_request_links_rejects_invalid_input(
    tmp_path: Path, repository_name: str, subject: str, content: str, message: str
) -> None:
    directory = tmp_path / "changelog.d"
    directory.mkdir()
    (directory / "+fix.bugfix.md").write_text(content)

    with pytest.raises(ValueError, match=message):
        add_pull_request_links(directory, repository_name, {"+fix.bugfix.md": subject})

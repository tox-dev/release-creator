"""Named fragment tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from release_creator.fragments.links import add_pull_request_links
from release_creator.fragments.pull_requests import PullRequestAuthor

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("filename", "content", "authors", "expected"),
    [
        pytest.param(
            "+first.feature.md",
            "Add a feature by [@alice](https://github.com/alice).\n",
            {"42": PullRequestAuthor(handle="alice", is_bot=False)},
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@alice](https://github.com/alice).\n",
            id="markdown-credit",
        ),
        pytest.param(
            "+first.feature.md",
            "Add a feature, by [@alice](https://github.com/alice).\n",
            {"42": PullRequestAuthor(handle="alice", is_bot=False)},
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@alice](https://github.com/alice).\n",
            id="markdown-credit-with-comma",
        ),
        pytest.param(
            "+first.feature.md",
            "Add a feature.\n",
            {"42": PullRequestAuthor(handle="alice", is_bot=False)},
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@alice](https://github.com/alice).\n",
            id="markdown-resolved-author",
        ),
        pytest.param(
            "+first.feature.rst",
            "Add a feature.\n",
            {"42": PullRequestAuthor(handle="alice", is_bot=False)},
            "Add a feature (:pr:`42`) by :user:`alice`.\n",
            id="rst-resolved-author",
        ),
        pytest.param(
            "+first.feature.rst",
            "Add a feature by :user:`alice`.\n",
            {"42": PullRequestAuthor(handle="alice", is_bot=False)},
            "Add a feature (:pr:`42`) by :user:`alice`.\n",
            id="rst-credit",
        ),
        pytest.param(
            "+first.feature.rst",
            "Add a feature by `@alice <https://github.com/alice>`_.\n",
            {"42": PullRequestAuthor(handle="alice", is_bot=False)},
            "Add a feature (:pr:`42`) by `@alice <https://github.com/alice>`_.\n",
            id="rst-profile-credit",
        ),
        pytest.param(
            "+first.feature.rst",
            "Add a feature.\n",
            None,
            "Add a feature (:pr:`42`).\n",
            id="rst-without-author-resolution",
        ),
        pytest.param(
            "+first.feature.md",
            "Add a feature.\n",
            None,
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)).\n",
            id="without-author-resolution",
        ),
        pytest.param(
            "+first.feature.md",
            "Add a feature.\n",
            {"42": PullRequestAuthor(handle="dependabot", is_bot=True)},
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)).\n",
            id="bot-author",
        ),
        pytest.param(
            "42.feature.md",
            "Add a feature.\n",
            {"42": PullRequestAuthor(handle="alice", is_bot=False)},
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@alice](https://github.com/alice).\n",
            id="numbered-markdown-author",
        ),
        pytest.param(
            "42.feature.rst",
            "Add a feature.\n",
            {"42": PullRequestAuthor(handle="alice", is_bot=False)},
            "Add a feature (:pr:`42`) by :user:`alice`.\n",
            id="numbered-rst-author",
        ),
        pytest.param(
            "42.feature.md",
            "Add a feature.\n",
            {"42": PullRequestAuthor(handle="dependabot", is_bot=True)},
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)).\n",
            id="numbered-bot",
        ),
        pytest.param(
            "42.feature.md",
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)).\n",
            {"42": PullRequestAuthor(handle="alice", is_bot=False)},
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@alice](https://github.com/alice).\n",
            id="numbered-existing-link",
        ),
        pytest.param(
            "42.feature.md",
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@alice](https://github.com/alice).\n",
            {"42": PullRequestAuthor(handle="alice", is_bot=False)},
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@alice](https://github.com/alice).\n",
            id="numbered-existing-link-and-credit",
        ),
        pytest.param(
            "42.feature.md",
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)).\n",
            {"42": PullRequestAuthor(handle="dependabot", is_bot=True)},
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)).\n",
            id="numbered-existing-link-and-bot",
        ),
    ],
)
def test_add_pull_request_links(
    tmp_path: Path,
    filename: str,
    content: str,
    authors: dict[str, PullRequestAuthor] | None,
    expected: str,
) -> None:
    fragment = tmp_path / filename
    fragment.write_text(content)

    add_pull_request_links(tmp_path, "tox-dev/example", {filename: "Add release notes (#42)"}, authors)

    assert fragment.read_text() == expected


def test_add_pull_request_links_preserves_shared_credits(tmp_path: Path) -> None:
    fragment = tmp_path / "+first.feature.md"
    fragment.write_text("Add a feature by [@alice](https://github.com/alice) and [@bob](https://github.com/bob).\n")

    add_pull_request_links(
        tmp_path,
        "tox-dev/example",
        {fragment.name: "Add release notes (#42)"},
        {"42": PullRequestAuthor(handle="alice", is_bot=False)},
    )

    assert fragment.read_text() == (
        "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) by "
        "[@alice](https://github.com/alice) and [@bob](https://github.com/bob).\n"
    )


@pytest.mark.parametrize(
    ("heading", "author", "expected"),
    [
        pytest.param(
            "Remove a distrusted root certificate",
            PullRequestAuthor(handle="alice", is_bot=False),
            "Remove a distrusted root certificate ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@alice](https://github.com/alice)",
            id="human",
        ),
        pytest.param(
            "Remove a distrusted root certificate",
            PullRequestAuthor(handle="dependabot", is_bot=True),
            "Remove a distrusted root certificate ([#42](https://github.com/tox-dev/example/pull/42))",
            id="bot",
        ),
        pytest.param(
            "Remove a distrusted root certificate by [@alice](https://github.com/alice) "
            "and [@bob](https://github.com/bob)",
            PullRequestAuthor(handle="alice", is_bot=False),
            "Remove a distrusted root certificate ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@alice](https://github.com/alice) and [@bob](https://github.com/bob)",
            id="shared-credit",
        ),
    ],
)
def test_add_pull_request_links_knope(tmp_path: Path, heading: str, author: PullRequestAuthor, expected: str) -> None:
    fragment = tmp_path / "trust-roots.md"
    fragment.write_text(f"---\ndefault: security\n---\n\n# {heading}\n\nMore context.\n")
    (tmp_path / "README.md").write_text("Knope guide.\n")

    add_pull_request_links(
        tmp_path,
        "tox-dev/example",
        {fragment.name: "Patch trust roots (#42)"},
        {"42": author},
        knope=True,
    )

    assert fragment.read_text() == f"---\ndefault: security\n---\n\n# {expected}\n\nMore context.\n"


def test_add_pull_request_links_knope_is_repeatable(tmp_path: Path) -> None:
    fragment = tmp_path / "trust-roots.md"
    fragment.write_text("---\ndefault: security\n---\n\n# Remove a distrusted root certificate\n")

    for _ in range(2):
        add_pull_request_links(
            tmp_path,
            "tox-dev/example",
            {fragment.name: "Patch trust roots (#42)"},
            {"42": PullRequestAuthor(handle="alice", is_bot=False)},
            knope=True,
        )

    assert fragment.read_text() == (
        "---\ndefault: security\n---\n\n# Remove a distrusted root certificate "
        "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice)\n"
    )


@pytest.mark.parametrize(
    ("content", "message"),
    [
        pytest.param("# Missing front matter\n", "missing YAML front matter", id="front-matter"),
        pytest.param("---\ndefault: security\n---\n\nNot a heading\n", "missing level-one", id="heading"),
    ],
)
def test_add_pull_request_links_knope_rejects_invalid_changeset(tmp_path: Path, content: str, message: str) -> None:
    fragment = tmp_path / "trust-roots.md"
    fragment.write_text(content)

    with pytest.raises(ValueError, match=message):
        add_pull_request_links(tmp_path, "tox-dev/example", {fragment.name: "Patch trust roots (#42)"}, knope=True)

    assert fragment.read_text() == content


def test_add_pull_request_links_preserves_numbered_shared_credits(tmp_path: Path) -> None:
    fragment = tmp_path / "42.feature.md"
    fragment.write_text("Add a feature by [@alice](https://github.com/alice).\n")

    add_pull_request_links(
        tmp_path,
        "tox-dev/example",
        {fragment.name: "Add a feature (#42)"},
        {"42": PullRequestAuthor(handle="alice", is_bot=False)},
    )

    assert fragment.read_text() == (
        "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n"
    )


@pytest.mark.parametrize("second_name", ["+second.feature.md", "43.feature.md"])
def test_add_pull_request_links_rejects_a_mismatched_author_without_partial_writes(
    tmp_path: Path, second_name: str
) -> None:
    first = tmp_path / "+first.feature.md"
    first.write_text("Add a feature.\n")
    second = tmp_path / second_name
    second.write_text("Fix a bug by [@bob](https://github.com/bob).\n")

    with pytest.raises(ValueError, match="pull request author @alice is missing"):
        add_pull_request_links(
            tmp_path,
            "tox-dev/example",
            {first.name: "Add release notes (#42)", second.name: "Add release notes (#43)"},
            {
                "42": PullRequestAuthor(handle="alice", is_bot=False),
                "43": PullRequestAuthor(handle="alice", is_bot=False),
            },
        )

    assert first.read_text() == "Add a feature.\n"
    assert second.read_text() == "Fix a bug by [@bob](https://github.com/bob).\n"


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            (
                "bad",
                "Add news (#42)",
                "Fix a bug.\n",
                {"42": PullRequestAuthor(handle="alice", is_bot=False)},
                "invalid repository",
            ),
            id="repository",
        ),
        pytest.param(
            (
                "tox-dev/example",
                "Add news",
                "Fix a bug.\n",
                {"42": PullRequestAuthor(handle="alice", is_bot=False)},
                "no squash pull request number",
            ),
            id="commit",
        ),
        pytest.param(
            (
                "tox-dev/example",
                "Add news (#42)",
                "Fix a bug ([#42](https://github.com/tox-dev/example/pull/42)).\n",
                {"42": PullRequestAuthor(handle="alice", is_bot=False)},
                "already linked",
            ),
            id="existing-markdown-link",
        ),
        pytest.param(
            (
                "tox-dev/example",
                "Add news (#42)",
                "Fix a bug (:pr:`42`).\n",
                {"42": PullRequestAuthor(handle="alice", is_bot=False)},
                "already linked",
            ),
            id="existing-rst-link",
        ),
        pytest.param(("tox-dev/example", "Add news (#42)", "Fix a bug.\n", {}, "no author data"), id="missing-author"),
    ],
)
def test_add_pull_request_links_rejects_invalid_input(
    tmp_path: Path, case: tuple[str, str, str, dict[str, PullRequestAuthor], str]
) -> None:
    repository, subject, content, authors, message = case
    fragment = tmp_path / "+fix.bugfix.md"
    fragment.write_text(content)

    with pytest.raises(ValueError, match=message):
        add_pull_request_links(tmp_path, repository, {fragment.name: subject}, authors)


def test_add_pull_request_links_rejects_bot_credits(tmp_path: Path) -> None:
    fragment = tmp_path / "+fix.bugfix.md"
    fragment.write_text("Fix a bug by [@dependabot](https://github.com/dependabot).\n")

    with pytest.raises(ValueError, match="bot author @dependabot must not be credited"):
        add_pull_request_links(
            tmp_path,
            "tox-dev/example",
            {fragment.name: "Automate updates (#42)"},
            {"42": PullRequestAuthor(handle="dependabot", is_bot=True)},
        )

"""Named fragment tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import pytest

from release_creator.fragments.links import add_pull_request_links
from release_creator.fragments.pull_requests import PullRequest, PullRequestAuthor

if TYPE_CHECKING:
    from pathlib import Path


def _link(
    directory: Path,
    repository: str,
    subjects: dict[str, str],
    authors: dict[str, PullRequestAuthor] | None = None,
    *,
    mode: Literal["towncrier", "knope"] = "towncrier",
) -> None:
    pull_requests: dict[str, PullRequest] = {}
    for name, subject in subjects.items():
        if "#" not in subject:
            continue
        number = subject.rpartition("#")[2].removesuffix(")")
        if authors is not None and number not in authors:
            continue
        pull_requests[name] = PullRequest(
            number=number,
            author=authors[number] if authors is not None else PullRequestAuthor(handle="alice", is_bot=False),
        )
    add_pull_request_links(directory, repository, pull_requests, mode=mode)


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

    _link(tmp_path, "tox-dev/example", {filename: "Add release notes (#42)"}, authors)

    assert fragment.read_text() == expected


def test_add_pull_request_links_preserves_shared_credits(tmp_path: Path) -> None:
    fragment = tmp_path / "+first.feature.md"
    fragment.write_text("Add a feature by [@alice](https://github.com/alice) and [@bob](https://github.com/bob).\n")

    _link(
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
    ("extension", "code"),
    [
        pytest.param("md", "```sh\necho yes\n```", id="markdown-fence"),
        pytest.param("md", "```sh\necho yes\n````", id="markdown-longer-closing-fence"),
        pytest.param("md", "    echo yes", id="markdown-indented"),
        pytest.param("rst", ".. code-block:: sh\n\n  echo yes", id="rst-directive"),
        pytest.param("rst", ".. code-block:: cpp\n\n  using std::", id="rst-indented-colons"),
        pytest.param("rst", ".. code-block:: haskell\n\n  f :: Int", id="rst-indented-type"),
        pytest.param("rst", ".. code-block:: text\n\n  Example::", id="rst-indented-literal"),
        pytest.param("rst", ".. code:: sh\n\n  echo yes", id="rst-code-directive"),
        pytest.param("rst", ".. sourcecode:: sh\n\n  echo yes", id="rst-sourcecode-directive"),
        pytest.param("rst", "Example::\n\n  echo yes", id="rst-literal"),
    ],
)
def test_add_pull_request_links_before_trailing_code(tmp_path: Path, extension: str, code: str) -> None:
    fragment = tmp_path / f"+first.feature.{extension}"
    fragment.write_text(f"Add a feature.\n\n{code}\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    link = (
        "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice)"
        if extension == "md"
        else "(:pr:`42`) by :user:`alice`"
    )
    assert fragment.read_text() == f"Add a feature {link}.\n\n{code}\n"


@pytest.mark.parametrize(
    ("extension", "code", "link"),
    [
        pytest.param(
            "md",
            "```text\nhttps://github.com/tox-dev/example/pull/42\n```",
            "([#42](https://github.com/tox-dev/example/pull/42))",
            id="markdown-fence",
        ),
        pytest.param("rst", ".. code-block:: text\n\n  :pr:`42`", "(:pr:`42`)", id="rst-code-block"),
        pytest.param(
            "rst",
            ".. code-block:: text\n  :caption: https://github.com/tox-dev/example/pull/42\n\n  sample",
            "(:pr:`42`)",
            id="rst-directive-option",
        ),
    ],
)
def test_add_pull_request_links_ignores_reference_in_code(tmp_path: Path, extension: str, code: str, link: str) -> None:
    fragment = tmp_path / f"42.feature.{extension}"
    fragment.write_text(f"Document this example.\n\n{code}\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Document this example (#42)"})

    result = fragment.read_text()
    assert result.startswith(f"Document this example {link} by ")
    assert result.endswith(f"\n\n{code}\n")


@pytest.mark.parametrize(
    ("extension", "literal", "link"),
    [
        pytest.param(
            "md",
            "`https://github.com/tox-dev/example/pull/42`",
            "([#42](https://github.com/tox-dev/example/pull/42))",
            id="markdown",
        ),
        pytest.param(
            "rst",
            "``https://github.com/tox-dev/example/pull/42``",
            "(:pr:`42`)",
            id="rst",
        ),
    ],
)
def test_add_pull_request_links_ignores_inline_code_reference(
    tmp_path: Path, extension: str, literal: str, link: str
) -> None:
    fragment = tmp_path / f"42.feature.{extension}"
    fragment.write_text(f"Document {literal} behavior.\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Document this example (#42)"})

    assert fragment.read_text().startswith(f"Document {literal} behavior {link} by ")


def test_add_pull_request_links_recognizes_reference_after_unclosed_rst_literal(tmp_path: Path) -> None:
    fragment = tmp_path / "42.feature.rst"
    source = "Document malformed ``literal and :pr:`42`.\n"
    fragment.write_text(source)

    _link(tmp_path, "tox-dev/example", {fragment.name: "Document this example (#42)"})

    assert fragment.read_text() == "Document malformed ``literal and :pr:`42` by :user:`alice`.\n"


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(".. code-block:: python\n\n      print(1)", id="nested-directive"),
        pytest.param(".. code-block:: cpp\n\n      using std::\n        continuation", id="nested-colons"),
    ],
)
def test_add_pull_request_links_to_list_item_before_nested_code(tmp_path: Path, code: str) -> None:
    fragment = tmp_path / "+first.feature.rst"
    fragment.write_text(f"- Item\n\n  {code}\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == f"- Item (:pr:`42`) by :user:`alice`.\n\n  {code}\n"


def test_add_pull_request_links_after_nonindented_rst_literal_marker(tmp_path: Path) -> None:
    fragment = tmp_path / "+first.feature.rst"
    fragment.write_text("Example::\n\nA new feature.\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == "Example::\n\nA new feature (:pr:`42`) by :user:`alice`.\n"


def test_add_pull_request_links_after_earlier_fence_before_final_fence(tmp_path: Path) -> None:
    fragment = tmp_path / "+first.feature.md"
    fragment.write_text("Example.\n\n```sh\nfirst\n```\n\nMore details.\n\n```sh\nsecond\n```\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        "Example.\n\n```sh\nfirst\n```\n\n"
        "More details ([#42](https://github.com/tox-dev/example/pull/42)) "
        "by [@alice](https://github.com/alice).\n\n```sh\nsecond\n```\n"
    )


@pytest.mark.parametrize(
    ("extension", "code"),
    [
        pytest.param("md", "```sh\necho yes\n```", id="markdown-fence"),
        pytest.param("md", "```sh\necho yes\n````", id="markdown-longer-closing-fence"),
        pytest.param("md", "````sh\n```\necho yes\n````", id="markdown-long-fence"),
        pytest.param("rst", ".. code:: sh\n\n  echo yes", id="rst-directive"),
        pytest.param("md", "    echo yes", id="markdown-indented"),
    ],
)
def test_add_pull_request_links_after_code_only(tmp_path: Path, extension: str, code: str) -> None:
    fragment = tmp_path / f"+first.feature.{extension}"
    fragment.write_text(f"{code}\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    link = (
        "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice)"
        if extension == "md"
        else "(:pr:`42`) by :user:`alice`"
    )
    assert fragment.read_text() == f"{code}\n\n{link}.\n"


def test_add_pull_request_links_after_bot_code_only(tmp_path: Path) -> None:
    fragment = tmp_path / "+first.feature.md"
    fragment.write_text("```sh\necho yes\n```\n")

    _link(
        tmp_path,
        "tox-dev/example",
        {fragment.name: "Add release notes (#42)"},
        {"42": PullRequestAuthor(handle="dependabot", is_bot=True)},
    )

    assert fragment.read_text() == ("```sh\necho yes\n```\n\n([#42](https://github.com/tox-dev/example/pull/42)).\n")


@pytest.mark.parametrize(
    "ending",
    [pytest.param("```unfinished", id="text-after-fence"), pytest.param("```", id="unmatched-fence")],
)
def test_add_pull_request_links_rejects_unmatched_fence(tmp_path: Path, ending: str) -> None:
    fragment = tmp_path / "+first.feature.md"
    content = f"Add a feature.\n\n{ending}\n"
    fragment.write_text(content)

    with pytest.raises(ValueError, match="unclosed Markdown code fence"):
        _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == content


def test_add_pull_request_links_ignores_indented_fence_inside_code(tmp_path: Path) -> None:
    fragment = tmp_path / "+first.feature.md"
    fragment.write_text("Add a feature.\n\n```text\n    ```\nexample\n```\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) "
        "by [@alice](https://github.com/alice).\n\n```text\n    ```\nexample\n```\n"
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

    _link(
        tmp_path,
        "tox-dev/example",
        {fragment.name: "Patch trust roots (#42)"},
        {"42": author},
        mode="knope",
    )

    assert fragment.read_text() == f"---\ndefault: security\n---\n\n# {expected}\n\nMore context.\n"


def test_add_pull_request_links_knope_is_repeatable(tmp_path: Path) -> None:
    fragment = tmp_path / "trust-roots.md"
    fragment.write_text("---\ndefault: security\n---\n\n# Remove a distrusted root certificate\n")

    for _ in range(2):
        _link(
            tmp_path,
            "tox-dev/example",
            {fragment.name: "Patch trust roots (#42)"},
            {"42": PullRequestAuthor(handle="alice", is_bot=False)},
            mode="knope",
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
        _link(tmp_path, "tox-dev/example", {fragment.name: "Patch trust roots (#42)"}, mode="knope")

    assert fragment.read_text() == content


def test_add_pull_request_links_preserves_numbered_shared_credits(tmp_path: Path) -> None:
    fragment = tmp_path / "42.feature.md"
    fragment.write_text("Add a feature by [@alice](https://github.com/alice).\n")

    _link(
        tmp_path,
        "tox-dev/example",
        {fragment.name: "Add a feature (#42)"},
        {"42": PullRequestAuthor(handle="alice", is_bot=False)},
    )

    assert fragment.read_text() == (
        "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n"
    )


def test_add_pull_request_links_matches_credit_case(tmp_path: Path) -> None:
    fragment = tmp_path / "42.feature.md"
    fragment.write_text("Add a feature by [@Alice](https://github.com/Alice).\n")

    _link(
        tmp_path,
        "tox-dev/example",
        {fragment.name: "Add a feature (#42)"},
        {"42": PullRequestAuthor(handle="alice", is_bot=False)},
    )

    assert fragment.read_text() == (
        "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) by [@Alice](https://github.com/Alice).\n"
    )


def test_add_pull_request_links_reports_deleted_author_credit(tmp_path: Path) -> None:
    fragment = tmp_path / "42.feature.md"
    fragment.write_text("Add a feature by [@alice](https://github.com/alice).\n")

    with pytest.raises(ValueError, match="cannot verify explicit credit for deleted pull request author"):
        _link(
            tmp_path,
            "tox-dev/example",
            {fragment.name: "Add a feature (#42)"},
            {"42": PullRequestAuthor(handle="ghost", is_bot=False)},
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
        _link(
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
                "tox-dev/example",
                "Add news",
                "Fix a bug.\n",
                {"42": PullRequestAuthor(handle="alice", is_bot=False)},
                "no pull request data",
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
        pytest.param(
            ("tox-dev/example", "Add news (#42)", "Fix a bug.\n", {}, "no pull request data"), id="missing-author"
        ),
    ],
)
def test_add_pull_request_links_rejects_invalid_input(
    tmp_path: Path, case: tuple[str, str, str, dict[str, PullRequestAuthor], str]
) -> None:
    repository, subject, content, authors, message = case
    fragment = tmp_path / "+fix.bugfix.md"
    fragment.write_text(content)

    with pytest.raises(ValueError, match=message):
        _link(tmp_path, repository, {fragment.name: subject}, authors)


def test_add_pull_request_links_rejects_bot_credits(tmp_path: Path) -> None:
    fragment = tmp_path / "+fix.bugfix.md"
    fragment.write_text("Fix a bug by [@dependabot](https://github.com/dependabot).\n")

    with pytest.raises(ValueError, match="bot author @dependabot must not be credited"):
        _link(
            tmp_path,
            "tox-dev/example",
            {fragment.name: "Automate updates (#42)"},
            {"42": PullRequestAuthor(handle="dependabot", is_bot=True)},
        )

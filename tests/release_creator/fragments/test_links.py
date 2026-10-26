"""Named fragment tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal

import pytest
from docutils.core import publish_doctree
from markdown_it import MarkdownIt

from release_creator.fragments.git import FragmentCommit
from release_creator.fragments.links import add_pull_request_links
from release_creator.fragments.pull_requests import PullRequest, PullRequestAuthor, PullRequestCredit
from release_creator.notes.rst import register_roles

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
        number = subject.rpartition("#")[2].removesuffix(")")
        author = authors[number] if authors is not None else PullRequestAuthor(handle="alice", is_bot=False)
        pull_requests[name] = PullRequest(number=number, credits=(PullRequestCredit(name=author.handle, linked=True),))
    add_pull_request_links(directory, repository, pull_requests, commits={}, mode=mode)


@pytest.mark.parametrize(
    ("filename", "content", "authors", "expected"),
    [
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
            "+first.feature.md",
            "Add a feature.\n",
            {"42": PullRequestAuthor(handle="dependabot", is_bot=True)},
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@dependabot](https://github.com/dependabot).\n",
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
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@dependabot](https://github.com/dependabot).\n",
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
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)).\n",
            {"42": PullRequestAuthor(handle="dependabot", is_bot=True)},
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@dependabot](https://github.com/dependabot).\n",
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


@pytest.mark.parametrize(
    "label", [pytest.param("![@alice](https://example.com/a.png)", id="image"), pytest.param("", id="empty")]
)
def test_add_pull_request_links_ignores_nontext_profile_label(tmp_path: Path, label: str) -> None:
    fragment = tmp_path / "+first.feature.md"
    fragment.write_text(f"Add a feature by [{label}](https://github.com/alice).\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        f"Add a feature by [{label}](https://github.com/alice) "
        "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n"
    )


@pytest.mark.parametrize(
    "credit",
    [
        pytest.param(r"\[@alice](https://github.com/alice)", id="escaped-label"),
        pytest.param(r"[@alice]\(https://github.com/alice)", id="escaped-target"),
    ],
)
def test_add_pull_request_links_requires_rendered_author_link(tmp_path: Path, credit: str) -> None:
    fragment = tmp_path / "+first.feature.md"
    fragment.write_text(f"Add a feature by {credit}.\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        f"Add a feature by {credit} "
        "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n"
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


def test_add_pull_request_links_after_earlier_fence_before_final_fence(tmp_path: Path) -> None:
    fragment = tmp_path / "+first.feature.md"
    fragment.write_text("Example.\n\n```sh\nfirst\n```\n\nMore details.\n\n```sh\nsecond\n```\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        "Example.\n\n```sh\nfirst\n```\n\n"
        "More details ([#42](https://github.com/tox-dev/example/pull/42)) "
        "by [@alice](https://github.com/alice).\n\n```sh\nsecond\n```\n"
    )


def test_add_pull_request_links_after_earlier_fence_and_final_prose(tmp_path: Path) -> None:
    fragment = tmp_path / "+first.feature.md"
    fragment.write_text("Example.\n\n```sh\nfirst\n```\n\nMore details.\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        "Example.\n\n```sh\nfirst\n```\n\nMore details "
        "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n"
    )


def test_add_pull_request_links_ignores_other_fence_inside_trailing_code(tmp_path: Path) -> None:
    fragment = tmp_path / "+first.feature.md"
    fragment.write_text("Example.\n\n```sh\necho ~~~\n~~~\n```\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        "Example ([#42](https://github.com/tox-dev/example/pull/42)) "
        "by [@alice](https://github.com/alice).\n\n```sh\necho ~~~\n~~~\n```\n"
    )


@pytest.mark.parametrize(
    "ending",
    [pytest.param("```unfinished", id="text-after-fence"), pytest.param("```", id="unmatched-fence")],
)
def test_add_pull_request_links_after_unmatched_fence(tmp_path: Path, ending: str) -> None:
    fragment = tmp_path / "+first.feature.md"
    fragment.write_text(f"Add a feature.\n\n{ending}\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) "
        f"by [@alice](https://github.com/alice).\n\n{ending}\n"
    )


def test_add_pull_request_links_ignores_indented_fence_inside_code(tmp_path: Path) -> None:
    fragment = tmp_path / "+first.feature.md"
    fragment.write_text("Add a feature.\n\n```text\n    ```\nexample\n```\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) "
        "by [@alice](https://github.com/alice).\n\n```text\n    ```\nexample\n```\n"
    )


@pytest.mark.parametrize(
    ("extension", "content", "expected"),
    [
        pytest.param(
            "md",
            "Add a feature.\n\n```sh\nrun this by [@bob](https://github.com/bob)\n```\n",
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@alice](https://github.com/alice).\n\n```sh\nrun this by [@bob](https://github.com/bob)\n```\n",
            id="markdown-fence",
        ),
        pytest.param(
            "md",
            "Add a feature using `by [@bob](https://github.com/bob)`.\n",
            "Add a feature using `by [@bob](https://github.com/bob)` "
            "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n",
            id="markdown-inline",
        ),
        pytest.param(
            "md",
            "Add a feature using `a `` by [@bob](https://github.com/bob) b` literal.\n",
            "Add a feature using `a `` by [@bob](https://github.com/bob) b` literal "
            "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n",
            id="markdown-longer-inner-backticks",
        ),
        pytest.param(
            "md",
            "Add a feature <!-- by [@alice](https://github.com/alice) --> safely.\n",
            "Add a feature <!-- by [@alice](https://github.com/alice) --> safely "
            "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n",
            id="markdown-comment",
        ),
        pytest.param(
            "rst",
            "Add a feature.\n\n.. code-block:: sh\n\n  run this by :user:`bob`\n",
            "Add a feature (:pr:`42`) by :user:`alice`.\n\n.. code-block:: sh\n\n  run this by :user:`bob`\n",
            id="rst-directive",
        ),
        pytest.param(
            "rst",
            "Add a feature::\n\n  run this by :user:`bob`\n",
            "Add a feature (:pr:`42`) by :user:`alice`::\n\n  run this by :user:`bob`\n",
            id="rst-literal-block",
        ),
        pytest.param(
            "rst",
            "Add a feature using ``by :user:`bob``` safely.\n",
            "Add a feature using ``by :user:`bob``` safely (:pr:`42`) by :user:`alice`.\n",
            id="rst-inline",
        ),
    ],
)
def test_add_pull_request_links_ignores_credit_inside_code(
    tmp_path: Path, extension: str, content: str, expected: str
) -> None:
    fragment = tmp_path / f"+first.feature.{extension}"
    fragment.write_text(content)

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == expected


def test_add_pull_request_links_ignores_reference_in_html_comment(tmp_path: Path) -> None:
    fragment = tmp_path / "+first.feature.md"
    fragment.write_text("Add parser <!-- https://github.com/tox-dev/example/pull/42 --> support.\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        "Add parser <!-- https://github.com/tox-dev/example/pull/42 --> support "
        "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n"
    )


def test_add_pull_request_links_keeps_prose_after_rst_literal(tmp_path: Path) -> None:
    fragment = tmp_path / "+first.feature.rst"
    fragment.write_text("Add a feature::\n\n  code output\n\nContinue here.\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == ("Add a feature::\n\n  code output\n\nContinue here (:pr:`42`) by :user:`alice`.\n")


@pytest.mark.parametrize(
    "hidden",
    [
        pytest.param('[docs](https://example.com "x by [@alice](https://github.com/alice)")', id="link-title"),
        pytest.param('[docs](https://example.com "x &#98;y [@alice](https://github.com/alice)")', id="encoded-title"),
        pytest.param('[docs](https://example.com/path(x) "x by [@alice](https://github.com/alice)")', id="nested-url"),
        pytest.param("[docs](https://example.com/path\\) 'x by [@alice](https://github.com/alice)')", id="escaped-url"),
        pytest.param(
            '[docs](https://example.com/foo\'bar "x by [@alice](https://github.com/alice)")', id="apostrophe-url"
        ),
        pytest.param('[docs](https://example.com/foo"bar "x by [@alice](https://github.com/alice)")', id="quote-url"),
        pytest.param(
            '[docs](<https://example.com/foo\'bar> "x by [@alice](https://github.com/alice)")', id="angle-url"
        ),
        pytest.param('<span title="x by [@alice](https://github.com/alice)">docs</span>', id="html-attribute"),
        pytest.param("<code>by [@alice](https://github.com/alice)</code>", id="html-code"),
        pytest.param('<code title="x > y">by [@mallory](https://github.com/mallory)</code>', id="html-quoted-tag"),
        *[
            pytest.param(f"<{tag}>by [@mallory](https://github.com/mallory)</{tag}>", id=f"html-{tag}")
            for tag in ("kbd", "pre", "samp", "script", "style", "textarea", "template", "noscript")
        ],
    ],
)
def test_add_pull_request_links_ignores_hidden_markdown_credit(tmp_path: Path, hidden: str) -> None:
    fragment = tmp_path / "+first.feature.md"
    fragment.write_text(f"Add {hidden}.\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        f"Add {hidden} ([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n"
    )


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            'Add `<span title="x by [@alice](https://github.com/alice)">` then '
            '<span title="x by [@alice](https://github.com/alice)">docs</span>.\n',
            id="earlier-inline-code",
        ),
        pytest.param(
            "Show example:\n\n```html\n<code>foo</code>\n```\n\n"
            "Add parser <code> by [@alice](https://github.com/alice)</code>.\n",
            id="earlier-fence",
        ),
    ],
)
def test_add_pull_request_links_ignores_repeated_html_inside_code(tmp_path: Path, source: str) -> None:
    fragment = tmp_path / "+first.feature.md"
    fragment.write_text(source)

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        f"{source.rstrip().removesuffix('.')} "
        "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n"
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "Add parser ![ by [@alice](https://github.com/alice)](image.png).\n",
            "Add parser ![ by [@alice](https://github.com/alice)](image.png) "
            "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n",
            id="leading-space",
        ),
        pytest.param(
            "Add ![x by [@alice](https://github.com/alice)](https://example.com/image.png) feature.\n",
            "Add ![x by [@alice](https://github.com/alice)](https://example.com/image.png) feature "
            "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n",
            id="inline",
        ),
        pytest.param(
            "Add ![x by [@alice](https://github.com/alice)][image] feature.\n\n"
            "[image]: https://example.com/image.png\n",
            "Add ![x by [@alice](https://github.com/alice)][image] feature "
            "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n\n"
            "[image]: https://example.com/image.png\n",
            id="reference",
        ),
        pytest.param(
            "Add ![`code` by [@alice](https://github.com/alice)](image.png) feature.\n",
            "Add ![`code` by [@alice](https://github.com/alice)](image.png) feature "
            "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n",
            id="inline-code",
        ),
        pytest.param(
            'Add [docs](https://example.com "![x by [@alice](https://github.com/alice)](image.png)") '
            "then ![x by [@alice](https://github.com/alice)](image.png) feature.\n",
            'Add [docs](https://example.com "![x by [@alice](https://github.com/alice)](image.png)") '
            "then ![x by [@alice](https://github.com/alice)](image.png) feature "
            "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n",
            id="repeated-in-link-title",
        ),
    ],
)
def test_add_pull_request_links_ignores_image_alt_credit(tmp_path: Path, source: str, expected: str) -> None:
    fragment = tmp_path / "+first.feature.md"
    fragment.write_text(source)

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == expected


@pytest.mark.parametrize(
    "earlier",
    [
        pytest.param("`![x](image.png)`", id="code"),
        pytest.param('[docs](https://example.com "![x](image.png)")', id="link-title"),
        pytest.param('<span title="![x](image.png)">docs</span>', id="html-attribute"),
        pytest.param("<!-- ![x](image.png) -->", id="comment"),
        pytest.param("![![x](image.png)](other.png)", id="image-alt"),
        pytest.param("\\![x](image.png)", id="escaped-image"),
        pytest.param("![x]", id="plain-image-label"),
    ],
)
def test_add_pull_request_links_maps_image_after_similar_text(tmp_path: Path, earlier: str) -> None:
    fragment = tmp_path / "+first.feature.md"
    fragment.write_text(f"Add {earlier} then ![x](image.png) feature.\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        f"Add {earlier} then ![x](image.png) feature "
        "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n"
    )


def test_add_pull_request_links_maps_repeated_images(tmp_path: Path) -> None:
    fragment = tmp_path / "+first.feature.md"
    fragment.write_text("Add ![x](image.png) and ![x](image.png) feature.\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        "Add ![x](image.png) and ![x](image.png) feature "
        "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n"
    )


@pytest.mark.parametrize("tag", [pytest.param("code", id="code"), pytest.param("span", id="span")])
def test_add_pull_request_links_ignores_html_tag_in_image_alt(tmp_path: Path, tag: str) -> None:
    fragment = tmp_path / "+first.feature.md"
    source = f"Add <{tag}>foo</{tag}> and ![example <{tag}> text](image.png) feature.\n"
    fragment.write_text(source)

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        f"Add <{tag}>foo</{tag}> and ![example <{tag}> text](image.png) feature "
        "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n"
    )


def test_add_pull_request_links_ignores_nested_link_title_credit(tmp_path: Path) -> None:
    fragment = tmp_path / "+first.feature.md"
    source = 'Add [see [a] more](https://example.com "x by [@alice](https://github.com/alice)") now.\n'
    fragment.write_text(source)

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        'Add [see [a] more](https://example.com "x by [@alice](https://github.com/alice)") now '
        "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n"
    )


def test_add_pull_request_links_ignores_reference_definition_title(tmp_path: Path) -> None:
    fragment = tmp_path / "+first.feature.md"
    definition = '[d]: https://example.com "by [@bob](https://github.com/bob)"'
    fragment.write_text(f"Add [docs][d].\n\n{definition}\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        "Add [docs][d] ([#42](https://github.com/tox-dev/example/pull/42)) "
        f"by [@alice](https://github.com/alice).\n\n{definition}\n"
    )


@pytest.mark.parametrize(
    "tag",
    [
        pytest.param("code", id="code"),
        pytest.param("kbd", id="kbd"),
        pytest.param("pre", id="pre"),
        pytest.param("samp", id="samp"),
        pytest.param("script", id="script"),
        pytest.param("style", id="style"),
        pytest.param("textarea", id="textarea"),
        pytest.param("template", id="template"),
        pytest.param("noscript", id="noscript"),
    ],
)
def test_add_pull_request_links_ignores_html_literal_reference(tmp_path: Path, tag: str) -> None:
    fragment = tmp_path / "+first.feature.md"
    fragment.write_text(f"Add <{tag}>https://github.com/tox-dev/example/pull/42</{tag}> support.\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        f"Add <{tag}>https://github.com/tox-dev/example/pull/42</{tag}> support "
        "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n"
    )


def test_add_pull_request_links_ignores_reference_in_quoted_html_tag(tmp_path: Path) -> None:
    fragment = tmp_path / "42.feature.md"
    source = '<code title="x > y">https://github.com/tox-dev/example/pull/42</code>'
    fragment.write_text(f"Add {source} support.\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        f"Add {source} support ([#42](https://github.com/tox-dev/example/pull/42)) "
        "by [@alice](https://github.com/alice).\n"
    )


@pytest.mark.parametrize(
    "tag",
    [pytest.param("code", id="code"), pytest.param("kbd", id="kbd"), pytest.param("pre", id="pre")],
)
def test_add_pull_request_links_rejects_self_closing_literal(tmp_path: Path, tag: str) -> None:
    fragment = tmp_path / "+first.feature.md"
    source = f'Add <{tag} title="x > y"/> by [@mallory](https://github.com/mallory).\n'
    fragment.write_text(source)

    with pytest.raises(ValueError, match="self-closing HTML literal elements are unsupported"):
        _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == source


@pytest.mark.parametrize(
    "opening",
    [
        pytest.param("<code>", id="code"),
        pytest.param("<kbd>", id="kbd"),
        pytest.param("<code><kbd>", id="nested"),
        pytest.param('<CoDe TiTlE="x > y">', id="mixed-case-quoted-attribute"),
    ],
)
def test_add_pull_request_links_rejects_unclosed_html_literal(tmp_path: Path, opening: str) -> None:
    fragment = tmp_path / "+first.feature.md"
    source = f"Add {opening}by [@mallory](https://github.com/mallory).\n"
    fragment.write_text(source)

    with pytest.raises(ValueError, match="unclosed HTML literal element"):
        _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == source


def test_add_pull_request_links_rejects_crossed_html_literals(tmp_path: Path) -> None:
    fragment = tmp_path / "+first.feature.md"
    source = "Add <code><kbd>by [@mallory](https://github.com/mallory)</code></kbd> support.\n"
    fragment.write_text(source)

    with pytest.raises(ValueError, match="mismatched HTML literal elements"):
        _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == source


def test_add_pull_request_links_accepts_balanced_nested_html_literals(tmp_path: Path) -> None:
    fragment = tmp_path / "+first.feature.md"
    fragment.write_text("Add <code><kbd>sample</kbd></code> support.\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        "Add <code><kbd>sample</kbd></code> support "
        "([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n"
    )


def test_add_pull_request_links_adds_visible_link_beside_empty_html_anchor(tmp_path: Path) -> None:
    anchor = '<a href="https://github.com/tox-dev/example/pull/42"></a>'
    fragment = tmp_path / "42.feature.md"
    fragment.write_text(f"Add parser ({anchor}).\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == (
        f"Add parser ({anchor}) ([#42](https://github.com/tox-dev/example/pull/42)) "
        "by [@alice](https://github.com/alice).\n"
    )


@pytest.mark.parametrize(
    "anchor",
    [
        pytest.param('<a href="https://github.com/tox-dev/example/pull/42">#42</a>', id="labeled"),
        pytest.param('<a href="https://github.com/tox-dev/example/pull/42" style="display:none">#42</a>', id="hidden"),
    ],
)
def test_add_pull_request_links_treats_html_anchor_label_as_bare_reference(tmp_path: Path, anchor: str) -> None:
    fragment = tmp_path / "42.feature.md"
    fragment.write_text(f"Add parser ({anchor}).\n")

    _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == f"Add parser ({anchor}) by [@alice](https://github.com/alice).\n"


def test_add_pull_request_links_rejects_unmatched_html_close(tmp_path: Path) -> None:
    fragment = tmp_path / "42.feature.md"
    link = "[#42](https://github.com/tox-dev/example/pull/42)"
    source = f"Add parser </code> ({link}).\n"
    fragment.write_text(source)

    with pytest.raises(ValueError, match="mismatched HTML literal elements"):
        _link(tmp_path, "tox-dev/example", {fragment.name: "Add release notes (#42)"})

    assert fragment.read_text() == source


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
            "Remove a distrusted root certificate ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@dependabot](https://github.com/dependabot)",
            id="bot",
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


@pytest.mark.parametrize(
    ("filename", "content", "expected"),
    [
        pytest.param(
            "+fix.bugfix.md",
            "Fix a bug by [@bob](https://github.com/bob).\n",
            "Fix a bug by [@bob](https://github.com/bob) ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@alice](https://github.com/alice).\n",
            id="hand-written-credit",
        ),
        pytest.param(
            "+fix.bugfix.rst",
            "Fix a bug (:pr:`42`).\n",
            "Fix a bug (:pr:`42`) by :user:`alice`.\n",
            id="named-already-linked",
        ),
        pytest.param(
            "+fix.bugfix.md",
            "- Fix a bug.\n",
            "- Fix a bug ([#42](https://github.com/tox-dev/example/pull/42)) by [@alice](https://github.com/alice).\n",
            id="structured",
        ),
    ],
)
def test_add_pull_request_links_appends_link_and_credit_as_written(
    tmp_path: Path, filename: str, content: str, expected: str
) -> None:
    fragment = tmp_path / filename
    fragment.write_text(content)

    _link(tmp_path, "tox-dev/example", {filename: "Fix a bug (#42)"})

    assert fragment.read_text() == expected


@pytest.mark.parametrize(
    "commits",
    [
        pytest.param({}, id="no-commit"),
        pytest.param({"+fix.bugfix.md": FragmentCommit(sha="a" * 40, credits=())}, id="uncredited-author"),
    ],
)
def test_add_pull_request_links_leaves_fragment_without_pull_request_or_credit(
    tmp_path: Path, commits: dict[str, FragmentCommit]
) -> None:
    fragment = tmp_path / "+fix.bugfix.md"
    fragment.write_text("Fix a bug.\n")

    add_pull_request_links(tmp_path, "tox-dev/example", {}, commits=commits)

    assert fragment.read_text() == "Fix a bug.\n"


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        pytest.param(
            ("+fix.bugfix.md", "Fix a bug.\n", PullRequestCredit(name="alice", linked=True), "towncrier"),
            "Fix a bug by [@alice](https://github.com/alice).\n",
            id="markdown-login",
        ),
        pytest.param(
            ("+fix.bugfix.rst", "Fix a bug.\n", PullRequestCredit(name="alice", linked=True), "towncrier"),
            "Fix a bug by :user:`alice`.\n",
            id="rst-login",
        ),
        pytest.param(
            ("+fix.bugfix.md", "Fix a bug.\n", PullRequestCredit(name="Alice Doe", linked=False), "towncrier"),
            "Fix a bug by Alice Doe.\n",
            id="markdown-name",
        ),
        pytest.param(
            (
                "fix.md",
                "---\ndefault: patch\n---\n\n# Fix a bug\n",
                PullRequestCredit(name="alice", linked=True),
                "knope",
            ),
            "---\ndefault: patch\n---\n\n# Fix a bug by [@alice](https://github.com/alice)\n",
            id="knope-login",
        ),
    ],
)
def test_add_pull_request_links_credits_commit_author_without_pull_request(
    tmp_path: Path, case: tuple[str, str, PullRequestCredit, Literal["towncrier", "knope"]], expected: str
) -> None:
    filename, content, author, mode = case
    fragment = tmp_path / filename
    fragment.write_text(content)

    add_pull_request_links(
        tmp_path, "tox-dev/example", {}, commits={filename: FragmentCommit(sha="a" * 40, credits=(author,))}, mode=mode
    )

    assert fragment.read_text() == expected


def test_add_pull_request_links_knope_keeps_bare_reference(tmp_path: Path) -> None:
    fragment = tmp_path / "trust-roots.md"
    content = "---\ndefault: security\n---\n\n# Remove a root (#42) by @alice\n"
    fragment.write_text(content)

    _link(tmp_path, "tox-dev/example", {fragment.name: "Patch trust roots (#42)"}, mode="knope")

    assert fragment.read_text() == content


_ALICE: Final = PullRequestCredit(name="alice", linked=True)
_BOB: Final = PullRequestCredit(name="bob", linked=True)
_CAROL: Final = PullRequestCredit(name="Carol Doe", linked=False)
_DAN: Final = PullRequestCredit(name="dan", linked=True)


@pytest.mark.parametrize(
    ("filename", "content", "credited", "expected"),
    [
        pytest.param(
            "+first.feature.md",
            "Add a feature.\n",
            (_ALICE, _BOB),
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@alice](https://github.com/alice) and [@bob](https://github.com/bob).\n",
            id="markdown-two",
        ),
        pytest.param(
            "+first.feature.md",
            "Add a feature.\n",
            (_ALICE, _BOB, _CAROL, _DAN),
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@alice](https://github.com/alice), [@bob](https://github.com/bob), Carol Doe "
            "and [@dan](https://github.com/dan).\n",
            id="markdown-many",
        ),
        pytest.param(
            "+first.feature.md",
            "Add a feature.\n",
            (_ALICE, _CAROL),
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@alice](https://github.com/alice) and Carol Doe.\n",
            id="markdown-unlinked",
        ),
        pytest.param(
            "+first.feature.rst",
            "Add a feature.\n",
            (_ALICE, _BOB),
            "Add a feature (:pr:`42`) by :user:`alice` and :user:`bob`.\n",
            id="rst-two",
        ),
        pytest.param(
            "+first.feature.rst",
            "Add a feature.\n",
            (_ALICE, _BOB, _CAROL),
            "Add a feature (:pr:`42`) by :user:`alice`, :user:`bob` and Carol Doe.\n",
            id="rst-three",
        ),
        pytest.param(
            "+first.feature.rst",
            "Add a feature.\n",
            (_CAROL,),
            "Add a feature (:pr:`42`) by Carol Doe.\n",
            id="rst-unlinked-only",
        ),
        pytest.param(
            "42.feature.md",
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)).\n",
            (_ALICE, _BOB, _CAROL),
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@alice](https://github.com/alice), [@bob](https://github.com/bob) and Carol Doe.\n",
            id="markdown-numbered-linked",
        ),
        pytest.param(
            "42.feature.rst",
            "Add a feature (:pr:`42`).\n",
            (_ALICE, _BOB),
            "Add a feature (:pr:`42`) by :user:`alice` and :user:`bob`.\n",
            id="rst-numbered-linked",
        ),
    ],
)
def test_add_pull_request_links_formats_credits(
    tmp_path: Path, filename: str, content: str, credited: tuple[PullRequestCredit, ...], expected: str
) -> None:
    fragment = tmp_path / filename
    fragment.write_text(content)

    add_pull_request_links(
        tmp_path, "tox-dev/example", {filename: PullRequest(number="42", credits=credited)}, commits={}
    )

    assert fragment.read_text() == expected


@pytest.mark.parametrize(
    ("filename", "content", "expected"),
    [
        pytest.param(
            "+first.feature.md",
            "Add a feature.\n",
            "Add a feature ([#42](https://github.com/tox-dev/example/pull/42)).\n",
            id="markdown",
        ),
        pytest.param("+first.feature.rst", "Add a feature.\n", "Add a feature (:pr:`42`).\n", id="rst"),
        pytest.param("42.feature.md", "Fix #42.\n", "Fix #42.\n", id="markdown-linked"),
        pytest.param("42.feature.rst", "Fix #42.\n", "Fix #42.\n", id="rst-linked"),
    ],
)
def test_add_pull_request_links_without_credits_adds_only_link(
    tmp_path: Path, filename: str, content: str, expected: str
) -> None:
    fragment = tmp_path / filename
    fragment.write_text(content)

    add_pull_request_links(
        tmp_path,
        "tox-dev/example",
        {filename: PullRequest(number="42", credits=())},
        commits={},
    )

    assert fragment.read_text() == expected


def test_add_pull_request_links_knope_formats_credits(tmp_path: Path) -> None:
    fragment = tmp_path / "trust-roots.md"
    fragment.write_text("---\ndefault: security\n---\n\n# Remove a root\n")

    add_pull_request_links(
        tmp_path,
        "tox-dev/example",
        {fragment.name: PullRequest(number="42", credits=(_ALICE, _BOB, _CAROL))},
        commits={},
        mode="knope",
    )

    assert fragment.read_text() == (
        "---\ndefault: security\n---\n\n# Remove a root ([#42](https://github.com/tox-dev/example/pull/42)) "
        "by [@alice](https://github.com/alice), [@bob](https://github.com/bob) and Carol Doe\n"
    )


_MARKUP_NAME: Final = "Ann *B* _C_ `D` [E](F) <G> |H| \\I &amp; :user:`j` #42 O'Neil"


def _linked_unlinked_name(tmp_path: Path, extension: str) -> str:
    fragment = tmp_path / f"+first.feature.{extension}"
    fragment.write_text("Add a feature.\n")
    credit = PullRequestCredit(name=_MARKUP_NAME, linked=False)

    add_pull_request_links(
        tmp_path, "tox-dev/example", {fragment.name: PullRequest(number="42", credits=(credit,))}, commits={}
    )

    return fragment.read_text()


def test_add_pull_request_links_escapes_unlinked_name_in_markdown(tmp_path: Path) -> None:
    tokens = MarkdownIt().parse(_linked_unlinked_name(tmp_path, "md"))
    text = "".join(child.content for token in tokens for child in token.children or () if child.type == "text")

    assert text == f"Add a feature (#42) by {_MARKUP_NAME}."


def test_add_pull_request_links_escapes_unlinked_name_in_rst(tmp_path: Path) -> None:
    register_roles()
    document = publish_doctree(
        _linked_unlinked_name(tmp_path, "rst"),
        settings_overrides={"release_repository": "tox-dev/example", "report_level": 5, "halt_level": 2},
    )

    assert document.astext() == f"Add a feature (#42) by {_MARKUP_NAME}."


@pytest.mark.parametrize(
    ("filename", "name", "expected"),
    [
        pytest.param(
            "42.feature.md",
            "Carol",
            "Fix a bug ([#42](https://github.com/tox-dev/example/pull/42)) by Carol.\n",
            id="markdown",
        ),
        pytest.param("42.feature.rst", "Carol", "Fix a bug (:pr:`42`) by Carol.\n", id="rst"),
        pytest.param(
            "42.feature.md",
            "J. R. Doe!",
            "Fix a bug ([#42](https://github.com/tox-dev/example/pull/42)) by J\\. R\\. Doe\\!.\n",
            id="markdown-escaped-punctuation",
        ),
        pytest.param("42.feature.rst", "J. R. Doe", "Fix a bug (:pr:`42`) by J\\. R\\. Doe.\n", id="rst-escaped-dot"),
    ],
)
def test_add_pull_request_links_rerun_keeps_unlinked_credit(
    tmp_path: Path, filename: str, name: str, expected: str
) -> None:
    fragment = tmp_path / filename
    fragment.write_text("Fix a bug.\n")
    pull = PullRequest(number="42", credits=(PullRequestCredit(name=name, linked=False),))

    for _ in range(2):
        add_pull_request_links(tmp_path, "tox-dev/example", {filename: pull}, commits={})

    assert fragment.read_text() == expected


def test_add_pull_request_links_knope_rerun_keeps_unlinked_credit(tmp_path: Path) -> None:
    fragment = tmp_path / "trust-roots.md"
    fragment.write_text("---\ndefault: security\n---\n\n# Remove a root\n")
    pull = PullRequest(number="42", credits=(PullRequestCredit(name="Carol", linked=False),))

    for _ in range(2):
        add_pull_request_links(tmp_path, "tox-dev/example", {fragment.name: pull}, commits={}, mode="knope")

    assert fragment.read_text() == (
        "---\ndefault: security\n---\n\n# Remove a root ([#42](https://github.com/tox-dev/example/pull/42)) by Carol\n"
    )


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        pytest.param(
            "+first.feature.md",
            "Fix a crash caused by stale caches ([#42](https://github.com/tox-dev/example/pull/42)) "
            "by [@alice](https://github.com/alice).\n",
            id="markdown",
        ),
        pytest.param(
            "+first.feature.rst",
            "Fix a crash caused by stale caches (:pr:`42`) by :user:`alice`.\n",
            id="rst",
        ),
    ],
)
def test_add_pull_request_links_credits_unlinked_fragment_ending_in_by_prose(
    tmp_path: Path, filename: str, expected: str
) -> None:
    fragment = tmp_path / filename
    fragment.write_text("Fix a crash caused by stale caches.\n")

    _link(tmp_path, "tox-dev/example", {filename: "Add release notes (#42)"})

    assert fragment.read_text() == expected

"""Share the Towncrier fragment contract across PR and release checks."""

# ruff: file-ignore[lazy-import-immediately-resolved]  # Shared HTML pattern compiles when the module loads.
from __future__ import annotations

lazy import re
lazy from html.parser import HTMLParser
lazy from io import StringIO
lazy from pathlib import Path
lazy from typing import Final, cast, override

lazy from docutils import nodes
lazy from docutils.core import publish_doctree
lazy from markdown_it import MarkdownIt
lazy from markdown_it.token import Token

lazy from release_creator.notes.rst import register_roles

# This pattern runs for every inline token in each pending fragment.
_RE_HTML_TAG: Final = re.compile(
    r"""
    <\s*(?P<closing>/)?\s*(?P<name>code|kbd|pre|samp|script|style|textarea|template|noscript)\b  # Hidden HTML element
    (?P<attributes>(?:[^>"']|"[^"]*"|'[^']*')*)>         # Attributes may contain quoted >
    """,
    re.VERBOSE | re.IGNORECASE,
)


def validate_towncrier_fragment(content: str, fragment: Path) -> None:
    """Keep attribution inside the item supplied by bullet-prefix templates."""
    if fragment.suffix == ".md":
        tokens = MarkdownIt().enable("table").parse(content)
        allowed = {"paragraph_open", "paragraph_close", "fence", "code_block", "html_block", "hr"}
        structured = not any(token.type == "paragraph_open" and token.level == 0 for token in tokens) or any(
            token.type not in allowed for token in tokens if token.level == 0
        )
        if not structured:
            markdown_visible_children(tokens)
    else:
        register_roles()
        document = publish_doctree(
            content,
            settings_overrides={
                "file_insertion_enabled": False,
                "halt_level": 6,
                "raw_enabled": True,
                "release_repository": "shape/check",
                "report_level": 5,
                "warning_stream": StringIO(),
            },
        )
        structured = not any(isinstance(node, nodes.paragraph) for node in document.children) or any(
            not isinstance(node, (nodes.paragraph, nodes.literal_block)) for node in document.children
        )
    if structured:
        msg = f"fragment must be prose; the Towncrier template adds its list item: {fragment}"
        raise ValueError(msg)


def markdown_visible_children(tokens: list[Token]) -> list[tuple[Token | None, int]]:
    """Literal HTML text cannot establish visible release attribution."""
    visible: list[tuple[Token | None, int]] = []
    hidden: list[str] = []
    block_parser = _BlockLiteralParser(hidden)
    has_inline = False
    for token in tokens:
        if token.type == "html_block":
            block_parser.feed(token.content)
            continue
        if token.type != "inline":
            continue
        end_line = token.map[1] if token.map is not None else 0
        if has_inline:
            visible.append((None, end_line))
        has_inline = True
        for child in token.children or ():
            if child.type == "html_inline" and _update_literal_stack(child.content, hidden):
                continue
            if not hidden:
                visible.append((child, end_line))
    block_parser.close()
    if hidden:
        msg = "unclosed HTML literal element in changelog fragment"
        raise ValueError(msg)
    return visible


def _update_literal_stack(content: str, hidden: list[str]) -> bool:
    if (match := _RE_HTML_TAG.fullmatch(content)) is None:
        return False
    if not match["closing"] and match["attributes"].rstrip().endswith("/"):
        msg = "self-closing HTML literal elements are unsupported in changelog fragments"
        raise ValueError(msg)
    if match["closing"]:
        if not hidden or hidden[-1] != match["name"].casefold():
            msg = "mismatched HTML literal elements in changelog fragment"
            raise ValueError(msg)
        hidden.pop()
    else:
        hidden.append(match["name"].casefold())
    return True


class _BlockLiteralParser(HTMLParser):
    def __init__(self, hidden: list[str]) -> None:
        super().__init__()
        self._hidden = hidden

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:  # Required callback signature.
        _update_literal_stack(cast("str", self.get_starttag_text()), self._hidden)

    @override
    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:  # Required callback signature.
        _update_literal_stack(cast("str", self.get_starttag_text()), self._hidden)

    @override
    def handle_endtag(self, tag: str) -> None:
        _update_literal_stack(f"</{tag}>", self._hidden)


__all__ = [
    "markdown_visible_children",
    "validate_towncrier_fragment",
]

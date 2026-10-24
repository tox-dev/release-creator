"""Validate prose fragments for bullet-prefix Towncrier templates."""

from __future__ import annotations

lazy from io import StringIO
lazy from pathlib import Path

lazy from docutils import nodes
lazy from docutils.core import publish_doctree
lazy from markdown_it import MarkdownIt

lazy from release_creator.notes.rst import register_roles


def validate_towncrier_fragment(content: str, fragment: Path) -> None:
    """Require prose that the Towncrier template can place inside one list item.

    :param content: Pending fragment source.
    :param fragment: Fragment path, including its Markdown or RST suffix.
    :raises ValueError: The fragment contains unsupported block structure.
    """
    if fragment.suffix == ".md":
        allowed = {"paragraph_open", "paragraph_close", "fence", "code_block", "html_block", "hr"}
        structured = any(
            token.type not in allowed for token in MarkdownIt().enable("table").parse(content) if token.level == 0
        )
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
        structured = any(
            not isinstance(node, (nodes.paragraph, nodes.literal_block, nodes.comment)) for node in document.children
        )
    if structured:
        msg = f"fragment must be prose; the Towncrier template adds its list item: {fragment}"
        raise ValueError(msg)


__all__ = ["validate_towncrier_fragment"]

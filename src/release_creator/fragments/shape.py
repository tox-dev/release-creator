"""Share the Towncrier fragment contract across PR and release checks."""

from __future__ import annotations

lazy from io import StringIO
lazy from pathlib import Path

lazy from docutils import nodes
lazy from docutils.core import publish_doctree
lazy from markdown_it import MarkdownIt

lazy from release_creator.notes.rst import register_roles


def validate_towncrier_fragment(content: str, fragment: Path) -> None:
    """Reject blocks that bullet-prefix templates place outside one change item.

    :param content: Pending fragment source.
    :param fragment: Fragment path, including its Markdown or RST suffix.
    :raises ValueError: The fragment contains unsupported block structure.
    """
    if fragment.suffix == ".md":
        tokens = MarkdownIt().enable("table").parse(content)
        allowed = {"paragraph_open", "paragraph_close", "fence", "code_block", "html_block", "hr"}
        structured = not any(token.type == "paragraph_open" and token.level == 0 for token in tokens) or any(
            token.type not in allowed for token in tokens if token.level == 0
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
        structured = not any(isinstance(node, nodes.paragraph) for node in document.children) or any(
            not isinstance(node, (nodes.paragraph, nodes.literal_block)) for node in document.children
        )
    if structured:
        msg = f"fragment must be prose; the Towncrier template adds its list item: {fragment}"
        raise ValueError(msg)


__all__ = [
    "validate_towncrier_fragment",
]

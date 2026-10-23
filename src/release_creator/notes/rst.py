"""Render supported changelog reStructuredText as GitHub Markdown."""

from __future__ import annotations

lazy from io import StringIO
lazy from typing import cast
lazy from urllib.parse import quote

lazy from docutils import nodes
lazy from docutils.core import publish_doctree
lazy from docutils.parsers.rst import roles
lazy from docutils.parsers.rst.states import Inliner
lazy from docutils.utils import SystemMessage

lazy from release_creator.anchors.names import release_anchor
lazy from release_creator.categories import RELEASE_CATEGORIES


def render_rst_section(source: str, tag: str, repository: str) -> str:
    """Convert one RST release body to GitHub Markdown.

    :param source: RST between this version heading and the next one.
    :param tag: Release tag used in section anchors.
    :param repository: GitHub owner and repository for role links.
    :returns: Markdown body with release categories and warnings.
    """
    _register_roles()
    body: list[str] = []
    for block in _parse_document(source, repository).children:
        if isinstance(block, nodes.target):
            continue
        if not isinstance(block, nodes.section):
            _reject_top_level(block)
        body.extend(_render_section(block, tag))
    return "\n\n".join(body)


def _register_roles() -> None:
    def github_role(
        name: str,
        rawtext: str,
        text: str,
        _lineno: int,
        inliner: Inliner,
        **ignored: dict[str, str] | list[str],
    ) -> tuple[list[nodes.Node], list[nodes.system_message]]:
        del ignored
        if name == "user":
            return [nodes.Text(f"@{text}")], []
        if name.lower() == "pep":
            number, _, anchor = text.partition("#")
            if not number.isdecimal():
                msg = f"invalid PEP number: {text}"
                raise ValueError(msg)
            url = f"https://peps.python.org/pep-{int(number):04d}/"
            return [nodes.reference(rawtext, f"PEP {number}", refuri=f"{url}#{anchor}" if anchor else url)], []
        if not text.isdecimal():
            msg = f"invalid {name} number: {text}"
            raise ValueError(msg)
        path = "pull" if name in {"pr", "pull"} else "issues"
        repository = inliner.document.settings.release_repository
        return [nodes.reference(rawtext, f"#{text}", refuri=f"https://github.com/{repository}/{path}/{text}")], []

    def literal_role(
        _: str,
        rawtext: str,
        text: str,
        _lineno: int,
        _inliner: Inliner,
        **ignored: dict[str, str] | list[str],
    ) -> tuple[list[nodes.Node], list[nodes.system_message]]:
        del ignored
        display, separator, target = " ".join(text.split()).partition(" <")
        label = display if separator and target.endswith(">") else text.lstrip("~").rsplit(".", 1)[-1]
        return [nodes.literal(rawtext, label)], []

    for name in ("pr", "pull", "issue", "user", "pep"):
        roles.register_local_role(name, github_role)
    for name in (
        "attr",
        "class",
        "confval",
        "cvar",
        "data",
        "discussion",
        "doc",
        "event",
        "exc",
        "func",
        "meth",
        "mod",
        "obj",
        "option",
        "pypi",
        "ref",
        "py:data",
        "py:mod",
        "rst:dir",
    ):
        roles.register_local_role(name, literal_role)


def _parse_document(source: str, repository: str) -> nodes.document:
    try:
        document = cast(
            "nodes.document",
            publish_doctree(
                source,
                settings_overrides={
                    "doctitle_xform": False,
                    "file_insertion_enabled": False,
                    "halt_level": 3,
                    "raw_enabled": False,
                    "release_repository": repository,
                    "report_level": 5,
                    "warning_stream": StringIO(),
                },
            ),
        )
    except SystemMessage as error:
        detail = str(error)
        if '"code-block" directive' in detail:
            msg = "empty RST directive: code-block"
        else:
            msg = f"unexpected release text: {detail}"
        raise ValueError(msg) from error
    for message in list(document.findall(nodes.system_message)):
        if message["type"] != "INFO":
            msg = f"unexpected release text: {message.astext()}"
            raise ValueError(msg)
        message.parent.remove(message)
    return document


def _reject_top_level(block: nodes.Node) -> None:
    if isinstance(block, nodes.literal_block):
        msg = "code block outside a release item"
    elif isinstance(block, (nodes.bullet_list, nodes.block_quote)):
        msg = "release item outside a category"
    else:
        msg = f"unexpected release text: {block.astext()}"
    raise ValueError(msg)


def _render_section(section: nodes.section, tag: str) -> list[str]:
    name = section[0].astext()
    if name not in RELEASE_CATEGORIES:
        msg = f"unknown changelog category: {name}"
        raise ValueError(msg)
    entries: list[str] = []
    warnings: list[str] = []
    for child in section[1:]:
        if isinstance(child, nodes.target):
            continue
        if isinstance(child, nodes.bullet_list) and not warnings:
            entries.extend(_render_item(item, 0) for item in child)
        elif isinstance(child, nodes.warning):
            warnings.append(f"> **Warning:** {' '.join(_render_paragraph(part) for part in child)}")
        else:
            _reject_top_level(child)
    if entries:
        body = "\n".join(entries)
        warnings.insert(0, f'<a name="{release_anchor(tag, name)}"></a>\n\n### {RELEASE_CATEGORIES[name]}\n\n{body}')
    return warnings


def _render_item(item: nodes.list_item, depth: int) -> str:
    indent = "  " * depth
    if isinstance(item[0], nodes.bullet_list) and len(item) == 1:
        nested = "\n".join(_render_item(entry, depth + 1) for entry in item[0])
        return f"{indent}-\n{nested}"
    result = f"{indent}- {_render_paragraph(item[0])}"
    only_paragraphs = True
    for child in item[1:]:
        if isinstance(child, nodes.paragraph) and only_paragraphs:
            result += f" {_render_paragraph(child)}"
        else:
            result += _render_item_child(child, item, depth)
        only_paragraphs = only_paragraphs and isinstance(child, nodes.paragraph)
    return result


def _render_paragraph(node: nodes.Node) -> str:
    return " ".join(_render_inline(node).split()).replace(" - by ", " by ")


def _render_inline(node: nodes.Node) -> str:
    if isinstance(node, nodes.Text):
        value = _escape_text(node.astext())
    elif isinstance(node, nodes.title_reference):
        value = _code_span(node.rawsource[1:-1])
    elif isinstance(node, nodes.literal):
        value = _code_span(node.astext())
    elif isinstance(node, nodes.reference):
        label = node.astext()
        url = node.get("refuri")
        is_profile = label.startswith("@") and url == f"https://github.com/{label.removeprefix('@')}"
        value = label if is_profile or url is None or url == label else f"[{_escape_text(label)}]({_escape_url(url)})"
    elif isinstance(node, nodes.target):
        value = ""
    elif isinstance(node, nodes.emphasis):
        value = f"*{''.join(map(_render_inline, node.children))}*"
    elif isinstance(node, nodes.strong):
        value = f"**{''.join(map(_render_inline, node.children))}**"
    else:
        value = "".join(map(_render_inline, cast("nodes.Element", node).children))
    return value


def _escape_text(value: str) -> str:
    for character in ("\\", "`", "*", "_", "[", "]", "<", ">"):
        value = value.replace(character, f"\\{character}")
    return value


def _escape_url(value: str) -> str:
    return quote(value, safe="/:#?&=@%+,-._").replace("~", "%7E")


def _code_span(value: str) -> str:
    fence = _backtick_fence(value, 1)
    padding = " " if "`" in value else ""
    return f"{fence}{padding}{value}{padding}{fence}"


def _backtick_fence(value: str, minimum: int) -> str:
    longest = run = 0
    for character in value:
        run = run + 1 if character == "`" else 0
        longest = max(longest, run)
    return "`" * max(minimum, longest + 1)


def _render_item_child(child: nodes.Node, item: nodes.list_item, depth: int) -> str:
    indent = "  " * depth
    if isinstance(child, nodes.bullet_list):
        children = list(child.children)
        credit = _render_paragraph(children[-1][0]) if children and _is_credit(children[-1]) else None
        if credit is not None:
            children.pop()
        nested = "\n".join(_render_item(entry, depth + 1) for entry in children)
        result = f"\n{nested}" if children else ""
        if credit is not None:
            result += f"\n\n{indent}  {credit}" if children or child is not item.children[1] else f" {credit}"
        return result
    if isinstance(child, nodes.paragraph):
        return f"\n\n{indent}  {_render_paragraph(child)}"
    if isinstance(child, nodes.literal_block):
        language = next((name for name in child["classes"] if name != "code"), "")
        code = "\n".join(f"{indent}  {line}" for line in child.astext().splitlines())
        fence = _backtick_fence(child.astext(), 3)
        return f"\n\n{indent}  {fence}{language}\n{code}\n{indent}  {fence}"
    msg = f"unexpected release text: {child.tagname}"
    raise TypeError(msg)


def _is_credit(item: nodes.Node) -> bool:
    return (
        isinstance(item, nodes.list_item)
        and len(item) == 1
        and isinstance(item[0], nodes.paragraph)
        and item[0].astext().startswith("by ")
    )


__all__ = [
    "render_rst_section",
]

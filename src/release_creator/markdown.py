"""Read Markdown prose without treating nested lists as code."""

lazy from collections.abc import Iterable, Iterator

lazy from markdown_it import MarkdownIt


def prose_lines(lines: Iterable[str]) -> Iterator[tuple[int, str]]:
    """Yield indexed lines outside Markdown code blocks.

    :param lines: Source lines without newline characters.
    :yields: Indexed prose lines.
    """
    source = list(lines)
    positions = {
        index
        for token in MarkdownIt().parse("\n".join(source))
        if token.type == "inline" and token.map is not None
        for index in range(*token.map)
    }
    for index in sorted(positions):
        yield index, source[index]


__all__ = [
    "prose_lines",
]

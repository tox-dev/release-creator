"""Read Markdown lines outside fenced and indented code."""

# ruff: file-ignore[lazy-import-immediately-resolved]  # The shared fence pattern compiles during module load.
lazy import re
lazy from collections.abc import Iterable, Iterator
lazy from typing import Final

_CODE_FENCE: Final = re.compile(
    r"""
    ^[ ]{0,3}(?P<delimiter>`{3,}|~{3,})(?P<rest>.*)$  # Fence and optional info string
    """,
    re.VERBOSE,
)


def prose_lines(lines: Iterable[str]) -> Iterator[tuple[int, str]]:
    """Yield indexed lines outside Markdown code blocks.

    :param lines: Source lines without newline characters.
    :yields: Indexed prose lines.
    """
    fence: str | None = None
    for index, line in enumerate(lines):
        if match := _CODE_FENCE.match(line):
            delimiter = str(match["delimiter"])
            if fence is None:
                fence = delimiter
            elif delimiter[0] == fence[0] and len(delimiter) >= len(fence) and not match["rest"].strip():
                fence = None
            continue
        if fence is None and not line.startswith("    "):
            yield index, line


__all__ = [
    "prose_lines",
]

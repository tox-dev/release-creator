"""Tell the reader what a command decided without touching the output callers capture."""

lazy import sys


def explain(message: str) -> None:
    """Write one decision and its reason to stderr, keeping stdout and written files for data.

    :param message: One short plain line.
    """
    sys.stderr.write(f"{message}\n")


def counted(number: int, singular: str, plural: str | None = None) -> str:
    """Pair a count with the noun form that matches it.

    :param number: How many there are.
    :param singular: Noun for one.
    :param plural: Noun for any other count; defaults to ``singular`` with an ``s``.
    :returns: For example ``1 fragment`` or ``3 entries``.
    """
    return f"{number} {singular if number == 1 else plural or f'{singular}s'}"


__all__ = [
    "counted",
    "explain",
]

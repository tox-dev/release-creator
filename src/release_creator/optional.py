"""Report missing optional command dependencies."""

lazy from importlib.util import find_spec


def require_yaml() -> None:
    """Fail with the installable extra instead of an import traceback.

    Raises:
        ValueError: PyYAML is absent.

    """
    if find_spec("yaml") is None:
        msg = "install release-creator[yaml] to use this command"
        raise ValueError(msg)


__all__ = [
    "require_yaml",
]

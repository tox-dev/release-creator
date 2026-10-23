"""Run local tools with captured UTF-8 output."""

lazy import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Callers pass argument lists without a shell.
lazy from pathlib import Path


def run_text(
    command: list[str], *, cwd: Path | None = None, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a command without a shell.

    :param command: Executable and arguments, passed without a shell.
    :param cwd: Working directory for the command.
    :param stdin: Text sent to the command.
    :returns: Captured stdout, stderr, and exit status.
    :raises ValueError: The command exceeds the timeout.
    """
    try:
        return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # No shell or interpolated command.
            command,
            cwd=cwd,
            input=stdin,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            timeout=300,
        )
    except subprocess.TimeoutExpired as error:
        msg = f"command timed out after 300 seconds: {command[0]}"
        raise ValueError(msg) from error


__all__ = [
    "run_text",
]

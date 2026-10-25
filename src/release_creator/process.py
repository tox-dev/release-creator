"""Run local tools with captured UTF-8 output."""

lazy import os
lazy import shlex
lazy import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Callers pass argument lists without a shell.
lazy from collections.abc import Mapping
lazy from pathlib import Path


def run_text(
    command: list[str], *, cwd: Path | None = None, stdin: str | None = None, env: Mapping[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a command without a shell.

    :param command: Executable and arguments, passed without a shell.
    :param cwd: Working directory for the command.
    :param stdin: Text sent to the command.
    :param env: Environment passed to the command, or the parent's environment.
    :returns: Captured stdout, stderr, and exit status.
    :raises ValueError: The command exceeds the timeout.
    """
    try:
        return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # No shell or interpolated command.
            command,
            cwd=cwd,
            env=env,
            input=stdin,
            stdin=subprocess.DEVNULL if stdin is None else None,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            timeout=300,
        )
    except subprocess.TimeoutExpired as error:
        msg = f"command timed out after 300 seconds: {shlex.join(command)}"
        raise ValueError(msg) from error


def isolated_uv_env() -> dict[str, str]:
    """Copy the environment without uv, pip, or TLS trust overrides, so uv reaches PyPI with the system CA store.

    :returns: Environment for a uv resolver process.
    """
    return {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("UV_", "PIP_"))
        and name not in {"SSL_CERT_FILE", "SSL_CERT_DIR", "SSL_CLIENT_CERT", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"}
    }


__all__ = [
    "isolated_uv_env",
    "run_text",
]

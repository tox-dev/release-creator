"""GitHub CLI boundary shared by New Contributors tests."""

from __future__ import annotations

import json
import re
import subprocess  # ruff: ignore[suspicious-subprocess-import]  # Model the GitHub CLI boundary.
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, create_autospec

import pytest

from release_creator import process

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

type Pull = tuple[str | None, str, str | None]
type GitHub = Callable[[Mapping[str, Pull], set[str]], MagicMock]


@pytest.fixture
def github(monkeypatch: pytest.MonkeyPatch) -> GitHub:
    """Answer pull request and search queries from a table of pulls and returning authors."""

    def install(pulls: Mapping[str, Pull], returning: set[str]) -> MagicMock:
        def respond(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            query = cast("str", kwargs["input"])
            if "pullRequest(" in query:
                data: dict[str, object] = {
                    "repository": {
                        f"p{number}": {
                            "number": int(number),
                            "mergedAt": pulls[number][2],
                            "author": None
                            if pulls[number][0] is None
                            else {"login": pulls[number][0], "__typename": pulls[number][1]},
                        }
                        for number in re.findall(r"pullRequest\(number: (\d+)\)", query)
                    }
                }
            else:
                data = {
                    alias: {"issueCount": int(login in returning)}
                    for alias, login in re.findall(r"(s\d+): search\(query: \"[^\"]* author:(\S+) ", query)
                }
            return subprocess.CompletedProcess(command, 0, json.dumps({"data": data}), "")

        run = cast("MagicMock", create_autospec(process.subprocess.run, side_effect=respond))
        monkeypatch.setattr(process.shutil, "which", create_autospec(process.shutil.which, return_value="gh"))
        monkeypatch.setattr(process.subprocess, "run", run)
        return run

    return install

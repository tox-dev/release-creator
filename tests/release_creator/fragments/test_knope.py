"""Knope changeset front matter tests."""

from pathlib import Path

import pytest

from release_creator.fragments.knope import changeset_versioning


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        pytest.param(
            "---\npackage name: patch\npackage name 2: minor\n---\nSummary\n",
            {"package name": "patch", "package name 2": "minor"},
            id="spaces-in-package-names",
        ),
        pytest.param("---\n  default  :   minor  \n---\n\n# Summary\n", {"default": "minor"}, id="trimmed-sides"),
        pytest.param("---\ndefault: custom: type\n---\n\n# Summary\n", {"default": "custom: type"}, id="first-colon"),
        pytest.param("---\n\"default\": 'patch'\n---\n\n# Summary\n", {'"default"': "'patch'"}, id="quotes-literal"),
        pytest.param("---\ndefault: patch # fix\n---\n\n# Summary\n", {"default": "patch # fix"}, id="comment-literal"),
        pytest.param(" --- \r\ndefault: patch\r\n ---\r\n\r\n# Summary\r\n", {"default": "patch"}, id="crlf-fences"),
    ],
)
def test_changeset_versioning(content: str, expected: dict[str, str]) -> None:
    assert changeset_versioning(Path("news.md"), content) == expected


@pytest.mark.parametrize(
    ("content", "error"),
    [
        pytest.param("default: patch\n---\n\n# Summary\n", "missing YAML front matter", id="missing-opening-fence"),
        pytest.param("", "missing YAML front matter", id="empty-file"),
        pytest.param("---\ndefault: patch\n", "invalid changeset front matter", id="missing-closing-fence"),
        pytest.param("---\ndefault patch\n---\n\n# Summary\n", "invalid changeset front matter", id="no-colon"),
        pytest.param("---\ndefault: patch\n\n---\n", "invalid changeset front matter", id="blank-line"),
        pytest.param(
            "---\ndefault: patch\ndefault: minor\n---\n", "invalid changeset front matter", id="repeated-package"
        ),
        pytest.param("---\n---\n\n# Summary\n", "empty changeset front matter", id="empty-front-matter"),
        pytest.param("---\n", "empty changeset front matter", id="only-opening-fence"),
    ],
)
def test_changeset_versioning_rejects(content: str, error: str) -> None:
    with pytest.raises(ValueError, match=f"^{error} in news.md$"):
        changeset_versioning(Path("news.md"), content)

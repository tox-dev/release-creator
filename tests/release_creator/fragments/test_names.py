"""Fragment filenames shared by linking and release selection."""

from pathlib import Path

import pytest

from release_creator.fragments.names import fragment_category, fragment_number, pending_fragments


@pytest.mark.parametrize(
    ("filename", "category"),
    [
        pytest.param("+topic.feature.md", "feature", id="named"),
        pytest.param("+topic.feature.2.md", "feature", id="named-counter"),
        pytest.param("42.feature.rst", "feature", id="numbered-rst"),
        pytest.param("42.feature.1.md", "feature", id="numbered-counter"),
        pytest.param("topic.feature.md", None, id="unprefixed"),
        pytest.param("+.feature.md", None, id="empty-name"),
        pytest.param("42.other.md", None, id="unknown-category"),
    ],
)
def test_fragment_category(filename: str, category: str | None) -> None:
    assert fragment_category(Path(filename), {"feature"}) == category


@pytest.mark.parametrize(
    ("filename", "number"),
    [
        pytest.param("42.feature.md", "42", id="numbered"),
        pytest.param("42.feature.1.md", "42", id="counter"),
        pytest.param("+topic.feature.md", None, id="named"),
    ],
)
def test_fragment_number(filename: str, number: str | None) -> None:
    assert fragment_number(Path(filename)) == number


def test_pending_fragments_accepts_counter(tmp_path: Path) -> None:
    (tmp_path / "+topic.feature.2.md").write_text("New feature.\n", encoding="utf-8")

    assert [fragment.name for fragment in pending_fragments(tmp_path)] == ["+topic.feature.2.md"]


def test_pending_fragments_rejects_unprefixed_name(tmp_path: Path) -> None:
    (tmp_path / "topic.feature.md").write_text("New feature.\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported changelog fragment name"):
        pending_fragments(tmp_path)

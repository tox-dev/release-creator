"""Numeric release tag selection tests."""

from datetime import date

import pytest

lazy from release_creator.tags.select import next_tag, parse_tag, previous_tag, require_newer_tag


@pytest.mark.parametrize(
    ("bump", "tags", "fragments", "expected"),
    [
        pytest.param("auto", [], ["+one.feature.md"], "0.1.0", id="first-feature"),
        pytest.param("auto", ["1.2.3"], ["+one.breaking.md", "+two.feature.md"], "2.0.0", id="breaking"),
        pytest.param("auto", ["1.2.3"], ["+one.breaking.rst"], "2.0.0", id="breaking-rst"),
        pytest.param("auto", ["1.2.3", "junk"], ["+one.feature.md"], "1.3.0", id="feature"),
        pytest.param("auto", ["1.2.3"], ["+one.feature.rst"], "1.3.0", id="feature-rst"),
        pytest.param("auto", ["1.2.3"], ["+one.bugfix.md"], "1.2.4", id="fix"),
        pytest.param("major", ["1.2.3"], ["+one.bugfix.md"], "2.0.0", id="major"),
        pytest.param("minor", ["1.2.3"], ["+one.bugfix.md"], "1.3.0", id="minor"),
        pytest.param("patch", ["1.2.3"], ["+one.feature.md"], "1.2.4", id="patch"),
        pytest.param("calver", ["2026.9.4"], ["+one.bugfix.md"], "2026.10.0", id="new-month"),
        pytest.param("calver", ["2026.10.4"], ["+one.bugfix.md"], "2026.10.5", id="same-month"),
    ],
)
def test_next_tag(bump: str, tags: list[str], fragments: list[str], expected: str) -> None:
    assert next_tag(bump, tags, fragments, date(2026, 10, 19)) == expected


@pytest.mark.parametrize(
    ("bump", "tags", "fragments", "message"),
    [
        pytest.param("auto", [], [], "no changelog fragments", id="empty"),
        pytest.param("unknown", [], ["+one.feature.md"], "unknown version bump", id="bump"),
        pytest.param("calver", ["2026.11.0"], ["+one.feature.md"], "must be newer", id="older-calver"),
    ],
)
def test_next_tag_rejects_invalid(bump: str, tags: list[str], fragments: list[str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        next_tag(bump, tags, fragments, date(2026, 10, 19))


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        pytest.param("1.2.3", (1, 2, 3), id="normal"),
        pytest.param("01.002.3", (1, 2, 3), id="leading-zeros"),
    ],
)
def test_parse_tag(tag: str, expected: tuple[int, int, int]) -> None:
    assert parse_tag(tag) == expected


@pytest.mark.parametrize(
    "tag",
    [
        pytest.param("1.2", id="short"),
        pytest.param("1.2.3.4", id="long"),
        pytest.param("1.2.", id="empty"),
        pytest.param("1.2.x", id="non-numeric"),
        pytest.param("\u0661.2.3", id="non-ascii"),
    ],
)
def test_parse_tag_rejects_invalid(tag: str) -> None:
    with pytest.raises(ValueError, match=r"(?x)expected\ a\ major\.minor\.patch\ version # Invalid tag format"):
        parse_tag(tag)


def test_previous_tag_uses_numeric_order() -> None:
    assert previous_tag("1.10.0", ["1.9.0", "1.2.0", "junk", "1.10.0", "2.0.0"]) == "1.9.0"


def test_previous_tag_missing() -> None:
    assert previous_tag("1.0.0", ["junk", "1.0.0", "2.0.0"]) is None


def test_require_newer_tag_accepts_first_release() -> None:
    require_newer_tag("1.0.0", ["junk"])


def test_require_newer_tag_accepts_new_version() -> None:
    require_newer_tag("1.10.0", ["junk", "1.9.0"])


@pytest.mark.parametrize(
    "tag",
    [pytest.param("1.9.0", id="same"), pytest.param("1.8.9", id="older")],
)
def test_require_newer_tag_rejects_existing(tag: str) -> None:
    with pytest.raises(ValueError, match="must be newer"):
        require_newer_tag(tag, ["junk", "1.9.0"])

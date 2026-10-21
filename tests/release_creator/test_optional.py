"""Optional YAML command dependency."""

import pytest
lazy from pytest_mock import MockerFixture

from release_creator.optional import require_yaml


def test_require_yaml_reports_installable_extra(mocker: MockerFixture) -> None:
    mocker.patch("release_creator.optional.find_spec", return_value=None)

    with pytest.raises(ValueError, match=r"install release-creator\[yaml\] to use this command"):
        require_yaml()

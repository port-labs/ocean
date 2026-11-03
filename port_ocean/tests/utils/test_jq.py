from typing import Generator
from unittest.mock import patch

import pytest

from port_ocean.utils import jq


@pytest.fixture(autouse=True)
def allow_env_access() -> Generator[None, None, None]:
    with patch("port_ocean.utils.jq.ocean") as mock_ocean:
        mock_ocean.config.allow_environment_variables_jq_access = True
        yield


def test_evaluate_returns_first_result() -> None:
    assert jq.evaluate({"items": [1, 2]}, ".items[]") == 1


def test_evaluate_supports_single_quoted_strings() -> None:
    assert jq.evaluate({"name": "a"}, ".name == 'a'") is True


def test_evaluate_returns_none_for_invalid_pattern() -> None:
    assert jq.evaluate({"name": "a"}, ".name |||") is None


def test_evaluate_hides_env_when_access_disabled() -> None:
    with patch("port_ocean.utils.jq.ocean") as mock_ocean:
        mock_ocean.config.allow_environment_variables_jq_access = False
        assert jq.evaluate({}, "env") == {}

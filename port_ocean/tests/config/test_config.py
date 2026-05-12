import pytest
from pydantic import BaseModel
from port_ocean.config.dynamic import NoTrailingSlashUrl, default_config_factory
from typing import cast
from pydantic import parse_obj_as


class TestClass(BaseModel):
    url: NoTrailingSlashUrl | None


def as_no_trailing_slash_url(value: str | None) -> NoTrailingSlashUrl:
    # mypy casting
    return cast(NoTrailingSlashUrl, value)


def test_trailing_slash_valid() -> None:
    cls = TestClass(url=as_no_trailing_slash_url("http://example"))
    assert cls.url == "http://example"


def test_trailing_slash_valid_remove_slash() -> None:
    cls = TestClass(url=as_no_trailing_slash_url("http://example/"))
    assert cls.url == "http://example"


def test_trailing_slash_not_valid() -> None:
    with pytest.raises(ValueError):
        TestClass(url=as_no_trailing_slash_url("/"))


def test_trailing_slash_not_valid_no_domain() -> None:
    with pytest.raises(ValueError):
        TestClass(url=as_no_trailing_slash_url("http:///"))


def test_trailing_empty() -> None:
    cls = TestClass(url=None)
    assert cls.url is None


def test_dynamic_config_strips_whitespace_only_optional_string() -> None:
    ConfigModel = default_config_factory(
        [
            {
                "name": "webhookSecret",
                "type": "string",
                "required": False,
            }
        ]
    )

    cfg = parse_obj_as(ConfigModel, {"webhook_secret": "   "})
    assert cfg.webhook_secret == ""


def test_dynamic_config_strips_surrounding_whitespace() -> None:
    ConfigModel = default_config_factory(
        [
            {
                "name": "webhookSecret",
                "type": "string",
                "required": False,
            }
        ]
    )

    cfg = parse_obj_as(ConfigModel, {"webhook_secret": "  abc  "})
    assert cfg.webhook_secret == "abc"

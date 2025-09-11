import pytest
from pydantic import BaseModel
from port_ocean.config.dynamic import NoTrailingSlashUrl
from typing import cast


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

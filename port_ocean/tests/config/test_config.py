import pytest
from pydantic import BaseModel
from port_ocean.config.dynamic import NoTrailingSlashUrl


class TestClass(BaseModel):
    url: NoTrailingSlashUrl | None


def test_trailing_slash_valid():
    cls = TestClass(url="http://example")
    assert cls.url == "http://example"


def test_trailing_slash_valid_remove_slash():
    cls = TestClass(url="http://example/")
    assert cls.url == "http://example"


def test_trailing_slash_not_valid():
    with pytest.raises(ValueError):
        TestClass(url="/")


def test_trailing_slash_not_valid_no_domain():
    with pytest.raises(ValueError):
        TestClass(url="http:///")


def test_trailing_empty():
    cls = TestClass(url=None)
    assert cls.url is None

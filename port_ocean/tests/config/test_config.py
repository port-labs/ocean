import pytest
from pydantic import BaseModel, ValidationError

from port_ocean.config.dynamic import NoTrailingSlashUrl


class UrlModel(BaseModel):
    url: NoTrailingSlashUrl | None = None


def test_trailing_slash_valid() -> None:
    # Arrange
    raw_url = "http://example"

    # Act
    model = UrlModel(url=raw_url)

    # Assert
    assert model.url == "http://example"


def test_trailing_slash_valid_remove_slash() -> None:
    # Arrange
    raw_url = "http://example/"

    # Act
    model = UrlModel(url=raw_url)

    # Assert
    assert model.url == "http://example"


def test_trailing_slash_not_valid() -> None:
    # Act + Assert
    with pytest.raises(ValidationError):
        UrlModel(url="/")


def test_trailing_slash_not_valid_no_domain() -> None:
    # Act + Assert
    with pytest.raises(ValidationError):
        UrlModel(url="http:///")


def test_trailing_empty() -> None:
    # Act
    model = UrlModel(url=None)

    # Assert
    assert model.url is None

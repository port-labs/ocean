import pytest
from pydantic import BaseModel, ValidationError

from port_ocean.config.dynamic import NoTrailingSlashUrl
from port_ocean.config.settings import PortSettings
from port_ocean.core.event_listener.http import HttpEventListenerSettings
from port_ocean.core.models import EventListenerType


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


def test_port_base_url_strips_trailing_slash() -> None:
    settings = PortSettings(
        client_id="id",
        client_secret="secret",
        base_url="https://api.getport.io/",
    )

    assert settings.base_url == "https://api.getport.io"
    assert f"{settings.base_url}/v1" == "https://api.getport.io/v1"


def test_webhook_changelog_url_does_not_double_slash() -> None:
    settings = HttpEventListenerSettings(
        type=EventListenerType.WEBHOOK,
        app_host="https://example.com/",
    )

    assert settings.get_changelog_destination_details()["url"] == (
        "https://example.com/resync"
    )

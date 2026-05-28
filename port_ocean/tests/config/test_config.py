import pytest
from pydantic import BaseModel
from port_ocean.config.dynamic import NoTrailingSlashUrl
from typing import cast
from port_ocean.config.settings import PortSettings


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


class TestIngestURL:
    def test_ingest_url_uses_us_region_when_base_url_is_us(self):
        """
        When the base_url contains 'us.getport.io',
        the ingest_url should be updated to 'https://ingest.us.getport.io'.
        """
        settings = PortSettings(
            client_id="test_client_id",
            client_secret="test_client_secret",
            base_url="https://api.us.getport.io",
        )

        assert settings.ingest_url == "https://ingest.us.getport.io"

    def test_ingest_url_remains_standard_when_base_url_is_standard(self):
        """
        When the base_url does not contain 'us.getport.io' (e.g., default),
        the ingest_url should remain the standard 'https://ingest.getport.io'.
        """
        settings = PortSettings(
            client_id="test_client_id",
            client_secret="test_client_secret",
            base_url="https://api.getport.io",
        )

        assert settings.ingest_url == "https://ingest.getport.io"

    def test_ingest_url_is_case_insensitive(self):
        """
        The validation logic checks for a lowercase substring 'us.getport.io'.
        This test ensures that the base_url case does not affect the result.
        """
        settings = PortSettings(
            client_id="test_client_id",
            client_secret="test_client_secret",
            base_url="https://api.US.GETPORT.IO",  # Uppercase URL
        )

        # The expected ingest_url should be lowercase based on the logic
        assert settings.ingest_url == "https://ingest.us.getport.io"

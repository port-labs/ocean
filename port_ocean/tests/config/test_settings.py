from typing import Any

import pytest
from pydantic import ValidationError, AnyHttpUrl, parse_obj_as
from port_ocean.config.settings import PortSettings


@pytest.mark.parametrize(
    "url, valid, expected_error",
    [
        # Valid URLs
        ("https://api.getport.io", True, None),
        ("https://api.us.getport.io", True, None),
        ("https://api.stg-01.getport.io", True, None),
        ("http://localhost", True, None),
        ("http://localhost:8000", True, None),
        ("http://host.docker.internal:3000", True, None),
        # Invalid URLs
        ("https://invalid.getport.io", False, ValidationError),
        ("https://api.invalid.io", False, ValidationError),
        ("http://127.0.0.1", False, ValidationError),
        ("https://google.com", False, ValidationError),
        ("http://example.com:8000", False, ValidationError),
        ("ftp://not-api.getport.io", False, ValidationError),
        ("http://host.docker", False, ValidationError),
        ("http://host.docker:8080", False, ValidationError),
    ],
)
@pytest.mark.asyncio
async def test_base_urls(url: str, valid: bool, expected_error: Any) -> None:
    if valid:
        # Convert the string URL to AnyHttpUrl and assert it works in PortSettings
        base_url = parse_obj_as(AnyHttpUrl, url)
        settings = PortSettings(
            client_id="test_client_id",
            client_secret="test_client_secret",
            base_url=base_url,
        )
        assert settings.base_url == url
    else:
        # Expect a ValidationError for invalid URLs
        with pytest.raises(expected_error):
            base_url = parse_obj_as(AnyHttpUrl, url)
            PortSettings(
                client_id="test_client_id",
                client_secret="test_client_secret",
                base_url=base_url,
            )

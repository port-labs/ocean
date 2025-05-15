import pytest
from pydantic import ValidationError

from port_ocean.config.dynamic import (
    Configuration,
    default_config_factory,
    strip_url_trailing_slash,
)


def test_strip_url_trailing_slash():
    """Test the URL trailing slash stripping function."""
    test_cases = [
        ("https://gitlab.com/", "https://gitlab.com"),
        ("https://gitlab.com/path/", "https://gitlab.com/path"),
        ("https://gitlab.com/path/to/resource/", "https://gitlab.com/path/to/resource"),
        (
            "https://gitlab.com?param=value/",
            "https://gitlab.com?param=value/",
        ),  # Query params should not be affected
        (
            "https://gitlab.com#fragment/",
            "https://gitlab.com#fragment/",
        ),  # Fragments should not be affected
        (
            "https://gitlab.com/path//",
            "https://gitlab.com/path",
        ),  # Multiple trailing slashes
        ("https://gitlab.com", "https://gitlab.com"),  # No trailing slash
    ]

    for input_url, expected_url in test_cases:
        assert strip_url_trailing_slash(input_url) == expected_url


def test_url_configuration_from_spec():
    """Test URL configuration handling from spec.yaml."""
    configurations = [
        Configuration(
            name="gitlabHost",
            type="url",
            required=False,
            default="https://gitlab.com/",
            sensitive=False,
        ),
        Configuration(
            name="apiUrl",
            type="url",
            required=True,
            default=None,
            sensitive=False,
        ),
    ]

    model = default_config_factory(configurations)

    # Test default value stripping
    instance = model(api_url="https://api.example.com")
    assert str(instance.gitlab_host) == "https://gitlab.com"
    assert str(instance.api_url) == "https://api.example.com"

    # Test required field
    with pytest.raises(ValidationError):
        model()


def test_url_configuration_validation():
    """Test URL validation and error handling."""
    configurations = [
        Configuration(
            name="gitlabHost",
            type="url",
            required=True,
            default=None,
            sensitive=False,
        ),
    ]

    model = default_config_factory(configurations)

    # Test invalid URL
    with pytest.raises(ValidationError):
        model(gitlab_host="not-a-url")

    # Test missing protocol
    with pytest.raises(ValidationError):
        model(gitlab_host="gitlab.com")

    # Test valid URL with query params and fragments
    instance = model(gitlab_host="https://gitlab.com/api/v4/?param=value#fragment/")
    assert (
        str(instance.gitlab_host) == "https://gitlab.com/api/v4?param=value#fragment/"
    )


def test_url_configuration_with_other_types():
    """Test URL configuration alongside other configuration types."""
    configurations = [
        Configuration(
            name="gitlabHost",
            type="url",
            required=True,
            default=None,
            sensitive=False,
        ),
        Configuration(
            name="apiKey",
            type="string",
            required=True,
            default=None,
            sensitive=True,
        ),
        Configuration(
            name="enabled",
            type="boolean",
            required=False,
            default=True,
            sensitive=False,
        ),
    ]

    model = default_config_factory(configurations)

    # Test mixed configuration with all required fields
    instance = model(
        gitlab_host="https://gitlab.com",
        api_key="secret-key",
        enabled=True,
    )
    assert str(instance.gitlab_host) == "https://gitlab.com"
    assert instance.api_key == "secret-key"
    assert instance.enabled is True

    # Test missing required fields
    with pytest.raises(ValidationError):
        model(gitlab_host="https://gitlab.com")  # Missing api_key

    with pytest.raises(ValidationError):
        model(api_key="secret-key")  # Missing gitlab_host

    instance = model(
        gitlab_host="https://gitlab.com",
        api_key="secret-key",
    )
    assert instance.enabled is True

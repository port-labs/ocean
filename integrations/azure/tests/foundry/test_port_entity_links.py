from unittest.mock import MagicMock, patch

from azure_integration.foundry.helpers.port_entity_links import build_entity_page_url, build_foundry_response_entity_page_url


def test_build_entity_page_url_from_app_url() -> None:
    mock_ocean = MagicMock()
    mock_ocean.config.port.app_url = "http://localhost:3000/"
    with patch("azure_integration.foundry.helpers.port_entity_links.ocean", mock_ocean):
        url = build_entity_page_url("foundry_response", "resp_abc")
    assert url == "http://localhost:3000/foundry_responseEntity?identifier=resp_abc"


def test_build_foundry_response_entity_page_url() -> None:
    mock_ocean = MagicMock()
    mock_ocean.config.port.app_url = None
    mock_ocean.port_client.api_url = "http://api.localhost:9080/v1"
    with patch("azure_integration.foundry.helpers.port_entity_links.ocean", mock_ocean):
        url = build_foundry_response_entity_page_url("resp_xyz")
    assert url == "http://app.localhost:9080/foundry_responseEntity?identifier=resp_xyz"

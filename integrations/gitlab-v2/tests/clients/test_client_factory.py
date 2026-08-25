from unittest.mock import MagicMock, patch

from gitlab.clients.client_factory import create_gitlab_client_for_token


def test_create_gitlab_client_for_token_uses_host_and_token() -> None:
    with (
        patch("gitlab.clients.client_factory.ocean") as mock_ocean,
        patch("gitlab.clients.client_factory.GitLabClient") as mock_gitlab_client_cls,
    ):
        mock_ocean.integration_config = {
            "gitlab_host": "https://gitlab.example.com/",
            "gitlab_token": "service-token",
        }
        mock_gitlab_client_cls.return_value = MagicMock()

        client = create_gitlab_client_for_token("user-oauth-token")

        mock_gitlab_client_cls.assert_called_once_with(
            "https://gitlab.example.com", "user-oauth-token"
        )
        assert client is mock_gitlab_client_cls.return_value

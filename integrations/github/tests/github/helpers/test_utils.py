import pytest
from typing import Any, AsyncGenerator, Dict
from unittest.mock import AsyncMock, MagicMock

from github.helpers.utils import (
    enrich_with_organization,
    enrich_with_repository,
    parse_github_options,
    enrich_user_with_primary_email,
    get_saml_identities,
)


class TestEnrichWithRepository:
    """Tests for enrich_with_repository function."""

    def test_enrich_with_default_key(self) -> None:
        """Test enriching response with default key."""
        response = {"data": "test"}
        repo_name = "test-repo"

        result = enrich_with_repository(response, repo_name)

        assert result["__repository"] == repo_name
        assert result["data"] == "test"
        assert result is response  # Should modify original dict

    def test_enrich_with_custom_key(self) -> None:
        """Test enriching response with custom key."""
        response = {"data": "test"}
        repo_name = "test-repo"
        custom_key = "repository_info"

        result = enrich_with_repository(response, repo_name, custom_key)

        assert result[custom_key] == repo_name
        assert result["data"] == "test"
        assert "__repository" not in result

    def test_enrich_empty_response(self) -> None:
        """Test enriching empty response."""
        response: Dict[str, Any] = {}
        repo_name = "test-repo"

        result = enrich_with_repository(response, repo_name)

        assert result["__repository"] == repo_name
        assert len(result) == 1

    def test_enrich_overwrites_existing_key(self) -> None:
        """Test that enriching overwrites existing key."""
        response = {"__repository": "old-repo", "data": "test"}
        repo_name = "new-repo"

        result = enrich_with_repository(response, repo_name)

        assert result["__repository"] == repo_name
        assert result["data"] == "test"

    def test_enrich_with_empty_string_repo_name(self) -> None:
        """Test enriching with empty string repo name."""
        response = {"data": "test"}
        repo_name = ""

        result = enrich_with_repository(response, repo_name)

        assert result["__repository"] == ""
        assert result["data"] == "test"


class TestExtractRepoParams:
    """Tests for parse_github_options function."""

    def test_extract_basic_params(self) -> None:
        """Test extracting repo name from basic params."""
        params = {
            "organization": "test-org",
            "repo_name": "test-repo",
            "other_param": "value",
        }

        repo_name, organization, remaining_params = parse_github_options(params)

        assert repo_name == "test-repo"
        assert organization == "test-org"
        assert remaining_params == {"other_param": "value"}
        assert "repo_name" not in remaining_params
        assert "organization" not in remaining_params

    def test_extract_modifies_original_dict(self) -> None:
        """Test that extraction modifies the original dict."""
        params = {
            "organization": "test-org",
            "repo_name": "test-repo",
            "other_param": "value",
        }
        original_params = params.copy()
        original_id = id(params)

        repo_name, organization, remaining_params = parse_github_options(params)

        assert repo_name == original_params["repo_name"]
        assert organization == original_params["organization"]
        assert id(remaining_params) == original_id  # Same dict object
        assert "repo_name" not in params  # Original dict modified
        assert "organization" not in params  # Original dict modified
        assert params == {"other_param": "value"}

    def test_extract_only_repo_name(self) -> None:
        """Test extracting when only repo_name is present."""
        params = {"organization": "test-org", "repo_name": "test-repo"}

        repo_name, organization, remaining_params = parse_github_options(params)

        assert repo_name == "test-repo"
        assert organization == "test-org"
        assert remaining_params == {}

    def test_extract_with_multiple_params(self) -> None:
        """Test extracting with multiple other parameters."""
        params = {
            "organization": "test-org",
            "repo_name": "test-repo",
            "param1": "value1",
            "param2": "value2",
            "param3": 123,
        }

        repo_name, organization, remaining_params = parse_github_options(params)

        assert repo_name == "test-repo"
        assert organization == "test-org"
        assert remaining_params == {
            "param1": "value1",
            "param2": "value2",
            "param3": 123,
        }

    def test_extract_missing_repo_name(self) -> None:
        """Test that missing repo_name raises KeyError."""
        params = {"organization": "test-org", "other_param": "value"}

        repo_name, organization, remaining_params = parse_github_options(params)

        assert repo_name is None
        assert organization == "test-org"
        assert remaining_params == {"other_param": "value"}

    def test_extract_empty_dict(self) -> None:
        """Test that empty dict raises KeyError."""
        params: Dict[str, Any] = {}

        with pytest.raises(KeyError, match="organization"):
            parse_github_options(params)

    def test_extract_with_none_repo_name(self) -> None:
        """Test extracting with None repo name."""
        params = {"organization": "test-org", "repo_name": None, "other_param": "value"}

        repo_name, organization, remaining_params = parse_github_options(params)

        assert repo_name is None
        assert organization == "test-org"
        assert remaining_params == {"other_param": "value"}


class TestEnrichWithOrganization:
    """Tests for enrich_with_organization function."""

    def test_enrich_with_organization(self) -> None:
        """Test enriching response with organization."""
        response = {"data": "test"}
        organization = "test-org"

        result = enrich_with_organization(response, organization)

        assert result["__organization"] == organization
        assert result["data"] == "test"


class DummyClient:
    def __init__(self, base_url: str = "https://api.github.com") -> None:
        self.base_url = base_url
        self.make_request = AsyncMock()


@pytest.mark.asyncio
async def test_enrich_user_with_primary_email_sets_email() -> None:
    client = DummyClient()
    resp = MagicMock()
    resp.json.return_value = [
        {"email": "alt@example.com", "primary": False},
        {"email": "primary@example.com", "primary": True},
    ]
    client.make_request.return_value = resp

    user: Dict[str, Any] = {"login": "alice"}
    result = await enrich_user_with_primary_email(client, user)

    assert result["email"] == "primary@example.com"
    client.make_request.assert_awaited_once_with(f"{client.base_url}/user/emails")


@pytest.mark.asyncio
async def test_enrich_user_with_primary_email_handles_empty_response() -> None:
    client = DummyClient()
    resp = MagicMock()
    resp.json.return_value = []
    client.make_request.return_value = resp

    user: Dict[str, Any] = {"lxxogin": "alice"}
    result = await enrich_user_with_primary_email(client, user)

    # Should return user unchanged when no primary email is found
    assert result == user


class TestEnterpriseSamlFallback:
    """Tests for enterprise SAML fallback in get_saml_identities."""

    @staticmethod
    def _make_saml_edges(
        identities: list[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        return [
            {
                "node": {
                    "user": {"login": login},
                    "samlIdentity": {"nameId": email},
                }
            }
            for login, email in identities
        ]

    @staticmethod
    def _make_client() -> MagicMock:
        client = MagicMock()
        client.base_url = "https://api.github.com/graphql"
        client.send_api_request = AsyncMock()
        client.send_paginated_request = MagicMock()
        return client

    @staticmethod
    async def _null_saml_generator(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Simulates org/enterprise SAML being null (TypeError from _extract_nodes)."""
        raise TypeError("NoneType is not subscriptable")
        yield  # noqa: unreachable - required for AsyncGenerator return type

    @pytest.mark.asyncio
    async def test_org_saml_returns_data_no_enterprise_fallback(self) -> None:
        """When org SAML has data, enterprise is never queried."""
        client = self._make_client()
        org_edges = self._make_saml_edges([("user1", "user1@corp.com")])

        async def mock_org_paginated(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield org_edges

        client.send_paginated_request.return_value = mock_org_paginated()

        result = await get_saml_identities(client, "test-org")

        assert result == {"user1": "user1@corp.com"}
        client.send_api_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_org_saml_empty_falls_back_to_enterprise(self) -> None:
        """When org SAML is null (TypeError), falls back to enterprise."""
        client = self._make_client()
        ent_edges = self._make_saml_edges(
            [
                ("user1", "user1@enterprise.com"),
                ("user2", "user2@enterprise.com"),
            ]
        )

        async def mock_ent_paginated(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield ent_edges

        call_count = 0

        def paginated_side_effect(*args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return self._null_saml_generator()
            return mock_ent_paginated()

        client.send_paginated_request.side_effect = paginated_side_effect
        client.send_api_request.return_value = {
            "data": {
                "viewer": {"enterprises": {"nodes": [{"slug": "test-enterprise"}]}}
            }
        }

        result = await get_saml_identities(client, "test-org")

        assert result == {
            "user1": "user1@enterprise.com",
            "user2": "user2@enterprise.com",
        }
        client.send_api_request.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_enterprise_slug_returns_empty(self) -> None:
        """When org SAML is null and no enterprise found, returns empty."""
        client = self._make_client()

        client.send_paginated_request.return_value = self._null_saml_generator()
        client.send_api_request.return_value = {
            "data": {"viewer": {"enterprises": {"nodes": []}}}
        }

        result = await get_saml_identities(client, "test-org")

        assert result == {}

    @pytest.mark.asyncio
    async def test_enterprise_slug_detected_but_saml_null(self) -> None:
        """Enterprise exists but has no SAML (e.g. OIDC), returns empty."""
        client = self._make_client()

        call_count = 0

        def paginated_side_effect(*args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            return self._null_saml_generator()

        client.send_paginated_request.side_effect = paginated_side_effect
        client.send_api_request.return_value = {
            "data": {
                "viewer": {"enterprises": {"nodes": [{"slug": "oidc-enterprise"}]}}
            }
        }

        result = await get_saml_identities(client, "test-org")

        assert result == {}

    @pytest.mark.asyncio
    async def test_enterprise_slug_api_failure_returns_empty(self) -> None:
        """If viewer.enterprises query fails, gracefully returns empty."""
        client = self._make_client()

        client.send_paginated_request.return_value = self._null_saml_generator()
        client.send_api_request.side_effect = KeyError("data")

        result = await get_saml_identities(client, "test-org")

        assert result == {}

    @pytest.mark.asyncio
    async def test_multiple_enterprises_uses_first(self) -> None:
        """When user belongs to multiple enterprises, uses the first slug."""
        client = self._make_client()
        ent_edges = self._make_saml_edges([("user1", "user1@first.com")])

        async def mock_ent_paginated(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield ent_edges

        call_count = 0

        def paginated_side_effect(*args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return self._null_saml_generator()
            return mock_ent_paginated()

        client.send_paginated_request.side_effect = paginated_side_effect
        client.send_api_request.return_value = {
            "data": {
                "viewer": {
                    "enterprises": {
                        "nodes": [
                            {"slug": "first-enterprise"},
                            {"slug": "second-enterprise"},
                        ]
                    }
                }
            }
        }

        result = await get_saml_identities(client, "test-org")

        assert result == {"user1": "user1@first.com"}

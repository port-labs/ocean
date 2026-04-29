import pytest
from unittest.mock import MagicMock, AsyncMock

from port_ocean.clients.port.mixins.organization import OrganizationClientMixin


@pytest.fixture
async def mocked_org_mixin() -> OrganizationClientMixin:
    auth = MagicMock()
    auth.headers = AsyncMock()
    auth.headers.return_value = {"auth": "enticated"}
    client = MagicMock()
    client.get = AsyncMock()
    client.get.return_value = MagicMock()
    client.get.return_value.json = MagicMock()
    client.get.return_value.json.return_value = {
        "organization": {"id": "org-123", "featureFlags": ["aa", "bb"]}
    }
    client.get.return_value.status_code = 200
    return OrganizationClientMixin(auth=auth, client=client)


async def test_org_feature_flags_should_fetch_proper_json_path(
    mocked_org_mixin: OrganizationClientMixin,
) -> None:
    result = await mocked_org_mixin.get_organization_feature_flags()

    assert result == ["aa", "bb"]


async def test_get_org_id_returns_id_from_organization_response(
    mocked_org_mixin: OrganizationClientMixin,
) -> None:
    result = await mocked_org_mixin.get_org_id()

    assert result == "org-123"


async def test_get_org_id_caches_result_and_calls_api_once(
    mocked_org_mixin: OrganizationClientMixin,
) -> None:
    # Call twice
    result1 = await mocked_org_mixin.get_org_id()
    result2 = await mocked_org_mixin.get_org_id()

    assert result1 == result2 == "org-123"
    # The underlying GET should only have been called once (cached after first call)
    assert mocked_org_mixin.client.get.call_count == 1


async def test_get_org_id_returns_empty_string_when_id_missing(
) -> None:
    auth = MagicMock()
    auth.headers = AsyncMock(return_value={})
    client = MagicMock()
    response = MagicMock()
    response.json = MagicMock(return_value={"organization": {}})
    response.status_code = 200
    client.get = AsyncMock(return_value=response)

    mixin = OrganizationClientMixin(auth=auth, client=client)
    result = await mixin.get_org_id()

    assert result == ""

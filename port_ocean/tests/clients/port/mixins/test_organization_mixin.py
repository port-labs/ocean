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
        "organization": {"featureFlags": ["aa", "bb"]}
    }
    client.get.return_value.status_code = 200
    return OrganizationClientMixin(auth=auth, client=client)


async def test_org_feature_flags_should_fetch_proper_json_path(
    mocked_org_mixin: OrganizationClientMixin,
) -> None:
    result = await mocked_org_mixin.get_organization_feature_flags()

    assert result == ["aa", "bb"]

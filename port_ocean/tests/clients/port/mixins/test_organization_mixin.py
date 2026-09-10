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
        "organization": {
            "id": "org-123",
            "featureFlags": ["aa", "bb"],
            "isBlocked": False,
        }
    }
    client.get.return_value.status_code = 200
    return OrganizationClientMixin(auth=auth, client=client)


async def test_org_feature_flags_should_fetch_proper_json_path(
    mocked_org_mixin: OrganizationClientMixin,
) -> None:
    result = await mocked_org_mixin.get_organization_feature_flags()

    assert result == ["aa", "bb"]


async def test_is_organization_blocked_returns_true_when_org_is_blocked(
    mocked_org_mixin: OrganizationClientMixin,
) -> None:
    mocked_org_mixin.client.get.return_value.json.return_value = {
        "organization": {"id": "org-123", "featureFlags": [], "isBlocked": True}
    }

    result = await mocked_org_mixin.is_organization_blocked()

    assert result is True


async def test_is_organization_blocked_returns_false_when_field_missing(
    mocked_org_mixin: OrganizationClientMixin,
) -> None:
    mocked_org_mixin.client.get.return_value.json.return_value = {
        "organization": {"id": "org-123", "featureFlags": []}
    }

    result = await mocked_org_mixin.is_organization_blocked()

    assert result is False

from typing import Any, cast

import pytest
from unittest.mock import MagicMock, AsyncMock

from port_ocean.clients.port.mixins.organization import OrganizationClientMixin


def _set_organization_response(
    mixin: OrganizationClientMixin, organization: dict[str, Any]
) -> None:
    mock_client = cast(MagicMock, mixin.client)
    mock_client.get.return_value.json.return_value = {"organization": organization}


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
    _set_organization_response(
        mocked_org_mixin,
        {"id": "org-123", "featureFlags": [], "isBlocked": True},
    )

    result = await mocked_org_mixin.is_organization_blocked()

    assert result is True


async def test_is_organization_blocked_returns_false_when_field_missing(
    mocked_org_mixin: OrganizationClientMixin,
) -> None:
    _set_organization_response(
        mocked_org_mixin,
        {"id": "org-123", "featureFlags": []},
    )

    result = await mocked_org_mixin.is_organization_blocked()

    assert result is False


async def test_create_organization_secret_posts_body(
    mocked_org_mixin: OrganizationClientMixin,
) -> None:
    mock_client = cast(MagicMock, mocked_org_mixin.client)
    mock_client.post = AsyncMock(
        return_value=MagicMock(
            status_code=200, json=MagicMock(return_value={"ok": True})
        )
    )
    mocked_org_mixin.auth.api_url = "https://api.example"

    result = await mocked_org_mixin.create_organization_secret(
        secret_name="my-secret",
        secret_value="value",
        description="desc",
    )

    assert result == {"ok": True}
    mock_client.post.assert_awaited_once()
    assert mock_client.post.await_args.kwargs["json"] == {
        "secretName": "my-secret",
        "secretValue": "value",
        "description": "desc",
    }


async def test_update_organization_secret_patches_body(
    mocked_org_mixin: OrganizationClientMixin,
) -> None:
    mock_client = cast(MagicMock, mocked_org_mixin.client)
    mock_client.patch = AsyncMock(
        return_value=MagicMock(
            status_code=200, json=MagicMock(return_value={"ok": True})
        )
    )
    mocked_org_mixin.auth.api_url = "https://api.example"

    result = await mocked_org_mixin.update_organization_secret(
        secret_name="my-secret",
        secret_value="new-value",
    )

    assert result == {"ok": True}
    mock_client.patch.assert_awaited_once()
    assert "/organization/secrets/my-secret" in mock_client.patch.await_args.args[0]
    assert mock_client.patch.await_args.kwargs["json"] == {"secretValue": "new-value"}

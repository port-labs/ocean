from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from azure_integration.helpers.subscription import SubscriptionManager
from tests.helpers import aiter


@pytest.mark.asyncio
async def test_get_all_subscriptions_success() -> None:
    auth_cred = MagicMock()
    auth_cred.create_azure_credential.return_value.close = AsyncMock()
    manager = SubscriptionManager(auth_cred, MagicMock())
    mock_sub = SimpleNamespace(subscription_id="123")

    mock_subs_client = MagicMock()
    mock_subs_client.subscriptions.list = MagicMock(return_value=aiter([mock_sub]))
    mock_subs_client.close = AsyncMock()

    with patch(
        "azure_integration.helpers.subscription.SubscriptionClient",
        return_value=mock_subs_client,
    ):
        async with manager:
            subs = await manager.get_all_subscriptions()
            assert len(subs) == 1
            assert subs[0].subscription_id == "123"


@pytest.mark.asyncio
async def test_get_all_subscriptions_not_initialized() -> None:
    manager = SubscriptionManager(MagicMock(), MagicMock())
    with pytest.raises(ValueError, match="Azure subscription client not initialized"):
        await manager.get_all_subscriptions()


@pytest.mark.asyncio
async def test_get_subscription_batches() -> None:
    auth_cred = MagicMock()
    auth_cred.create_azure_credential.return_value.close = AsyncMock()
    manager = SubscriptionManager(auth_cred, MagicMock(), batch_size=2)
    subscriptions = [
        SimpleNamespace(subscription_id="1"),
        SimpleNamespace(subscription_id="2"),
        SimpleNamespace(subscription_id="3"),
    ]

    mock_subs_client = MagicMock()
    mock_subs_client.close = AsyncMock()

    with patch(
        "azure_integration.helpers.subscription.SubscriptionClient",
        return_value=mock_subs_client,
    ):
        async with manager:
            manager.get_all_subscriptions = AsyncMock(return_value=subscriptions)
            batches = [batch async for batch in manager.get_subscription_batches()]

    assert len(batches) == 2
    assert len(batches[0]) == 2
    assert len(batches[1]) == 1
    assert batches[0][0].subscription_id == "1"
    assert batches[1][0].subscription_id == "3"


@pytest.mark.asyncio
async def test_get_sub_id_in_batches() -> None:
    manager = SubscriptionManager(MagicMock(), MagicMock(), batch_size=2)
    subscriptions = [
        [
            SimpleNamespace(subscription_id="1"),
            SimpleNamespace(subscription_id="2"),
        ],
        [SimpleNamespace(subscription_id="3")],
    ]
    manager.get_subscription_batches = MagicMock(return_value=aiter(subscriptions))

    batches = [batch async for batch in manager.get_sub_id_in_batches()]
    assert len(batches) == 2
    assert batches[0] == ["1", "2"]
    assert batches[1] == ["3"]

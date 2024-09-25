from unittest.mock import AsyncMock, patch
import asyncio
from utils.aws import update_available_access_credentials
from typing import Any


@patch("aws.session_manager.SessionManager.reset", new_callable=AsyncMock)
async def test_update_available_access_credentials(mock_reset: Any) -> None:
    """
    Test to ensure that thundering herd problem is avoided and multiple
    concurrent calls only trigger one session reset.
    """

    result = await update_available_access_credentials()
    mock_reset.assert_called_once()
    assert result

    result_1 = await update_available_access_credentials()
    assert result_1 is True
    mock_reset.assert_called_once()  # No additional calls should be made

    # Thundering herd test
    mock_reset.reset_mock()
    mock_reset.return_value = asyncio.sleep(0.1)

    await asyncio.gather(
        update_available_access_credentials(),
        update_available_access_credentials(),
        update_available_access_credentials(),
    )

    mock_reset.assert_called_once()

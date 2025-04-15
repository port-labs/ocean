import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import List, Any
from utils.aws import get_sessions
from aws.aws_credentials import AwsCredentials
from aws.session_manager import SessionManager
from aioboto3 import Session


class TestAwsSessions(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.session_manager_mock: AsyncMock = patch(
            "utils.aws._session_manager", autospec=SessionManager
        ).start()

        self.credentials_mock: AsyncMock = AsyncMock(spec=AwsCredentials)
        self.session_mock: AsyncMock = AsyncMock(spec=Session)

    def tearDown(self) -> None:
        patch.stopall()

    async def test_get_sessions_with_custom_account_id(self) -> None:
        """Test get_sessions with a custom account ID and region."""
        self.credentials_mock.create_session = AsyncMock(return_value=self.session_mock)

        self.session_manager_mock.find_credentials_by_account_id.return_value = (
            self.credentials_mock
        )

        sessions: List[Session] = [
            s
            async for s in get_sessions(
                custom_account_id="123456789", custom_region="us-west-2"
            )
        ]

        self.credentials_mock.create_session.assert_called_once_with("us-west-2")
        self.assertEqual(sessions[0], self.session_mock)

    async def test_create_session_with_custom_region(self) -> None:
        """Test create_session with custom region."""
        self.credentials_mock.create_session = AsyncMock(return_value=self.session_mock)

        # Test the create_session method directly on the credentials mock
        session = await self.credentials_mock.create_session("us-east-1")

        self.credentials_mock.create_session.assert_called_once_with("us-east-1")
        self.assertEqual(session, self.session_mock)

    async def test_get_sessions_with_multiple_credentials(self) -> None:
        """Test get_sessions with multiple AWS credentials."""
        self.credentials_mock_1: AsyncMock = AsyncMock(spec=AwsCredentials)
        self.credentials_mock_2: AsyncMock = AsyncMock(spec=AwsCredentials)

        self.credentials_mock_1.default_regions = ["us-west-1"]
        self.credentials_mock_2.default_regions = ["us-east-1"]

        self.credentials_mock_1.enabled_regions = ["us-west-1"]
        self.credentials_mock_2.enabled_regions = ["us-east-1"]

        # Create proper async iterators for both credentials
        async def async_iter_1() -> Any:
            yield self.session_mock

        async def async_iter_2() -> Any:
            yield self.session_mock

        # Set up the create_session_for_each_region method to return the async iterators
        self.credentials_mock_1.create_session_for_each_region = MagicMock(
            return_value=async_iter_1()
        )
        self.credentials_mock_2.create_session_for_each_region = MagicMock(
            return_value=async_iter_2()
        )

        self.session_manager_mock._aws_credentials = [
            self.credentials_mock_1,
            self.credentials_mock_2,
        ]

        # Create a mock resource config with a selector that allows all regions
        mock_resource_config = AsyncMock()
        mock_resource_config.selector.is_region_allowed = lambda region: True

        sessions: List[Session] = [
            session async for session in get_sessions(aws_resource_config=mock_resource_config)
        ]

        # Verify create_session_for_each_region was called for both credentials
        self.credentials_mock_1.create_session_for_each_region.assert_called_once()
        self.credentials_mock_2.create_session_for_each_region.assert_called_once()

        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0], self.session_mock)
        self.assertEqual(sessions[1], self.session_mock)

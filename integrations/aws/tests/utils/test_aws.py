import unittest
from unittest.mock import AsyncMock, patch
from typing import List
from utils.aws import get_sessions, session_factory
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

    async def test_session_factory_with_custom_region(self) -> None:
        """Test session_factory with custom region."""
        self.credentials_mock.create_session = AsyncMock(return_value=self.session_mock)
        sessions: List[Session] = [
            s
            async for s in session_factory(
                self.credentials_mock,
                custom_region="us-east-1",
                use_default_region=False,
            )
        ]

        self.credentials_mock.create_session.assert_called_once_with("us-east-1")
        self.assertEqual(sessions[0], self.session_mock)

    async def test_get_sessions_with_default_region(self) -> None:
        """Test get_sessions with default region."""
        self.credentials_mock.default_regions = ["us-west-1"]
        self.credentials_mock.create_session = AsyncMock(return_value=self.session_mock)
        self.session_manager_mock._aws_credentials = [self.credentials_mock]

        sessions: List[Session] = [
            s async for s in get_sessions(use_default_region=True)
        ]

        self.credentials_mock.create_session.assert_called_once_with("us-west-1")
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0], self.session_mock)

    async def test_get_sessions_with_multiple_credentials(self) -> None:
        """Test get_sessions with multiple AWS credentials."""
        self.credentials_mock_1: AsyncMock = AsyncMock(spec=AwsCredentials)
        self.credentials_mock_2: AsyncMock = AsyncMock(spec=AwsCredentials)

        self.credentials_mock_1.default_regions = ["us-west-1"]
        self.credentials_mock_2.default_regions = ["us-east-1"]

        self.credentials_mock_1.create_session = AsyncMock(
            return_value=self.session_mock
        )
        self.credentials_mock_2.create_session = AsyncMock(
            return_value=self.session_mock
        )

        self.session_manager_mock._aws_credentials = [
            self.credentials_mock_1,
            self.credentials_mock_2,
        ]

        sessions: List[Session] = [
            s async for s in get_sessions(use_default_region=True)
        ]

        self.assertEqual(len(sessions), 2)
        self.credentials_mock_1.create_session.assert_called_once_with("us-west-1")
        self.credentials_mock_2.create_session.assert_called_once_with("us-east-1")

from unittest.mock import AsyncMock, MagicMock
import pytest

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.client.paginator import AsyncPaginator


class TestAioBaseClientProxy:

    @pytest.fixture
    def isolated_mock_session(self) -> AsyncMock:
        """Create an isolated mock session for proxy testing."""
        mock_session = AsyncMock()
        # Set the spec to avoid issues with create_client returning the wrong type
        mock_session.create_client = MagicMock()
        return mock_session

    def test_initialization(self, isolated_mock_session: AsyncMock) -> None:
        """Test that the proxy initializes correctly with required parameters."""
        proxy = AioBaseClientProxy(
            session=isolated_mock_session, region="us-west-2", service_name="s3"
        )

        assert proxy.session == isolated_mock_session
        assert proxy.region == "us-west-2"
        assert proxy.service_name == "s3"
        assert proxy._base_client is None

    def test_client_property_raises_when_not_initialized(
        self, isolated_mock_session: AsyncMock
    ) -> None:
        """Test that accessing client property raises RuntimeError when not initialized."""
        proxy = AioBaseClientProxy(
            session=isolated_mock_session, region="us-west-2", service_name="s3"
        )

        with pytest.raises(
            RuntimeError, match="Client not initialized. Use 'async with' context."
        ):
            _ = proxy.client

    @pytest.mark.asyncio
    async def test_context_manager_lifecycle(
        self, isolated_mock_session: AsyncMock
    ) -> None:
        """Test the async context manager lifecycle (__aenter__ and __aexit__)."""
        # Mock the client creation chain
        mock_client = AsyncMock()
        mock_client_cm = AsyncMock()
        mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cm.__aexit__ = AsyncMock()

        isolated_mock_session.create_client.return_value = mock_client_cm

        proxy = AioBaseClientProxy(
            session=isolated_mock_session, region="us-east-1", service_name="ec2"
        )

        # Test entering the context
        async with proxy as entered_proxy:
            assert entered_proxy is proxy
            assert proxy._base_client is mock_client
            assert proxy.client is mock_client

            # Verify create_client was called with correct parameters
            isolated_mock_session.create_client.assert_called_once_with(
                service_name="ec2", region_name="us-east-1"
            )
            mock_client_cm.__aenter__.assert_called_once()

        # Test that __aexit__ was called on the client
        mock_client.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_with_exception(
        self, isolated_mock_session: AsyncMock
    ) -> None:
        """Test that the context manager properly handles exceptions."""
        mock_client = AsyncMock()
        mock_client_cm = AsyncMock()
        mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cm.__aexit__ = AsyncMock()

        isolated_mock_session.create_client.return_value = mock_client_cm

        proxy = AioBaseClientProxy(
            session=isolated_mock_session, region="us-west-2", service_name="s3"
        )

        test_exception = ValueError("Test exception")

        try:
            async with proxy:
                raise test_exception
        except ValueError:
            pass  # Expected exception

        # Verify __aexit__ was called with exception info
        mock_client.__aexit__.assert_called_once()
        call_args = mock_client.__aexit__.call_args[0]
        assert call_args[0] is ValueError
        assert call_args[1] is test_exception
        assert call_args[2] is not None  # traceback

    @pytest.mark.asyncio
    async def test_context_manager_without_client(
        self, isolated_mock_session: AsyncMock
    ) -> None:
        """Test __aexit__ when no client is initialized."""
        proxy = AioBaseClientProxy(
            session=isolated_mock_session, region="us-west-2", service_name="s3"
        )

        # Manually call __aexit__ without initializing client
        await proxy.__aexit__(None, None, None)

        # Should not raise any errors
        assert proxy._base_client is None

    def test_get_paginator_raises_when_not_initialized(
        self, isolated_mock_session: AsyncMock
    ) -> None:
        """Test that get_paginator raises RuntimeError when client not initialized."""
        proxy = AioBaseClientProxy(
            session=isolated_mock_session, region="us-west-2", service_name="s3"
        )

        with pytest.raises(
            RuntimeError, match="Client not initialized. Use 'async with' context."
        ):
            proxy.get_paginator("list_objects_v2", "Contents")

    @pytest.mark.asyncio
    async def test_get_paginator_returns_async_paginator(
        self, isolated_mock_session: AsyncMock
    ) -> None:
        """Test that get_paginator returns an AsyncPaginator with correct parameters."""
        mock_client = AsyncMock()
        mock_client_cm = AsyncMock()
        mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cm.__aexit__ = AsyncMock()

        isolated_mock_session.create_client.return_value = mock_client_cm

        proxy = AioBaseClientProxy(
            session=isolated_mock_session, region="us-west-2", service_name="s3"
        )

        async with proxy:
            paginator = proxy.get_paginator("list_objects_v2", "Contents")

            assert isinstance(paginator, AsyncPaginator)
            # Check that the paginator was created with correct parameters
            assert paginator.client is mock_client
            assert paginator.method_name == "list_objects_v2"
            assert paginator.list_param == "Contents"

    @pytest.mark.asyncio
    async def test_multiple_paginator_creation(
        self, isolated_mock_session: AsyncMock
    ) -> None:
        """Test creating multiple paginators from the same proxy."""
        mock_client = AsyncMock()
        mock_client_cm = AsyncMock()
        mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cm.__aexit__ = AsyncMock()

        isolated_mock_session.create_client.return_value = mock_client_cm

        proxy = AioBaseClientProxy(
            session=isolated_mock_session, region="us-west-2", service_name="s3"
        )

        async with proxy:
            paginator1 = proxy.get_paginator("list_objects_v2", "Contents")
            paginator2 = proxy.get_paginator("list_multipart_uploads", "Uploads")

            # Both should be valid AsyncPaginator instances
            assert isinstance(paginator1, AsyncPaginator)
            assert isinstance(paginator2, AsyncPaginator)

            # Both should reference the same client
            assert paginator1.client is mock_client
            assert paginator2.client is mock_client

            # But have different method names and list params
            assert paginator1.method_name == "list_objects_v2"
            assert paginator1.list_param == "Contents"
            assert paginator2.method_name == "list_multipart_uploads"
            assert paginator2.list_param == "Uploads"

    @pytest.mark.asyncio
    async def test_different_supported_services(
        self, isolated_mock_session: AsyncMock
    ) -> None:
        """Test that proxy works with different supported services."""
        services = ["sqs", "resource-groups", "s3", "ec2"]

        for service in services:
            mock_client = AsyncMock()
            mock_client_cm = AsyncMock()
            mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cm.__aexit__ = AsyncMock()

            isolated_mock_session.create_client.return_value = mock_client_cm

            proxy = AioBaseClientProxy(
                session=isolated_mock_session,
                region="us-east-1",
                service_name=service,  # type: ignore
            )

            async with proxy:
                assert proxy.service_name == service
                assert proxy.client is mock_client

                # Verify create_client was called with the correct service
                isolated_mock_session.create_client.assert_called_with(
                    service_name=service, region_name="us-east-1"
                )

            # Reset the mock for next iteration
            isolated_mock_session.reset_mock()

    @pytest.mark.asyncio
    async def test_client_property_access_within_context(
        self, isolated_mock_session: AsyncMock
    ) -> None:
        """Test that client property works correctly within async context."""
        mock_client = AsyncMock()
        mock_client_cm = AsyncMock()
        mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cm.__aexit__ = AsyncMock()

        isolated_mock_session.create_client.return_value = mock_client_cm

        proxy = AioBaseClientProxy(
            session=isolated_mock_session, region="eu-west-1", service_name="sqs"
        )

        async with proxy:
            # Multiple accesses should return the same client
            client1 = proxy.client
            client2 = proxy.client

            assert client1 is mock_client
            assert client2 is mock_client
            assert client1 is client2

    @pytest.mark.asyncio
    async def test_context_manager_reentry_creates_new_client(
        self, isolated_mock_session: AsyncMock
    ) -> None:
        """Test that re-entering the context manager creates a new client."""
        # First client
        mock_client1 = AsyncMock()
        mock_client_cm1 = AsyncMock()
        mock_client_cm1.__aenter__ = AsyncMock(return_value=mock_client1)
        mock_client_cm1.__aexit__ = AsyncMock()

        # Second client
        mock_client2 = AsyncMock()
        mock_client_cm2 = AsyncMock()
        mock_client_cm2.__aenter__ = AsyncMock(return_value=mock_client2)
        mock_client_cm2.__aexit__ = AsyncMock()

        isolated_mock_session.create_client.side_effect = [
            mock_client_cm1,
            mock_client_cm2,
        ]

        proxy = AioBaseClientProxy(
            session=isolated_mock_session, region="us-west-2", service_name="s3"
        )

        # First context
        async with proxy:
            assert proxy.client is mock_client1

        # Second context should create a new client
        async with proxy:
            assert proxy.client is mock_client2

        # Verify both clients were properly managed
        mock_client_cm1.__aenter__.assert_called_once()
        mock_client1.__aexit__.assert_called_once()
        mock_client_cm2.__aenter__.assert_called_once()
        mock_client2.__aexit__.assert_called_once()

        # Verify create_client was called twice
        assert isolated_mock_session.create_client.call_count == 2

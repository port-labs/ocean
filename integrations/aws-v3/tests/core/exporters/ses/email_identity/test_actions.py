from typing import Any
from unittest.mock import AsyncMock
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.ses.email_identity.actions import (
    EmailIdentityRecord,
    GetEmailIdentityAction,
    ListEmailIdentitiesAction,
    SesEmailIdentityActionsMap,
)
from aws.core.interfaces.action import Action


class TestGetEmailIdentityAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock SESv2 client for testing."""
        mock_client = AsyncMock()
        mock_client.get_email_identity = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetEmailIdentityAction:
        """Create a GetEmailIdentityAction instance for testing."""
        return GetEmailIdentityAction(mock_client)

    def test_inheritance(self, action: GetEmailIdentityAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: GetEmailIdentityAction) -> None:
        """Test that the raw get_email_identity response is returned unchanged, minus ResponseMetadata."""
        domain_fields = {
            "IdentityType": "DOMAIN",
            "FeedbackForwardingStatus": True,
            "VerifiedForSendingStatus": True,
            "DkimAttributes": {"SigningEnabled": True, "Status": "SUCCESS"},
            "MailFromAttributes": {
                "MailFromDomain": "mail.example.com",
                "MailFromDomainStatus": "SUCCESS",
                "BehaviorOnMxFailure": "USE_DEFAULT_VALUE",
            },
            "Policies": {},
            "Tags": [{"Key": "Environment", "Value": "production"}],
            "ConfigurationSetName": "my-config-set",
            "VerificationStatus": "SUCCESS",
            "VerificationInfo": None,
        }
        action.client.get_email_identity.return_value = {
            "ResponseMetadata": {
                "RequestId": "f0a4d20f-1d65-4265-adee-f6ce9d88ae64",
                "HTTPStatusCode": 200,
                "HTTPHeaders": {"content-type": "application/x-amz-json-1.1"},
                "RetryAttempts": 0,
            },
            **domain_fields,
        }

        test_identities: list[EmailIdentityRecord] = [{"IdentityName": "example.com"}]
        result = await action._execute(test_identities)

        assert len(result) == 1
        assert result[0] == domain_fields
        assert "ResponseMetadata" not in result[0]

        action.client.get_email_identity.assert_called_once_with(
            EmailIdentity="example.com"
        )

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: GetEmailIdentityAction) -> None:
        """Test execution with empty identities list."""
        result = await action._execute([])

        assert result == []
        action.client.get_email_identity.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_with_recoverable_exception(
        self, action: GetEmailIdentityAction
    ) -> None:
        """Test execution with recoverable exception preserves an empty placeholder."""
        error = ClientError(
            error_response={"Error": {"Code": "NotFoundException"}},
            operation_name="GetEmailIdentity",
        )
        action.client.get_email_identity.side_effect = error

        test_identities: list[EmailIdentityRecord] = [{"IdentityName": "example.com"}]
        result = await action._execute(test_identities)

        assert result == [{}]
        action.client.get_email_identity.assert_called_once_with(
            EmailIdentity="example.com"
        )

    @pytest.mark.asyncio
    async def test_execute_preserves_index_alignment_with_middle_failure(
        self, action: GetEmailIdentityAction
    ) -> None:
        """Middle identity fails recoverably; results keep aligned positions."""

        def mock_get_email_identity(
            EmailIdentity: str, **kwargs: Any
        ) -> dict[str, Any]:
            if EmailIdentity == "fail.com":
                raise ClientError(
                    error_response={"Error": {"Code": "AccessDenied"}},
                    operation_name="GetEmailIdentity",
                )
            return {
                "IdentityType": "DOMAIN",
                "VerifiedForSendingStatus": True,
                "DkimAttributes": {"SigningEnabled": True},
                "MailFromAttributes": None,
                "Policies": None,
                "ConfigurationSetName": None,
                "VerificationStatus": "SUCCESS",
                "VerificationInfo": None,
            }

        action.client.get_email_identity.side_effect = mock_get_email_identity

        identities: list[EmailIdentityRecord] = [
            {"IdentityName": "first.com"},
            {"IdentityName": "fail.com"},
            {"IdentityName": "third.com"},
        ]

        result = await action._execute(identities)

        assert len(result) == 3
        assert result[0]["IdentityType"] == "DOMAIN"
        assert result[1] == {}
        assert result[2]["IdentityType"] == "DOMAIN"

    @pytest.mark.asyncio
    async def test_execute_with_non_recoverable_exception(
        self, action: GetEmailIdentityAction
    ) -> None:
        """Test execution with non-recoverable exception."""
        error = ClientError(
            error_response={"Error": {"Code": "InternalServerError"}},
            operation_name="GetEmailIdentity",
        )
        action.client.get_email_identity.side_effect = error

        test_identities: list[EmailIdentityRecord] = [{"IdentityName": "example.com"}]

        with pytest.raises(ClientError):
            await action._execute(test_identities)


class TestListEmailIdentitiesAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock SESv2 client for testing."""
        return AsyncMock()

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListEmailIdentitiesAction:
        """Create a ListEmailIdentitiesAction instance for testing."""
        return ListEmailIdentitiesAction(mock_client)

    def test_inheritance(self, action: ListEmailIdentitiesAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: ListEmailIdentitiesAction) -> None:
        """Test that raw list_email_identities items are returned unchanged."""
        test_identities: list[EmailIdentityRecord] = [
            {
                "IdentityName": "example.com",
                "IdentityType": "DOMAIN",
                "SendingEnabled": True,
                "VerificationStatus": "SUCCESS",
            },
            {
                "IdentityName": "user@example.com",
                "IdentityType": "EMAIL_ADDRESS",
                "SendingEnabled": False,
                "VerificationStatus": "PENDING",
            },
        ]

        result = await action._execute(test_identities)

        assert result == test_identities

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: ListEmailIdentitiesAction) -> None:
        """Test execution with empty identities list."""
        result = await action._execute([])
        assert result == []


class TestSesEmailIdentityActionsMap:

    def test_defaults_include_required_actions(self) -> None:
        """Test that the defaults list contains the required actions."""
        actions_map = SesEmailIdentityActionsMap()
        assert ListEmailIdentitiesAction in actions_map.defaults
        assert GetEmailIdentityAction in actions_map.defaults

    def test_no_options(self) -> None:
        """Test that there are no optional actions (Tags already come from GetEmailIdentityAction)."""
        actions_map = SesEmailIdentityActionsMap()
        assert actions_map.options == []

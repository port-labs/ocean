from typing import Any
from unittest.mock import AsyncMock
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.ses.email_identity.actions import (
    GetEmailIdentityAction,
    ListEmailIdentityTagsAction,
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
        """Test successful execution of get_email_identity."""
        expected_response = {
            "IdentityType": "DOMAIN",
            "VerifiedForSendingStatus": True,
            "DkimEnabled": True,
            "DkimAttributes": {"SigningEnabled": True, "Status": "SUCCESS"},
            "MailFromAttributes": {
                "MailFromDomain": "mail.example.com",
                "MailFromDomainStatus": "SUCCESS",
                "BehaviorOnMxFailure": "USE_DEFAULT_VALUE",
            },
            "Policies": {},
            "ConfigurationSetName": "my-config-set",
            "VerificationStatus": "SUCCESS",
            "VerificationInfo": None,
        }
        action.client.get_email_identity.return_value = expected_response

        test_identities = [{"EmailIdentity": "example.com"}]
        result = await action._execute(test_identities)

        assert len(result) == 1
        assert result[0]["IdentityType"] == "DOMAIN"
        assert result[0]["VerifiedForSendingStatus"] is True
        assert result[0]["DkimEnabled"] is True
        assert result[0]["VerificationStatus"] == "SUCCESS"
        assert result[0]["ConfigurationSetName"] == "my-config-set"

        action.client.get_email_identity.assert_called_once_with(
            EmailIdentity="example.com"
        )

    @pytest.mark.asyncio
    async def test_execute_empty_list(
        self, action: GetEmailIdentityAction
    ) -> None:
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

        test_identities = [{"EmailIdentity": "example.com"}]
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
                "DkimEnabled": True,
                "DkimAttributes": None,
                "MailFromAttributes": None,
                "Policies": None,
                "ConfigurationSetName": None,
                "VerificationStatus": "SUCCESS",
                "VerificationInfo": None,
            }

        action.client.get_email_identity.side_effect = mock_get_email_identity

        identities = [
            {"EmailIdentity": "first.com"},
            {"EmailIdentity": "fail.com"},
            {"EmailIdentity": "third.com"},
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

        test_identities = [{"EmailIdentity": "example.com"}]

        with pytest.raises(ClientError):
            await action._execute(test_identities)


class TestListEmailIdentityTagsAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock SESv2 client for testing."""
        mock_client = AsyncMock()
        mock_client.list_tags_for_resource = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListEmailIdentityTagsAction:
        """Create a ListEmailIdentityTagsAction instance for testing."""
        return ListEmailIdentityTagsAction(mock_client)

    def test_inheritance(self, action: ListEmailIdentityTagsAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(
        self, action: ListEmailIdentityTagsAction
    ) -> None:
        """Test successful execution of list_tags_for_resource."""
        expected_response = {
            "Tags": [
                {"Key": "Environment", "Value": "production"},
                {"Key": "Team", "Value": "platform"},
            ]
        }
        action.client.list_tags_for_resource.return_value = expected_response

        test_identities = [
            {
                "EmailIdentity": "example.com",
                "IdentityArn": "arn:aws:ses:us-east-1:123456789012:identity/example.com",
            }
        ]
        result = await action._execute(test_identities)

        assert len(result) == 1
        assert len(result[0]["Tags"]) == 2
        assert result[0]["Tags"][0]["Key"] == "Environment"

    @pytest.mark.asyncio
    async def test_execute_no_tags(
        self, action: ListEmailIdentityTagsAction
    ) -> None:
        """Test execution with no tags."""
        action.client.list_tags_for_resource.return_value = {"Tags": []}

        test_identities = [
            {
                "EmailIdentity": "example.com",
                "IdentityArn": "arn:aws:ses:us-east-1:123456789012:identity/example.com",
            }
        ]
        result = await action._execute(test_identities)

        assert len(result) == 1
        assert result[0]["Tags"] == []

    @pytest.mark.asyncio
    async def test_execute_with_recoverable_exception(
        self, action: ListEmailIdentityTagsAction
    ) -> None:
        """Test execution with recoverable exception preserves an empty placeholder."""
        error = ClientError(
            error_response={"Error": {"Code": "AccessDenied"}},
            operation_name="ListTagsForResource",
        )
        action.client.list_tags_for_resource.side_effect = error

        test_identities = [
            {
                "EmailIdentity": "example.com",
                "IdentityArn": "arn:aws:ses:us-east-1:123456789012:identity/example.com",
            }
        ]
        result = await action._execute(test_identities)

        assert result == [{}]

    @pytest.mark.asyncio
    async def test_execute_with_non_recoverable_exception(
        self, action: ListEmailIdentityTagsAction
    ) -> None:
        """Test execution with non-recoverable exception."""
        error = ClientError(
            error_response={"Error": {"Code": "InternalServerError"}},
            operation_name="ListTagsForResource",
        )
        action.client.list_tags_for_resource.side_effect = error

        test_identities = [
            {
                "EmailIdentity": "example.com",
                "IdentityArn": "arn:aws:ses:us-east-1:123456789012:identity/example.com",
            }
        ]

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
    async def test_execute_success(
        self, action: ListEmailIdentitiesAction
    ) -> None:
        """Test successful execution returns identities as-is."""
        test_identities = [
            {"EmailIdentity": "example.com", "IdentityType": "DOMAIN"},
            {
                "EmailIdentity": "user@example.com",
                "IdentityType": "EMAIL_ADDRESS",
            },
        ]

        result = await action._execute(test_identities)

        assert len(result) == 2
        assert result[0]["EmailIdentity"] == "example.com"
        assert result[1]["EmailIdentity"] == "user@example.com"

    @pytest.mark.asyncio
    async def test_execute_empty_list(
        self, action: ListEmailIdentitiesAction
    ) -> None:
        """Test execution with empty identities list."""
        result = await action._execute([])
        assert result == []


class TestSesEmailIdentityActionsMap:

    def test_defaults_include_required_actions(self) -> None:
        """Test that the defaults list contains the required actions."""
        actions_map = SesEmailIdentityActionsMap()
        assert ListEmailIdentitiesAction in actions_map.defaults
        assert GetEmailIdentityAction in actions_map.defaults

    def test_options_include_tag_action(self) -> None:
        """Test that the options list contains the tag action."""
        actions_map = SesEmailIdentityActionsMap()
        assert ListEmailIdentityTagsAction in actions_map.options

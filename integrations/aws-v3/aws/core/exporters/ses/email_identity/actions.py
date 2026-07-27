from typing import Any, Type
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import execute_concurrent_aws_operations


class GetEmailIdentityAction(Action[list[dict[str, Any]]]):
    """Fetches detailed information for SES email identities."""

    async def _execute(
        self, identities: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=identities,
            operation_func=self._fetch_email_identity,
            get_resource_identifier=lambda identity: identity.get(
                "EmailIdentity", "unknown"
            ),
            operation_name="email identity details",
        )

    async def _fetch_email_identity(
        self, identity: dict[str, Any]
    ) -> dict[str, Any]:
        response = await self.client.get_email_identity(
            EmailIdentity=identity["EmailIdentity"]
        )
        return {
            "IdentityType": response.get("IdentityType"),
            "VerifiedForSendingStatus": response.get("VerifiedForSendingStatus"),
            "DkimEnabled": response.get("DkimEnabled"),
            "DkimAttributes": response.get("DkimAttributes"),
            "MailFromAttributes": response.get("MailFromAttributes"),
            "Policies": response.get("Policies"),
            "ConfigurationSetName": response.get("ConfigurationSetName"),
            "VerificationStatus": response.get("VerificationStatus"),
            "VerificationInfo": response.get("VerificationInfo"),
        }


class ListEmailIdentityTagsAction(Action[list[dict[str, Any]]]):
    """Fetches tags for SES email identities."""

    async def _execute(
        self, identities: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=identities,
            operation_func=self._fetch_email_identity_tags,
            get_resource_identifier=lambda identity: identity.get(
                "EmailIdentity", "unknown"
            ),
            operation_name="email identity tags",
        )

    async def _fetch_email_identity_tags(
        self, identity: dict[str, Any]
    ) -> dict[str, Any]:
        response = await self.client.list_tags_for_resource(
            ResourceArn=identity.get("IdentityArn", "")
        )
        return {"Tags": response.get("Tags", [])}


class ListEmailIdentitiesAction(Action[list[dict[str, Any]]]):
    """Processes the initial list of email identities from AWS."""

    async def _execute(
        self, identities: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Return email identities as-is from the list response."""
        return identities


class SesEmailIdentityActionsMap(ActionMap[list[dict[str, Any]]]):
    """Groups all actions for SES email identities."""

    defaults: list[Type[Action[list[dict[str, Any]]]]] = [
        ListEmailIdentitiesAction,
        GetEmailIdentityAction,
    ]
    options: list[Type[Action[list[dict[str, Any]]]]] = [
        ListEmailIdentityTagsAction,
    ]

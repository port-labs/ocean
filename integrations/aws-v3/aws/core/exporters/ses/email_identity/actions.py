from typing import Any, Type
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import execute_concurrent_aws_operations


class GetEmailIdentityAction(Action[list[dict[str, Any]]]):
    """Fetches detailed information for SES email identities."""

    async def _execute(self, identities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=identities,
            operation_func=self._fetch_email_identity,
            get_resource_identifier=lambda identity: identity.get(
                "IdentityName", "unknown"
            ),
            operation_name="email identity details",
        )

    async def _fetch_email_identity(self, identity: dict[str, Any]) -> dict[str, Any]:
        response = await self.client.get_email_identity(
            EmailIdentity=identity["IdentityName"]
        )
        response.pop("ResponseMetadata", None)
        return response


class ListEmailIdentitiesAction(Action[list[dict[str, Any]]]):
    """Processes the initial list of email identities from AWS."""

    async def _execute(self, identities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return email identities as-is from the list response."""
        return identities


class SesEmailIdentityActionsMap(ActionMap[list[dict[str, Any]]]):
    """Groups all actions for SES email identities."""

    defaults: list[Type[Action[list[dict[str, Any]]]]] = [
        ListEmailIdentitiesAction,
        GetEmailIdentityAction,
    ]
    options: list[Type[Action[list[dict[str, Any]]]]] = []

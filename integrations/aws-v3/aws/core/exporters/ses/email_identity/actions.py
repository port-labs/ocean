from typing import Any, NotRequired, Type, TypedDict
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import execute_concurrent_aws_operations


class EmailIdentityRecord(TypedDict):
    """Identity record actions operate on.

    ``IdentityName`` is always present, whether sourced from a single
    ``get_resource`` call or from a ``list_email_identities`` page. The rest
    are only present when sourced from ``list_email_identities``.
    """

    IdentityName: str
    IdentityType: NotRequired[str]
    SendingEnabled: NotRequired[bool]
    VerificationStatus: NotRequired[str]


class GetEmailIdentityAction(Action[list[EmailIdentityRecord]]):
    """Fetches detailed information for SES email identities."""

    async def _execute(
        self, identities: list[EmailIdentityRecord]
    ) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=identities,
            operation_func=self._fetch_email_identity,
            get_resource_identifier=lambda identity: identity.get(
                "IdentityName", "unknown"
            ),
            operation_name="email identity details",
        )

    async def _fetch_email_identity(
        self, identity: EmailIdentityRecord
    ) -> dict[str, Any]:
        response = await self.client.get_email_identity(
            EmailIdentity=identity["IdentityName"]
        )
        response.pop("ResponseMetadata", None)
        return response


class ListEmailIdentitiesAction(Action[list[EmailIdentityRecord]]):
    """Processes the initial list of email identities from AWS."""

    async def _execute(
        self, identities: list[EmailIdentityRecord]
    ) -> list[dict[str, Any]]:
        """Return email identities as-is from the list response."""
        return identities  # type: ignore[return-value]


class SesEmailIdentityActionsMap(ActionMap[list[EmailIdentityRecord]]):
    """Groups all actions for SES email identities."""

    defaults: list[Type[Action[list[EmailIdentityRecord]]]] = [
        ListEmailIdentitiesAction,
        GetEmailIdentityAction,
    ]
    options: list[Type[Action[list[EmailIdentityRecord]]]] = []

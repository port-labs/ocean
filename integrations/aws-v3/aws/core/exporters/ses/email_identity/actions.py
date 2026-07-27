from typing import Any, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception
from loguru import logger
import asyncio


class GetEmailIdentityDetailsAction(Action[list[str]]):
    """Fetches detailed information about SES email identities."""

    async def _execute(self, identities: list[str]) -> list[dict[str, Any]]:
        details = await asyncio.gather(
            *(self._fetch_identity_details(identity) for identity in identities),
            return_exceptions=True,
        )

        results: list[dict[str, Any]] = []
        success_count = 0
        for idx, detail_result in enumerate(details):
            if isinstance(detail_result, Exception):
                identity = identities[idx]
                if is_recoverable_aws_exception(detail_result):
                    logger.warning(
                        f"Skipping email identity details for '{identity}': {detail_result}"
                    )
                    results.append({})
                    continue
                else:
                    logger.error(
                        f"Error fetching email identity details for '{identity}': {detail_result}"
                    )
                    raise detail_result
            results.append(cast(dict[str, Any], detail_result))
            success_count += 1
        logger.info(
            f"Successfully fetched details for {success_count} SES email identities"
        )
        return results

    async def _fetch_identity_details(self, identity: str) -> dict[str, Any]:
        response = await self.client.get_email_identity(EmailIdentity=identity)
        logger.info(f"Successfully fetched details for email identity '{identity}'")

        return {
            "EmailIdentity": identity,
            "IdentityType": response.get("IdentityType"),
            "FeedbackForwardingStatus": response.get("FeedbackForwardingStatus"),
            "VerifiedForSendingStatus": response.get("VerifiedForSendingStatus"),
            "DkimAttributes": response.get("DkimAttributes"),
            "MailFromAttributes": response.get("MailFromAttributes"),
            "Policies": response.get("Policies"),
            "Tags": response.get("Tags"),
            "ConfigurationSetName": response.get("ConfigurationSetName"),
        }


class ListEmailIdentitiesAction(Action[list[str]]):
    """Processes the initial list of SES email identities."""

    async def _execute(self, identities: list[str]) -> list[dict[str, Any]]:
        """Return identities wrapped in dictionaries."""
        return [{"EmailIdentity": identity} for identity in identities]


class SesEmailIdentityActionsMap(ActionMap[list[str]]):
    """Groups all actions for SES email identities."""

    defaults: list[Type[Action[list[str]]]] = [
        ListEmailIdentitiesAction,
        GetEmailIdentityDetailsAction,
    ]
    options: list[Type[Action[list[str]]]] = []

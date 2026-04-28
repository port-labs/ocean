from abc import abstractmethod
from typing import Any, Optional, cast
from github.webhook.events import COLLABORATOR_EVENTS, TEAM_COLLABORATOR_EVENTS
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent
from port_ocean.context.event import event
from github.clients.client_factory import create_github_client
from github.core.exporters.repository_exporter import RestRepositoryExporter
from github.core.options import ListRepositoryOptions
from github.helpers.models import RepoSearchParams
from github.webhook.webhook_processors.github_abstract_webhook_processor import (
    _GithubAbstractWebhookProcessor,
)
from integration import GithubPortAppConfig, RepoSearchSelector
from loguru import logger


class BaseRepositoryWebhookProcessor(_GithubAbstractWebhookProcessor):
    async def validate_payload(self, payload: EventPayload) -> bool:
        return (
            await super().validate_payload(payload)
            and await self.validate_repository_payload(payload)
            and await self._validate_payload(payload)
        )

    @abstractmethod
    async def _validate_payload(self, payload: EventPayload) -> bool: ...

    async def should_process_repo_search(
        self, payload: EventPayload, config: ResourceConfig
    ) -> bool:
        repo_search = cast(RepoSearchSelector, config.selector).repo_search

        if repo_search is not None:
            logger.info(
                "search query is configured for this kind, checking if repository is in matched results."
            )
            if await self.repo_in_search(payload, config) is None:
                logger.info(
                    "Repository is not matched by search query, no actions will be performed."
                )
                return False
        return True

    async def repo_in_search(
        self, payload: EventPayload, config: ResourceConfig
    ) -> Optional[dict[str, Any]]:
        configured_visibility = cast(
            GithubPortAppConfig, event.port_app_config
        ).repository_type
        selector = cast(RepoSearchSelector, config.selector)
        organization = self.get_webhook_payload_organization(payload)
        repo = payload["repository"]

        if selector.repo_search is None:
            return repo

        return await self._search_repository_by_query(
            selector.repo_search.query,
            repo,
            organization["login"],
            configured_visibility,
        )

    async def _search_repository_by_query(
        self,
        query: str,
        repo: dict[str, Any],
        organization_login: str,
        configured_visibility: str,
    ) -> Optional[dict[str, Any]]:
        # This search is designed to match exactly one repo and would not paginate through many
        targeted_query = f"{query} AND {repo['name']} in:name"

        search_options = ListRepositoryOptions(
            type=configured_visibility,
            organization=organization_login,
            organization_type="Organization",
            search_params=RepoSearchParams(query=targeted_query),
        )
        rest_client = create_github_client()
        exporter = RestRepositoryExporter(rest_client)
        async for search_results in exporter.get_paginated_resources(search_options):
            for repository in search_results:
                if repository["id"] == repo["id"]:
                    logger.info(
                        f"repository {repository['name']} found in search query, webhook will be processed."
                    )
                    return repository
        return None

    def should_filter_by_visibility(self) -> bool:
        """
        By default, repository-based processors respect visibility filtering.
        Subclasses may override this.
        """
        return True

    async def validate_repository_payload(self, payload: EventPayload) -> bool:
        repository = payload.get("repository", {})
        if not repository.get("name"):
            return False

        if not self.should_filter_by_visibility():
            return True

        repository_visibility = repository.get("visibility")

        return (
            repository_visibility is not None
            and await self.validate_repository_visibility(repository_visibility)
        )

    async def validate_repository_visibility(self, repository_visibility: str) -> bool:
        configured_visibility = cast(
            GithubPortAppConfig, event.port_app_config
        ).repository_type

        logger.debug(
            f"Validating repository webhook for repository with visibility '{repository_visibility}' against configured filter '{configured_visibility}'"
        )

        return (
            configured_visibility == "all"
            or repository_visibility == configured_visibility
        )


class CollaboratorEventValidator:

    async def validate_member_collaborator_payload(self, payload: EventPayload) -> bool:
        has_required_fields = not ({"action", "repository", "member"} - payload.keys())

        return has_required_fields and "login" in payload.get("member", {})

    async def should_process_member_collaborator_event(
        self, event: WebhookEvent
    ) -> bool:
        return (
            event.headers.get("x-github-event") == "member"
            and event.payload.get("action") in COLLABORATOR_EVENTS
        )

    async def validate_membership_collaborator_payload(
        self, payload: EventPayload
    ) -> bool:

        has_required_fields = not (
            {"action", "organization", "team", "member"} - payload.keys()
        )

        has_org_login = "login" in payload.get("organization", {})
        has_team_name = "name" in payload.get("team", {})
        has_member_login = "login" in payload.get("member", {})

        return (
            has_required_fields and has_org_login and has_team_name and has_member_login
        )

    async def should_process_membership_collaborator_event(
        self, event: WebhookEvent
    ) -> bool:
        return (
            event.headers.get("x-github-event") == "membership"
            and event.payload.get("action") in COLLABORATOR_EVENTS
        )

    async def validate_team_collaborator_payload(self, payload: EventPayload) -> bool:

        has_required_fields = not (
            {"action", "repository", "organization", "team"} - payload.keys()
        )

        has_org_login = "login" in payload.get("organization", {})
        has_team_name = "name" in payload.get("team", {})

        return has_required_fields and has_org_login and has_team_name

    async def should_process_team_collaborator_event(self, event: WebhookEvent) -> bool:
        return (
            event.headers.get("x-github-event") == "team"
            and event.payload.get("action") in TEAM_COLLABORATOR_EVENTS
        )

    async def should_process_collaborator_event(self, event: WebhookEvent) -> bool:
        match event.headers.get("x-github-event"):
            case "member":
                return await self.should_process_member_collaborator_event(
                    event
                ) and await self.validate_member_collaborator_payload(event.payload)
            case "membership":
                return await self.should_process_membership_collaborator_event(
                    event
                ) and await self.validate_membership_collaborator_payload(event.payload)
            case "team":
                return await self.should_process_team_collaborator_event(
                    event
                ) and await self.validate_team_collaborator_payload(event.payload)
            case _:
                return False

from typing import Any, Dict, Optional

from github.clients.client_factory import create_github_client
from github.core.exporters.collaborator_exporter import RestCollaboratorExporter
from github.core.options import ListCollaboratorOptions
from github.helpers.utils import (
    ObjectKind,
    enrich_with_organization,
    enrich_with_repository,
)
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)


class BaseCollaboratorWebhookProcessor(BaseRepositoryWebhookProcessor):
    async def affiliation_matches(
        self,
        *,
        organization: str,
        repo_name: str,
        username: str,
        affiliation: str,
        repo_collaborators_cache: Optional[Dict[str, set[str]]] = None,
    ) -> bool:
        """
        Check whether `username` is returned from the repo collaborators endpoint
        using GitHub's `affiliation` filter.
        """
        if affiliation == "all":
            return True

        cache = repo_collaborators_cache if repo_collaborators_cache is not None else {}
        cache_key = f"{organization}/{repo_name}:{affiliation}"

        if cache_key not in cache:
            rest_client = create_github_client()
            exporter = RestCollaboratorExporter(rest_client)
            logins: set[str] = set()
            async for batch in exporter.get_paginated_resources(
                ListCollaboratorOptions(
                    organization=organization,
                    repo_name=repo_name,
                    affiliation=affiliation,
                )
            ):
                for collaborator in batch:
                    login = collaborator.get("login")
                    if login:
                        logins.add(login)
            cache[cache_key] = logins

        return username in cache[cache_key]

    def collaborator_delete_payload(
        self,
        *,
        organization: str,
        repo_name: str,
        repository: dict[str, Any],
        username: str,
        user_id: Any,
    ) -> dict[str, Any]:
        return enrich_with_organization(
            enrich_with_repository(
                {"login": username, "id": user_id},
                repo_name,
                repo=repository,
            ),
            organization,
        )

    def collaborator_delete_result(
        self,
        *,
        organization: str,
        repo_name: str,
        repository: dict[str, Any],
        username: str,
        user_id: Any,
    ) -> WebhookEventRawResults:
        data_to_delete = self.collaborator_delete_payload(
            organization=organization,
            repo_name=repo_name,
            repository=repository,
            username=username,
            user_id=user_id,
        )
        return WebhookEventRawResults(
            updated_raw_results=[],
            deleted_raw_results=[data_to_delete],
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.COLLABORATOR]

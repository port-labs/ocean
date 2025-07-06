from loguru import logger
from github.core.exporters.collaborator_exporter import RestCollaboratorExporter
from github.core.exporters.team_exporter import RestTeamExporter
from github.webhook.events import (
    COLLABORATOR_DELETE_EVENTS,
    COLLABORATOR_UPSERT_EVENTS,
    COLLABORATOR_EVENTS,
    TEAM_COLLABORATOR_EVENTS,
)
from github.helpers.utils import ObjectKind
from github.clients.client_factory import create_github_client
from github.webhook.webhook_processors.github_abstract_webhook_processor import (
    _GithubAbstractWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from github.core.options import SingleCollaboratorOptions, SingleTeamOptions
from github.helpers.utils import enrich_collaborators_with_repositories


class CollaboratorWebhookProcessor(_GithubAbstractWebhookProcessor):
    _event_name: str | None = None

    EVENT_VALIDATION_FIELDS = {
        "member": {"action", "repository", "member"},
        "membership": {"action", "repository", "organization", "team", "member"},
        "team": {"action", "repository", "organization", "team"},
    }

    async def validate_payload(self, payload: EventPayload) -> bool:
        if self._event_name is None:
            return False

        required_fields = self.EVENT_VALIDATION_FIELDS.get(self._event_name)
        if not required_fields:
            return False

        if not required_fields.issubset(payload.keys()):
            return False

        has_org_login = "login" in payload.get("organization", {})
        has_team_name = "name" in payload.get("team", {})
        has_member_login = "login" in payload.get("member", {})

        if (
            self._event_name != "membership"
            and not await super().validate_repository_payload(payload)
        ):
            return False

        match self._event_name:
            case "member":
                return has_member_login
            case "membership":
                return has_org_login and has_team_name and has_member_login
            case "team":
                return has_org_login and has_team_name
            case _:
                return False

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        self._event_name = event.headers.get("x-github-event")

        is_valid_event = self._event_name in self.EVENT_VALIDATION_FIELDS.keys()
        is_valid_action = False

        if self._event_name == "team":
            is_valid_action = event.payload.get("action") in TEAM_COLLABORATOR_EVENTS
        else:
            is_valid_action = event.payload.get("action") in COLLABORATOR_EVENTS

        return is_valid_event and is_valid_action

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.COLLABORATOR]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:

        action = payload["action"]
        repository = payload["repository"]
        repo_name = repository["name"]

        if self._event_name == "team":
            username = payload["organization"]["login"]
        else:
            username = payload["member"]["login"]

        logger.info(f"Processing member event: {action} for {username} in {repo_name}")

        if action in COLLABORATOR_DELETE_EVENTS:
            logger.info(
                f"Collaborator {username} was removed from repository {repo_name}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[username]
            )

        rest_client = create_github_client()
        exporter = RestCollaboratorExporter(rest_client)

        data_to_upsert = await exporter.get_resource(
            SingleCollaboratorOptions(repo_name=repo_name, username=username)
        )
        if self._event_name == "membership" and action in COLLABORATOR_UPSERT_EVENTS:
            team_slug = payload["team"]["slug"]
            team_exporter = RestTeamExporter(rest_client)

            repositories = []
            async for batch in team_exporter.get_team_repositories_by_slug(
                SingleTeamOptions(slug=team_slug)
            ):
                repositories.extend(batch)

            list_data_to_upsert = enrich_collaborators_with_repositories(
                data_to_upsert, repositories
            )

            return WebhookEventRawResults(
                updated_raw_results=list_data_to_upsert, deleted_raw_results=[]
            )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )

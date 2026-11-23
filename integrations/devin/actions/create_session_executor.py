import time
from typing import Any

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from pydantic import Field

from actions.abstract_action_input import AbstractDevinActionInput
from actions.abstract_executor import AbstractDevinExecutor
from actions.exceptions import DevinApiError
from actions.utils import ensure_no_reserved_tags, merge_config
from core.tracking.run_output import started_output
from core.tracking.tags import MANAGED_TAG, build_external_id, tracking_tags
from integration import ObjectKind

CREATING_STATUS_LABEL = "Creating session"
SESSION_RUNNING_STATUS_LABEL = "Session running"
SESSION_CREATED_STATUS_LABEL = "Session created"


class CreateSessionInputs(AbstractDevinActionInput):
    prompt: str = Field(min_length=1)
    playbookId: str | None = None
    repos: list[str] | None = None
    knowledgeIds: list[str] | None = None
    secretIds: list[str] | None = None
    tags: list[str] = Field(default_factory=list)
    maxAcuLimit: int | None = None
    structuredOutputSchema: dict[str, Any] | None = None
    createAsUserId: str | None = None
    reportCompletion: bool = True
    config: dict[str, Any] | None = None

    def to_api_body(self, *, tags: list[str]) -> dict[str, Any]:
        return merge_config(
            self.config,
            {
                "prompt": self.prompt,
                "playbook_id": self.playbookId,
                "repos": self.repos,
                "knowledge_ids": self.knowledgeIds,
                "secret_ids": self.secretIds,
                "max_acu_limit": self.maxAcuLimit,
                "structured_output_schema": self.structuredOutputSchema,
                "create_as_user_id": self.createAsUserId,
                "tags": tags,
            },
        )


class CreateSessionExecutor(AbstractDevinExecutor):
    """Executor for the `create_session` action.

    With `reportCompletion`, every tracking tag is written in the create call
    itself (the external ID only needs the Port run ID), so there is no window
    in which a session exists that the `SessionTracker` cannot find. The run is
    then left in progress for the tracker to complete.

    New sessions are independent, so runs have no partition key.
    """

    ACTION_NAME = "create_session"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = CreateSessionInputs.from_execution_properties(run.execution_properties)
        user_tags = list(inputs.tags)
        ensure_no_reserved_tags(user_tags)

        await ocean.port_client.post_run_log(
            run,
            "Creating a Devin session",
            status_label=CREATING_STATUS_LABEL,
            should_raise=False,
        )

        external_id = build_external_id(run.id)
        sent_at = int(time.time())
        tags = [MANAGED_TAG, *dict.fromkeys(user_tags)]
        if inputs.reportCompletion:
            tags.extend(
                tracking_tags(ocean.config.integration.identifier, external_id, sent_at)
            )

        try:
            session = await self.sessions.create(inputs.to_api_body(tags=tags))
        except httpx.HTTPError as error:
            raise DevinApiError.from_http_error(
                error, "Failed to create the Devin session"
            ) from error

        logger.info(
            f"Created Devin session {session.session_id} for run {run.id}",
            session_id=session.session_id,
            external_id=external_id,
        )
        await ocean.port_client.post_run_log(
            run, f"Devin session started: {session.url}", should_raise=False
        )
        await ocean.port_client.update_run_started(
            run,
            session.url,
            external_id,
            extra_output=started_output(session, sent_at),
            status_label=SESSION_RUNNING_STATUS_LABEL,
        )
        await self.register_entity(ObjectKind.SESSION, session.raw(), run)

        if not inputs.reportCompletion:
            await ocean.port_client.report_run_completed(
                run,
                True,
                f"Devin session created: {session.url}",
                status_label=SESSION_CREATED_STATUS_LABEL,
            )

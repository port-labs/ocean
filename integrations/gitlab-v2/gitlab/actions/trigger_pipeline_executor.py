import json
from typing import Any

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import ActionRun, WorkflowNodeRun

from gitlab.actions.abstract_gitlab_executor import AbstractGitlabExecutor
from gitlab.actions.utils import build_external_id
from gitlab.webhook.webhook_processors.trigger_pipeline_webhook_processor import (
    TriggerPipelineWebhookProcessor,
)


class TriggerPipelineExecutor(AbstractGitlabExecutor):
    ACTION_NAME = "trigger_pipeline"
    WEBHOOK_PROCESSOR_CLASS = TriggerPipelineWebhookProcessor
    WEBHOOK_PATH = "/hook/{group_id}"

    async def _get_partition_key(self, run: ActionRun | WorkflowNodeRun) -> str | None:
        return run.execution_properties.get("project")

    async def execute(self, run: ActionRun | WorkflowNodeRun) -> None:
        project = run.execution_properties.get("project")
        ref = run.execution_properties.get("ref")

        if not (project and ref):
            raise Exception("project and ref are required")

        raw_variables: dict[str, Any] = run.execution_properties.get(
            "pipelineVariables", {}
        )
        variables = [
            {"key": k, "value": v if isinstance(v, str) else json.dumps(v)}
            for k, v in raw_variables.items()
        ]

        try:
            pipeline = await self.client.trigger_pipeline(project, ref, variables)
        except httpx.HTTPStatusError as e:
            try:
                message = e.response.json().get("message", str(e))
            except Exception:
                message = str(e)
            raise Exception(f"Failed to trigger pipeline: {message}")

        external_id = build_external_id(pipeline["project_id"], pipeline["id"])
        await ocean.port_client.update_run_started(
            run,
            pipeline["web_url"],
            external_id,
        )
        logger.info(
            f"Pipeline {pipeline['id']} triggered for project {project} on ref {ref}",
            pipeline_id=pipeline["id"],
            project=project,
            ref=ref,
            external_id=external_id,
        )

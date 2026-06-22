import json

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import ActionRun, WorkflowNodeRun

from gitlab.actions.abstract_gitlab_executor import AbstractGitlabExecutor
from gitlab.actions.utils import build_external_id
from gitlab.helpers.exceptions import (
    GitlabTriggerPipelineError,
    MissingExecutionPropertyError,
)
from gitlab.webhook.webhook_processors.trigger_pipeline_webhook_processor import (
    TriggerPipelineWebhookProcessor,
)


class TriggerPipelineExecutor(AbstractGitlabExecutor):
    ACTION_NAME = "trigger_pipeline"
    WEBHOOK_PROCESSOR_CLASS = TriggerPipelineWebhookProcessor
    WEBHOOK_PATH = "/hook/{group_id}"

    async def execute(self, run: ActionRun | WorkflowNodeRun) -> None:
        project = run.execution_properties.get("project")
        ref = run.execution_properties.get("ref")

        if not project:
            raise MissingExecutionPropertyError("project is required")
        if not ref:
            raise MissingExecutionPropertyError("ref is required")

        raw_variables = run.execution_properties.get("pipelineVariables") or {}
        if not isinstance(raw_variables, dict):
            raise MissingExecutionPropertyError(
                f"pipelineVariables must be a key-value object, got {type(raw_variables).__name__}"
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
            raise GitlabTriggerPipelineError(f"Failed to trigger pipeline: {message}")

        if not pipeline or not all(
            k in pipeline for k in ("id", "project_id", "web_url")
        ):
            raise GitlabTriggerPipelineError(
                "Failed to trigger pipeline: GitLab returned an empty or incomplete response"
            )

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

        if not run.execution_properties.get("reportPipelineStatus", True):
            logger.info(
                f"reportPipelineStatus is disabled for run {run.id}, completing run immediately"
            )
            await ocean.port_client.report_run_completed(
                run, True, "Pipeline triggered successfully"
            )

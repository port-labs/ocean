from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

from actions.abstract_executor import AbstractCursorExecutor
from actions.config_validation import (
    API_VERSION_V0,
    parse_api_version,
    validate_report_completion_policy,
)
from actions.request_bodies import parse_v0_create_body, parse_v1_create_body
from actions.exceptions import InvalidActionParametersException
from actions.utils import (
    build_agent_link,
    build_v0_launch_body,
    build_v1_create_body,
    build_webhook_config,
    build_webhook_url,
)
from clients.endpoints import V0_AGENTS, V1_AGENTS
from clients.run_reads import list_first_runs_page
from core.webhook_signing import derive_webhook_secret
from integration import ObjectKind


class CreateAgentExecutor(AbstractCursorExecutor):
    """Executor for the `create_agent` action.

    Launches a new Cursor cloud agent with its initial prompt. Cursor's create
    endpoints always start a run and billable work immediately - there is no
    config-only create. v1 create requires `repository`, `config.repos`, or
    `config.env` in the merged request body (Port policy). v0 source requirements
    are enforced by Cursor.

    `apiVersion` selects the Cursor create endpoint (`v0` or `v1`). On v0,
    `reportCompletion` optionally attaches a webhook and leaves the Port run
    `IN_PROGRESS` until `CursorAgentWebhookProcessor` concludes it. On v1,
    the Port run always completes immediately after launch (`reportCompletion`
    is rejected - v1 has no webhooks).
    """

    ACTION_NAME = "create_agent"

    async def execute(self, run: IntegrationRun) -> None:
        props = run.execution_properties

        repository = props.get("repository")
        ref = props.get("ref")
        pr_url = props.get("prUrl")
        auto_create_pr = props.get("autoCreatePr")

        api_version = parse_api_version(props.get("apiVersion"))
        report_completion = bool(props.get("reportCompletion", False))

        config = props.get("config")
        if config is None:
            config = {}
        elif not isinstance(config, dict):
            raise InvalidActionParametersException("config must be an object")

        model = props.get("model")

        validate_report_completion_policy(api_version, report_completion)

        if api_version == API_VERSION_V0:
            await self._launch_v0(
                run,
                props.get("prompt"),
                repository,
                ref,
                pr_url,
                model,
                auto_create_pr,
                config,
                track_completion=report_completion,
            )
        else:
            await self._create_v1(
                run,
                props.get("prompt"),
                repository,
                ref,
                pr_url,
                model,
                auto_create_pr,
                config,
            )

    async def _launch_v0(
        self,
        run: IntegrationRun,
        prompt: str | None,
        repository: str | None,
        ref: str | None,
        pr_url: str | None,
        model: object | None,
        auto_create_pr: bool | None,
        config: dict[str, object],
        *,
        track_completion: bool,
    ) -> None:
        body = build_v0_launch_body(
            prompt=prompt,
            repository=repository,
            ref=ref,
            pr_url=pr_url,
            model=model,
            auto_create_pr=auto_create_pr,
            webhook=None,
            config=config,
        )
        parse_v0_create_body(body, report_completion=track_completion)

        if track_completion:
            webhook_url = build_webhook_url(run.id)
            if webhook_url is None:
                raise InvalidActionParametersException(
                    "reportCompletion requires a reachable public URL (OCEAN__BASE_URL)"
                )
            body["webhook"] = build_webhook_config(
                webhook_url, await derive_webhook_secret(run.id)
            )

        try:
            agent = await self.client.send_api_request(
                "POST", V0_AGENTS, json_body=body
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to launch Cursor agent: {error}"
            ) from error

        agent_id = agent.get("id")
        if not agent_id:
            raise ActionExecutionError(
                "Cursor agent was launched but no id was returned"
            )

        logger.info(
            f"Launched Cursor agent {agent_id} (v0, "
            f"{'tracked' if track_completion else 'fire-and-forget'}) for run {run.id}"
        )

        # Reflect the new agent in the catalog via the `agent` kind mapping.
        # Best-effort: never fails the run.
        await self.register_entity(ObjectKind.AGENT, agent, run)
        try:
            runs = await list_first_runs_page(self.client, agent_id)
        except Exception as error:
            logger.warning(
                f"Failed to list runs for Cursor agent {agent_id} after v0 launch "
                f"(catalog run upsert skipped): {error}"
            )
            runs = []
        if runs:
            run_raw = dict(runs[0])
            run_raw.setdefault("agentId", agent_id)
            await self.register_entity(ObjectKind.RUN, run_raw, run)

        if isinstance(run, WorkflowNodeRun):
            run.output["agentId"] = agent_id
            run.output["status"] = agent.get("status")

        if track_completion:
            await ocean.port_client.update_run_started(
                run,
                build_agent_link(self.client.get_console_host(), agent_id),
                agent_id,
                extra_output={"agentId": agent_id},
            )
        else:
            await ocean.port_client.report_run_completed(
                run, True, f"Launched agent {agent_id}"
            )

    async def _create_v1(
        self,
        run: IntegrationRun,
        prompt: str | None,
        repository: str | None,
        ref: str | None,
        pr_url: str | None,
        model: object | None,
        auto_create_pr: bool | None,
        config: dict[str, object],
    ) -> None:
        body = build_v1_create_body(
            prompt=prompt,
            repository=repository,
            ref=ref,
            pr_url=pr_url,
            model=model,
            auto_create_pr=auto_create_pr,
            config=config,
        )
        parse_v1_create_body(body)
        try:
            response = await self.client.send_api_request(
                "POST", V1_AGENTS, json_body=body
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to create Cursor agent: {error}"
            ) from error

        agent = response.get("agent") or {}
        run_obj = response.get("run") or {}
        agent_id = agent.get("id")
        run_id = run_obj.get("id")
        if not agent_id:
            raise ActionExecutionError(
                "Cursor agent was created but no id was returned"
            )

        logger.info(f"Created Cursor agent {agent_id} (v1) for run {run.id}")

        await self.register_entity(ObjectKind.AGENT, agent, run)
        if run_id:
            run_raw = dict(run_obj)
            run_raw.setdefault("agentId", agent_id)
            await self.register_entity(ObjectKind.RUN, run_raw, run)

        if isinstance(run, WorkflowNodeRun):
            run.output["agentId"] = agent_id
            run.output["runId"] = run_id
            run.output["url"] = agent.get("url")

        await ocean.port_client.report_run_completed(
            run, True, f"Created agent {agent_id}"
        )

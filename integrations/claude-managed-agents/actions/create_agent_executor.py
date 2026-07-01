from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import ActionRun, WorkflowNodeRun

from actions.abstract_executor import AbstractAnthropicExecutor
from integration import ObjectKind


class CreateAgentExecutor(AbstractAnthropicExecutor):
    """Executor for the `create_agent` action.

    Creates a Claude managed agent, reflects it into the catalog (if the `agent`
    kind is mapped), and completes the run synchronously - there is no async
    webhook for agent creation.
    """

    ACTION_NAME = "create_agent"

    async def execute(self, run: ActionRun | WorkflowNodeRun) -> None:
        props = run.execution_properties
        name = props.get("name")
        model = props.get("model")
        if not (name and model):
            raise ValueError("name and model are required")

        system = props.get("systemPrompt")
        extra = props.get("config")
        if extra is None:
            extra = {}
        elif not isinstance(extra, dict):
            raise ValueError("config must be an object")

        try:
            agent = await self.client.create_agent(
                name=name, model=model, system=system, extra=extra
            )
        except Exception as error:
            logger.error(f"Failed to create Claude agent for run {run.id}: {error}")
            await ocean.port_client.report_run_completed(
                run, False, f"Failed to create agent: {error}"
            )
            return

        agent_id = agent.get("id")
        logger.info(f"Created Claude agent {agent_id} for run {run.id}")

        # Reflect the new agent in the catalog via the existing `agent` kind
        # mapping. Agents have no webhook events, so without this the entity would
        # not appear until the next resync. Best-effort: never fails the run.
        await self.register_entity(ObjectKind.AGENT, agent)

        await ocean.port_client.report_run_completed(
            run, True, f"Created agent {agent_id}"
        )

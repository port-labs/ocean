from typing import Dict, Any, Optional

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from spacelift.client import SpaceliftClient


class SpaceLiftIntegration:
    def __init__(self) -> None:
        self.client: Optional[SpaceliftClient] = None

    async def initialize_client(self) -> SpaceliftClient:
        """Initialize the Spacelift client with proper authentication and configuration."""
        if not self.client:
            logger.info("Initializing Spacelift client")
            self.client = SpaceliftClient()
            await self.client.initialize()
            logger.info("Spacelift client initialized successfully")
        return self.client


integration = SpaceLiftIntegration()


@ocean.on_start()
async def on_start() -> None:
    """Initialize the integration when Ocean starts."""
    logger.info("Starting Spacelift integration")
    await integration.initialize_client()
    logger.success("Spacelift integration started successfully")


@ocean.on_resync()
async def on_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Handle resync events for all supported resource kinds."""
    logger.info(f"Starting resync for kind: {kind}")

    client = await integration.initialize_client()

    match kind:
        case "space":
            logger.info("Resyncing Spacelift spaces")
            async for spaces_batch in client.get_spaces():
                logger.info(f"Received {len(spaces_batch)} spaces")
                yield spaces_batch
        case "stack":
            logger.info("Resyncing Spacelift stacks")
            async for stacks_batch in client.get_stacks():
                logger.info(f"Received {len(stacks_batch)} stacks")
                yield stacks_batch
        case "deployment":
            logger.info("Resyncing Spacelift deployments")
            async for deployments_batch in client.get_deployments():
                logger.info(f"Received {len(deployments_batch)} deployments")
                yield deployments_batch
        case "policy":
            logger.info("Resyncing Spacelift policies")
            async for policies_batch in client.get_policies():
                logger.info(f"Received {len(policies_batch)} policies")
                yield policies_batch
        case "user":
            logger.info("Resyncing Spacelift users")
            async for users_batch in client.get_users():
                logger.info(f"Received {len(users_batch)} users")
                yield users_batch
        case _:
            logger.warning(f"Unknown resource kind: {kind}")


@ocean.router.post("/webhook")
async def handle_webhook(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle real-time webhook events from Spacelift."""
    logger.info(f"Received webhook event: {body.get('event_type', 'unknown')}")

    event_type = body.get("event_type")

    if event_type == "run_state_changed_event":
        run_data = body.get("run", {})
        if run_data.get("type") == "TRACKED":
            logger.info(
                f"Processing deployment state change for run: {run_data.get('id')}"
            )

            deployment = {
                "id": run_data.get("id"),
                "stack_id": body.get("stack", {}).get("id"),
                "state": body.get("state"),
                "type": run_data.get("type"),
                "branch": run_data.get("branch"),
                "commit": run_data.get("commit", {}),
                "createdAt": run_data.get("createdAt"),
                "delta": run_data.get("delta", {}),
                "triggeredBy": run_data.get("triggeredBy"),
                "url": run_data.get("url"),
            }
            await ocean.register_raw("deployment", [deployment])

    elif event_type == "stack_updated_event":
        stack_data = body.get("stack", {})
        logger.info(f"Processing stack update for: {stack_data.get('id')}")
        await ocean.register_raw("stack", [stack_data])

    else:
        logger.debug(f"Unhandled webhook event type: {event_type}")

    return {"ok": True}

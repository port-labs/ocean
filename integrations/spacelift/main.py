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


@ocean.on_resync(kind="space")
async def on_resync_spaces(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Handle resync events for Spacelift spaces."""
    logger.info("Starting resync for Spacelift spaces")
    client = await integration.initialize_client()
    
    async for spaces_batch in client.get_spaces():
        logger.info(f"Received {len(spaces_batch)} spaces")
        yield spaces_batch


@ocean.on_resync(kind="stack")
async def on_resync_stacks(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Handle resync events for Spacelift stacks."""
    logger.info("Starting resync for Spacelift stacks")
    client = await integration.initialize_client()
    
    async for stacks_batch in client.get_stacks():
        logger.info(f"Received {len(stacks_batch)} stacks")
        yield stacks_batch


@ocean.on_resync(kind="deployment")
async def on_resync_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Handle resync events for Spacelift deployments."""
    logger.info("Starting resync for Spacelift deployments")
    client = await integration.initialize_client()
    
    async for deployments_batch in client.get_deployments():
        logger.info(f"Received {len(deployments_batch)} deployments")
        yield deployments_batch


@ocean.on_resync(kind="policy")
async def on_resync_policies(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Handle resync events for Spacelift policies."""
    logger.info("Starting resync for Spacelift policies")
    client = await integration.initialize_client()
    
    async for policies_batch in client.get_policies():
        logger.info(f"Received {len(policies_batch)} policies")
        yield policies_batch


@ocean.on_resync(kind="user")
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Handle resync events for Spacelift users."""
    logger.info("Starting resync for Spacelift users")
    client = await integration.initialize_client()
    
    async for users_batch in client.get_users():
        logger.info(f"Received {len(users_batch)} users")
        yield users_batch


@ocean.on_resync()
async def on_resync_global(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Handle resync events for undefined resource kinds."""
    logger.warning(f"Received resync request for undefined resource kind: {kind}")
    logger.info(f"Supported resource kinds are: space, stack, deployment, policy, user")
    yield []


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

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


def _safe_get_nested_value(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely get nested value from dictionary with fallback to default."""
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def _validate_webhook_payload(body: Dict[str, Any], event_type: str) -> bool:
    """Validate webhook payload structure based on event type."""
    if event_type == "run_state_changed_event":
        # Check for required fields
        if not body.get("run"):
            logger.warning("Missing 'run' field in run_state_changed_event payload")
            return False
        if not body.get("stack"):
            logger.warning("Missing 'stack' field in run_state_changed_event payload")
            return False
        return True
    elif event_type == "stack_updated_event":
        if not body.get("stack"):
            logger.warning("Missing 'stack' field in stack_updated_event payload")
            return False
        return True
    return True


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
    logger.info("Supported resource kinds are: space, stack, deployment, policy, user")
    yield []


async def _handle_webhook_logic(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle real-time webhook events from Spacelift - testable business logic."""
    logger.info(f"Received webhook event: {body.get('event_type', 'unknown')}")

    event_type = body.get("event_type")
    
    if not event_type:
        logger.warning("Received webhook without event_type field")
        return {"ok": False, "error": "missing event_type"}

    # Validate payload structure
    if not _validate_webhook_payload(body, event_type):
        logger.warning(f"Invalid webhook payload structure for event type: {event_type}")
        return {"ok": False, "error": "invalid payload structure"}

    if event_type == "run_state_changed_event":
        run_data = body.get("run", {})
        stack_data = body.get("stack", {})
        
        if run_data.get("type") == "TRACKED":
            logger.info(
                f"Processing deployment state change for run: {run_data.get('id')}"
            )

            # Safely extract commit data with validation
            commit_data = run_data.get("commit", {})
            if not isinstance(commit_data, dict):
                logger.warning("Invalid commit data structure, using empty dict")
                commit_data = {}

            # Safely extract delta data with validation
            delta_data = run_data.get("delta", {})
            if not isinstance(delta_data, dict):
                logger.warning("Invalid delta data structure, using empty dict")
                delta_data = {}

            deployment = {
                "id": run_data.get("id"),
                "stack_id": stack_data.get("id"),
                "state": body.get("state"),
                "type": run_data.get("type"),
                "branch": run_data.get("branch"),
                "commit": {
                    "hash": commit_data.get("hash"),
                    "message": commit_data.get("message"),
                    "authorName": commit_data.get("authorName"),
                },
                "createdAt": run_data.get("createdAt"),
                "delta": {
                    "created": delta_data.get("created", 0),
                    "updated": delta_data.get("updated", 0),
                    "deleted": delta_data.get("deleted", 0),
                },
                "triggeredBy": run_data.get("triggeredBy"),
                "url": run_data.get("url"),
            }
            await ocean.register_raw("deployment", [deployment])

    elif event_type == "stack_updated_event":
        stack_data = body.get("stack", {})
        if not isinstance(stack_data, dict):
            logger.warning("Invalid stack data structure, skipping event")
            return {"ok": False, "error": "invalid stack data"}
            
        logger.info(f"Processing stack update for: {stack_data.get('id')}")
        await ocean.register_raw("stack", [stack_data])

    else:
        logger.debug(f"Unhandled webhook event type: {event_type}")

    return {"ok": True}


@ocean.router.post("/webhook")
async def handle_webhook(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handle real-time webhook events from Spacelift."""
    return await _handle_webhook_logic(body)

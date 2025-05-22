import os
import asyncio
import pickle
from loguru import logger
from port_ocean.clients.port.types import UserAgentType
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from port_ocean.context.ocean import ocean
from port_ocean.context.event import event


def run_task(
    id: str,
    resource: ResourceConfig,
    index: int,
    user_agent_type: UserAgentType,
) -> None:
    resource_dir = f"/tmp/{id}"
    os.makedirs(resource_dir, exist_ok=True)
    with open(f"{resource_dir}/status", "w") as f:
        f.write("started")
    logger.info(f"process started successfully for {resource.kind} with index {index}")

    async def task():
        result = await ocean.integration._process_resource(
            resource, index, user_agent_type
        )
        with open(f"{resource_dir}/result.pkl", "wb") as f:
            pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
        with open(f"{resource_dir}/status", "w") as f:
            f.write("finished")
        with open(f"{resource_dir}/topological_entities.pkl", "wb") as f:
            pickle.dump(
                event.entity_topological_sorter.entities,
                f,
                protocol=pickle.HIGHEST_PROTOCOL,
            )

    asyncio.run(task())
    logger.info(f"Process finished for {resource.kind} with index {index}")

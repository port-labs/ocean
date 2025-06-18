from port_ocean.context.ocean import ocean
from .client import SpaceliftClient
from .config import SpaceliftConfig

class SpaceliftLoader:
    def __init__(self, context: ocean):
        self.context = context
        self.cfg = SpaceliftConfig()
        self.client = SpaceliftClient(self.cfg)

    async def run(self):
        await self.client.authenticate()
        query = """
        query {
          stacks {
            id
            name
            description
          }
        }
        """
        data = await self.client.query(query)
        stacks = data.get("stacks", [])

        for stack in stacks:
            print(f"Ingesting stack: {stack['name']}")
            await self.context.port_client.write_entity(
                kind="spacelift-stack",
                resource_id=stack["id"],
                properties={
                    "name": stack["name"],
                    "description": stack.get("description", "")
                }
            )
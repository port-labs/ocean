from typing import Any, Dict, List, AsyncGenerator

from .data_clients import SpacelifDataClients


class SpacelifClient(SpacelifDataClients):
    """Main Spacelift client that combines all functionality."""

    async def initialize(self) -> None:
        """Initialize the client and authenticate."""
        await super().initialize()

    async def get_spaces(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get all spaces with pagination."""
        async for spaces_batch in super().get_spaces():
            yield spaces_batch

    async def get_stacks(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get all stacks with pagination."""
        async for stacks_batch in super().get_stacks():
            yield stacks_batch

    async def get_deployments(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get all deployments (tracked runs) with pagination."""
        async for deployments_batch in super().get_deployments():
            yield deployments_batch

    async def get_policies(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get all policies."""
        async for policies_batch in super().get_policies():
            yield policies_batch

    async def get_users(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get all users."""
        async for users_batch in super().get_users():
            yield users_batch

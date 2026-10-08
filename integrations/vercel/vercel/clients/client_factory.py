"""Factory for creating Vercel API clients."""

from port_ocean.context.ocean import ocean

from vercel.clients.http.vercel_client import VercelClient


def create_vercel_client() -> VercelClient:
    """Build a VercelClient from the current Ocean integration configuration."""
    cfg = ocean.integration_config
    return VercelClient(
        token=cfg["token"],
        team_id=cfg.get("teamId") or None,
    )

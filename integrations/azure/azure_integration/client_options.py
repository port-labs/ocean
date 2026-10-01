"""Optional overrides for Azure management and Entra authority.

When ``azure_management_base_url`` / ``azure_authority_host`` are unset (the normal
production case), management clients use the Azure SDK defaults (public ARM and
Entra). Load tests and private-cloud setups set these via integration config or
``OCEAN__INTEGRATION__CONFIG__*`` env vars to point at a mock or alternate host.
"""

from __future__ import annotations

import contextlib
import os
from typing import Any, AsyncIterator

from azure.core.credentials import AccessToken
from azure.core.credentials_async import AsyncTokenCredential
from azure.core.pipeline import PipelineRequest
from azure.core.pipeline.policies import SansIOHTTPPolicy
from azure.identity.aio import DefaultAzureCredential
from loguru import logger
from port_ocean.context.ocean import ocean


class _AllowInsecureArmHttpPolicy(SansIOHTTPPolicy):
    """Let bearer auth run against http:// ARM mocks (load tests only)."""

    def on_request(self, request: PipelineRequest) -> None:
        request.context.options["enforce_https"] = False


def azure_management_base_url() -> str | None:
    raw = ocean.integration_config.get("azure_management_base_url")
    if raw:
        return str(raw).rstrip("/")
    env = os.environ.get("OCEAN__INTEGRATION__CONFIG__AZURE_MANAGEMENT_BASE_URL", "").strip()
    return env.rstrip("/") if env else None


def azure_mgmt_client_kwargs() -> dict[str, Any]:
    base = azure_management_base_url()
    if not base:
        return {}
    kwargs: dict[str, Any] = {"base_url": base}
    if base.lower().startswith("http://"):
        kwargs["per_call_policies"] = [_AllowInsecureArmHttpPolicy()]
    return kwargs


def apply_azure_authority_host_from_config() -> None:
    raw = ocean.integration_config.get("azure_authority_host")
    if not raw:
        raw = os.environ.get("OCEAN__INTEGRATION__CONFIG__AZURE_AUTHORITY_HOST", "").strip()
    if not raw:
        return
    value = str(raw).rstrip("/")
    if value.lower().startswith("http://"):
        logger.warning(
            "Ignoring azure_authority_host {} — Entra authority must be https; "
            "load tests use a static token when azure_management_base_url is set",
            value,
        )
        return
    os.environ["AZURE_AUTHORITY_HOST"] = value


class _LoadTestAzureCredential(AsyncTokenCredential):
    """Static token for ARM mocks that do not validate JWTs."""

    async def __aenter__(self) -> _LoadTestAzureCredential:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get_token(self, *scopes: str, **kwargs: Any) -> AccessToken:
        return AccessToken(token="mock-load-test-token", expires_on=9999999999)


@contextlib.asynccontextmanager
async def azure_async_credential() -> AsyncIterator[AsyncTokenCredential]:
    """DefaultAzureCredential in production; static token when ARM base URL is overridden."""
    if azure_management_base_url():
        async with _LoadTestAzureCredential() as credential:
            yield credential
    else:
        async with DefaultAzureCredential() as credential:
            yield credential

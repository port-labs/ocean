"""Read-only vault client for the ``port`` vault type (SaaS identity propagation).

Exchanges the caller's identity JWT for a downstream access token via
``POST /v1/identity-propagation/token``.  Caches per identity token (which is
unique per node run) so integrations that resolve the token twice in one run
do not trigger a second exchange.
"""

from port_ocean.context.ocean import ocean
from port_ocean.exceptions.identity_propagation import (
    UserAuthRequiredError,
    VaultError,
)
from port_ocean.identity_propagation.vault.base import TokenRecord, VaultClient
from port_ocean.utils import http_async_client

EXCHANGE_PATH = "/v1/identity-propagation/token"
REAUTH_REQUIRED_RESULT = "reauth_required"


class PortExchangeVaultClient(VaultClient):
    """Stateless, read-only vault backed by Port's identity-propagation API.

    Before calling ``read``, the caller must set the current run's identity
    token via ``set_identity_token``.  ``write`` is a no-op - the server
    owns the grants store.
    """

    def __init__(self) -> None:
        super().__init__()
        self._cache: dict[str, TokenRecord] = {}
        self._identity_token: str | None = None

    def set_identity_token(self, token: str) -> None:
        self._identity_token = token

    async def read(self, org_id: str, actor_id: str, target: str) -> TokenRecord | None:
        if self._identity_token is None:
            raise VaultError(
                "PortExchangeVaultClient requires an identity token; "
                "call set_identity_token before read"
            )

        cached = self._cache.get(self._identity_token)
        if cached is not None and not cached.is_expired():
            return cached

        record = await self._exchange(self._identity_token)
        if record is not None:
            self._cache[self._identity_token] = record
        return record

    async def write(
        self, org_id: str, actor_id: str, target: str, record: TokenRecord
    ) -> None:
        pass

    async def _exchange(self, identity_token: str) -> TokenRecord | None:
        base_url = str(ocean.config.port.base_url).rstrip("/")
        url = f"{base_url}{EXCHANGE_PATH}"

        headers = {
            **await ocean.port_client.auth.headers(),
            "x-port-identity-token": identity_token,
        }

        try:
            response = await http_async_client.post(url, headers=headers)
            body = response.json()
        except Exception as e:
            raise VaultError(f"Exchange request failed: {e}") from e

        if body.get("result") == REAUTH_REQUIRED_RESULT:
            raise UserAuthRequiredError()

        if response.status_code >= 400:
            raise VaultError(
                f"Exchange returned {response.status_code}: "
                f"{body.get('message', 'unknown error')}"
            )

        access_token = body.get("accessToken")
        if not access_token:
            raise VaultError("Exchange response carried no accessToken")

        expires_at = body.get("expiresAt")
        return TokenRecord(
            access_token=access_token,
            expires_at=int(expires_at) if expires_at is not None else None,
        )

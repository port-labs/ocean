"""Port API helpers."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from scripts.utils.ssl import SslConfig


def trigger_port_resync(
    client_id: str,
    client_secret: str,
    *,
    port_base_url: str,
    integration_identifier: str,
    ssl_config: SslConfig | None = None,
) -> None:
    """Trigger an integration resync via the Port API."""
    config = ssl_config or SslConfig()
    api_base = f"{port_base_url.rstrip('/')}/v1"

    auth_request = urllib.request.Request(
        f"{api_base}/auth/access_token",
        data=json.dumps({"clientId": client_id, "clientSecret": client_secret}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            auth_request, timeout=60, context=config.create_context()
        ) as response:
            access_token = json.loads(response.read().decode())["accessToken"]
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Failed to authenticate with Port API: {error}") from error

    resync_request = urllib.request.Request(
        f"{api_base}/integration/{integration_identifier}",
        data=b"{}",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(
            resync_request, timeout=60, context=config.create_context()
        ) as response:
            response.read()
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"Failed to trigger Port resync for integration {integration_identifier}: {error}"
        ) from error

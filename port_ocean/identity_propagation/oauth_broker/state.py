import base64
import hashlib
import hmac
import json
import time
from typing import Any

from pydantic.v1 import BaseModel

from port_ocean.context.ocean import ocean
from port_ocean.exceptions.base import BaseOceanException

STATE_TTL_SECONDS = 600
# Domain separator, so the derived key cannot collide with any other use of the
# Port client secret.
_HMAC_KEY_INFO = b"port-ocean-oauth-state"


class InvalidStateError(BaseOceanException):
    pass


class OAuthState(BaseModel):
    run_id: str
    node_run_id: str
    actor_id: str
    org_id: str
    target: str
    exp: int


def _signing_key() -> bytes:
    custom = ocean.config.identity_propagation.oauth.state_signing_secret
    raw_secret = custom if custom else ocean.config.port.client_secret
    return hmac.new(
        raw_secret.encode(), _HMAC_KEY_INFO, hashlib.sha256
    ).digest()


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def sign_state(
    run_id: str,
    node_run_id: str,
    actor_id: str,
    org_id: str,
    target: str,
    ttl_seconds: int = STATE_TTL_SECONDS,
) -> str:
    payload = OAuthState(
        run_id=run_id,
        node_run_id=node_run_id,
        actor_id=actor_id,
        org_id=org_id,
        target=target,
        exp=int(time.time()) + ttl_seconds,
    )
    encoded = _b64encode(payload.json(sort_keys=True).encode())
    signature = hmac.new(_signing_key(), encoded.encode(), hashlib.sha256).digest()
    return f"{encoded}.{_b64encode(signature)}"


def verify_state(state: str) -> OAuthState:
    """Return the payload of an authentic, unexpired state, or raise."""
    encoded, _, signature = state.partition(".")
    if not encoded or not signature:
        raise InvalidStateError("Malformed state")

    expected = hmac.new(_signing_key(), encoded.encode(), hashlib.sha256).digest()
    try:
        provided = _b64decode(signature)
    except Exception as e:
        raise InvalidStateError("Malformed state signature") from e

    if not hmac.compare_digest(expected, provided):
        raise InvalidStateError("State signature mismatch")

    try:
        payload: dict[str, Any] = json.loads(_b64decode(encoded))
        parsed = OAuthState.parse_obj(payload)
    except Exception as e:
        raise InvalidStateError("Malformed state payload") from e

    if parsed.exp <= int(time.time()):
        raise InvalidStateError("State has expired")

    return parsed

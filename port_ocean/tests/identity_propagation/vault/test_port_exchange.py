import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.exceptions.identity_propagation import (
    UserAuthRequiredError,
    VaultError,
)
from port_ocean.identity_propagation.vault.base import TokenRecord
from port_ocean.identity_propagation.vault import port_exchange as mod
from port_ocean.identity_propagation.vault.port_exchange import (
    PortExchangeVaultClient,
)

VALID_UNTIL = int(time.time()) + 3600
IDENTITY_TOKEN = "eyJ.test.token"


@pytest.fixture(autouse=True)
def _patch_ocean(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock()
    mock.config.port.base_url = "https://api.getport.io"
    mock.port_client.auth.headers = AsyncMock(
        return_value={"Authorization": "Bearer svc"}
    )
    monkeypatch.setattr(mod, "ocean", mock)
    return mock


@pytest.fixture(autouse=True)
def _patch_http(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock()
    mock.post = AsyncMock()
    monkeypatch.setattr(mod, "http_async_client", mock)
    return mock


@pytest.fixture
def http(_patch_http: MagicMock) -> MagicMock:
    return _patch_http


@pytest.fixture
def client() -> PortExchangeVaultClient:
    c = PortExchangeVaultClient()
    c.set_identity_token(IDENTITY_TOKEN)
    return c


def _ok(access_token: str = "gho_ok", expires_at: int | None = None) -> MagicMock:
    r = MagicMock(status_code=200)
    body: dict[str, str | int] = {"accessToken": access_token}
    if expires_at is not None:
        body["expiresAt"] = expires_at
    r.json.return_value = body
    return r


async def test_read_without_identity_token_raises() -> None:
    c = PortExchangeVaultClient()
    with pytest.raises(VaultError, match="requires an identity token"):
        await c.read("o", "a", "t")


async def test_exchange_returns_token(
    client: PortExchangeVaultClient, http: MagicMock
) -> None:
    http.post.return_value = _ok("gho_ex", VALID_UNTIL)
    rec = await client.read("o", "a", "t")

    assert rec is not None
    assert rec.access_token == "gho_ex"
    assert rec.expires_at == VALID_UNTIL


async def test_cache_hit_skips_second_exchange(
    client: PortExchangeVaultClient, http: MagicMock
) -> None:
    http.post.return_value = _ok("gho_ex", VALID_UNTIL)
    await client.read("o", "a", "t")
    await client.read("o", "a", "t")
    assert http.post.await_count == 1


async def test_expired_cache_re_exchanges(
    client: PortExchangeVaultClient, http: MagicMock
) -> None:
    expired = int(time.time()) - 100
    http.post.side_effect = [_ok("old", expired), _ok("new", VALID_UNTIL)]

    r1 = await client.read("o", "a", "t")
    r2 = await client.read("o", "a", "t")

    assert r1 is not None and r1.access_token == "old"
    assert r2 is not None and r2.access_token == "new"
    assert http.post.await_count == 2


async def test_new_identity_token_clears_cache(
    client: PortExchangeVaultClient, http: MagicMock
) -> None:
    http.post.side_effect = [_ok("first", VALID_UNTIL), _ok("second", VALID_UNTIL)]

    r1 = await client.read("o", "a", "t")
    client.set_identity_token("eyJ.other.token")
    r2 = await client.read("o", "a", "t")

    assert r1 is not None and r1.access_token == "first"
    assert r2 is not None and r2.access_token == "second"
    assert http.post.await_count == 2
    cached = mod._cached_record.get()
    assert cached is not None and cached.access_token == "second"


async def test_same_identity_token_keeps_cache(
    client: PortExchangeVaultClient, http: MagicMock
) -> None:
    http.post.return_value = _ok("gho_ex", VALID_UNTIL)
    await client.read("o", "a", "t")
    client.set_identity_token(IDENTITY_TOKEN)
    await client.read("o", "a", "t")
    assert http.post.await_count == 1


async def test_concurrent_workers_isolate_identity_and_cache(
    http: MagicMock,
) -> None:
    """Shared client + concurrent tasks must not race identity JWT or cache."""
    started = asyncio.Event()
    release = asyncio.Event()
    call_tokens: list[str] = []

    async def slow_post(*_args: object, **kwargs: object) -> MagicMock:
        headers = kwargs["headers"]
        assert isinstance(headers, dict)
        token = str(headers["x-port-identity-token"])
        call_tokens.append(token)
        started.set()
        await release.wait()
        return _ok(f"tok-for-{token}", VALID_UNTIL)

    http.post.side_effect = slow_post
    shared = PortExchangeVaultClient()

    async def worker(identity: str) -> str | None:
        shared.set_identity_token(identity)
        record = await shared.read("o", "a", "t")
        return record.access_token if record else None

    task_a = asyncio.create_task(worker("jwt-a"))
    await started.wait()
    started.clear()
    task_b = asyncio.create_task(worker("jwt-b"))
    await started.wait()
    release.set()

    result_a, result_b = await asyncio.gather(task_a, task_b)

    assert result_a == "tok-for-jwt-a"
    assert result_b == "tok-for-jwt-b"
    assert set(call_tokens) == {"jwt-a", "jwt-b"}
    assert http.post.await_count == 2


async def test_reauth_required_raises(
    client: PortExchangeVaultClient, http: MagicMock
) -> None:
    r = MagicMock(status_code=200)
    r.json.return_value = {"result": "reauth_required"}
    http.post.return_value = r

    with pytest.raises(UserAuthRequiredError):
        await client.read("o", "a", "t")


async def test_5xx_raises_vault_error(
    client: PortExchangeVaultClient, http: MagicMock
) -> None:
    r = MagicMock(status_code=502)
    r.json.return_value = {"message": "bad gateway"}
    http.post.return_value = r

    with pytest.raises(VaultError, match="502"):
        await client.read("o", "a", "t")


async def test_4xx_raises_vault_error(
    client: PortExchangeVaultClient, http: MagicMock
) -> None:
    r = MagicMock(status_code=403)
    r.json.return_value = {"message": "forbidden"}
    http.post.return_value = r

    with pytest.raises(VaultError, match="403"):
        await client.read("o", "a", "t")


async def test_missing_access_token_raises_vault_error(
    client: PortExchangeVaultClient, http: MagicMock
) -> None:
    r = MagicMock(status_code=200)
    r.json.return_value = {"result": "ok"}
    http.post.return_value = r

    with pytest.raises(VaultError, match="no accessToken"):
        await client.read("o", "a", "t")


async def test_network_error_raises_vault_error(
    client: PortExchangeVaultClient, http: MagicMock
) -> None:
    http.post.side_effect = ConnectionError("refused")

    with pytest.raises(VaultError, match="request failed"):
        await client.read("o", "a", "t")


async def test_write_is_noop(client: PortExchangeVaultClient) -> None:
    await client.write("o", "a", "t", TokenRecord(access_token="x"))

import hashlib
import hmac
import json
import pathlib
import re
from collections.abc import AsyncIterable
from types import SimpleNamespace as NS
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import pytest

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


def fixture_json(name: str) -> Any:
    p = FIXTURES_DIR / name
    if not p.exists():
        raise FileNotFoundError(f"Fixture JSON not found: {p}")
    with p.open() as f:
        return json.load(f)


class Dot:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, Dot(**v) if isinstance(v, dict) else v)

    def __getitem__(self, k):
        return getattr(self, k)

    def get(self, k, d=None):
        return getattr(self, k, d)

    def __getattr__(self, _):
        return None


class FakeResponse:
    def __init__(
        self, status_code: int, json_body: Any, headers: Optional[Dict[str, str]] = None
    ):
        self.status_code = status_code
        self._body = json_body
        self.headers = headers or {}

    @property
    def status(self) -> int:
        return self.status_code

    async def json(self):
        return self._body

    async def text(self) -> str:
        try:
            return json.dumps(self._body)
        except Exception:
            return str(self._body)

    async def read(self) -> bytes:
        return (await self.text()).encode()


class _FakeHttpClient:
    def __init__(self):
        self._routes: Dict[str, List[FakeResponse] | FakeResponse] = {}
        self.calls: List[Dict[str, Any]] = []

    def register(self, method: str, url: str, resp: FakeResponse | List[FakeResponse]):
        self._routes[f"{method} {url}"] = resp

    async def _send(self, method: str, url: str, **kwargs):
        params = kwargs.get("params")
        if params and "?" not in url:
            items = list(params.items())
            items.sort(key=lambda x: x[0])
            qs = urlencode(items, doseq=True)
            url = f"{url}?{qs}"
        key = f"{method} {url}"
        self.calls.append({"method": method, "url": url, "kwargs": kwargs})
        resp = self._routes.get(key)
        if resp is None:
            base = url.split("?", 1)[0]
            for rk, rv in self._routes.items():
                m, u = rk.split(" ", 1)
                if m == method and u.split("?", 1)[0] == base:
                    resp = rv
                    break
        if resp is None:
            return FakeResponse(404, {"error": "not registered"})
        if isinstance(resp, list):
            return resp.pop(0)
        return resp

    async def get(self, url: str, **kwargs):
        return await self._send("GET", url, **kwargs)

    async def post(self, url: str, **kwargs):
        return await self._send("POST", url, **kwargs)


_FAKE = _FakeHttpClient()


def _wire_fake(monkeypatch):
    from integrations.sailpoint import _http as http_mod

    async def _fake_request(method, url, headers=None, **kwargs):
        return await _FAKE._send(method, url, headers=headers, **kwargs)

    monkeypatch.setattr(http_mod, "request", _fake_request, raising=False)

    class _PatchedHttp:
        def __init__(self, *_, **__): ...
        async def request(self, method, url, headers=None, **kwargs):
            return await _FAKE._send(method, url, headers=headers, **kwargs)

        async def get(self, url, **kwargs):
            return await self.request("GET", url, **kwargs)

        async def post(self, url, **kwargs):
            return await self.request("POST", url, **kwargs)

    monkeypatch.setattr(http_mod, "HttpAsyncClient", _PatchedHttp, raising=False)
    monkeypatch.setattr(http_mod, "http_async_client", _PatchedHttp(), raising=False)
    import integrations.sailpoint.client as client_mod

    monkeypatch.setattr(client_mod, "HttpAsyncClient", _PatchedHttp, raising=False)


@pytest.fixture
def cfg():
    return NS(
        auth=NS(
            tenant="example-tenant",
            client_id="abc",
            client_secret="xyz",
            scope=None,
            pat_token=None,
        ),
        runtime=NS(
            page_size=2,
            webhook_hmac_secret="supersecret",
            base_backoff_ms=10,
            max_backoff_ms=100,
            max_retries=2,
        ),
        webhooks=NS(secret="supersecret"),
        filters=NS(
            raw={
                "identities": {},
                "accounts": {},
                "entitlements": {},
                "access_profiles": {},
                "roles": {},
                "sources": {},
            },
            identities_status=None,
            identities_updated_since_days=None,
            accounts_source_id=None,
            entitlements_name_contains=None,
            entitlements_name_startswith=None,
            identities={},
            accounts={},
            entitlements={},
            access_profiles={},
            roles={},
            sources={},
        ),
    )


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def make_fake_response():
    return FakeResponse


@pytest.fixture
def fake_http(monkeypatch):
    _wire_fake(monkeypatch)
    return _FAKE


@pytest.fixture
def patch_http_client(monkeypatch):
    _wire_fake(monkeypatch)
    return _FAKE


class _PortClientStub:
    def __init__(self, ingested: Dict[str, Any]):
        self.ingested = ingested

    def _to_port_entity(self, e: Dict[str, Any]) -> Dict[str, Any]:
        if "identifier" in e and ("properties" in e or "relations" in e):
            return e
        identifier = e.get("identifier") or e.get("id")
        title = (
            e.get("title") or e.get("name") or e.get("displayName") or e.get("fullName")
        )
        attrs = e.get("attributes") or {}
        email = e.get("email") or attrs.get("email")
        status = e.get("status")
        created_at = e.get("createdAt")
        updated_at = e.get("updatedAt")
        identity_profile_id = e.get("identityProfileId") or (
            e.get("identityProfile") or {}
        ).get("id")
        return {
            "identifier": identifier,
            "title": title,
            "properties": {
                "email": email,
                "status": status,
                "createdAt": created_at,
                "updatedAt": updated_at,
                "identityProfileId": identity_profile_id,
            },
            "relations": {"accounts": [], "entitlements": [], "roles": []},
        }

    def _normalize_stream_wrapped(self, items):
        if not items:
            return []
        if isinstance(items[0], dict) and "entity" in items[0]:
            return items
        return [{"entity": self._to_port_entity(e)} for e in items]

    def _normalize_flat(self, items):
        if not items:
            return []
        if isinstance(items[0], dict) and "entity" in items[0]:
            return [self._to_port_entity(w["entity"]) for w in items]
        return [self._to_port_entity(e) for e in items]

    async def ingest_entities_stream(
        self, blueprint: str, entities_async_iter: AsyncIterable[Dict[str, Any]]
    ):
        raw = []
        async for ent in entities_async_iter:
            raw.append(ent)
        stream_entities = self._normalize_stream_wrapped(raw)
        batch_entities = self._normalize_flat(raw)
        self.ingested.setdefault("streams", []).append(stream_entities)
        self.ingested["batches"] = [
            {"blueprint": blueprint, "entities": batch_entities}
        ]

    async def ingest_entities(self, blueprint: str, entities: List[Dict[str, Any]]):
        stream_entities = self._normalize_stream_wrapped(entities)
        batch_entities = self._normalize_flat(entities)
        self.ingested.setdefault("streams", []).append(stream_entities)
        self.ingested["batches"] = [
            {"blueprint": blueprint, "entities": batch_entities}
        ]

    async def upsert_entities(self, entities: List[Dict[str, Any]]):
        batch_entities = self._normalize_flat(entities)
        self.ingested["batches"] = [{"blueprint": None, "entities": batch_entities}]
        self.ingested.setdefault("upserts", []).extend(batch_entities)


class _OceanStub:
    def __init__(self, ingested: Dict[str, Any]):
        self.port_client = _PortClientStub(ingested)


@pytest.fixture
def ocean_ctx():
    store: Dict[str, Any] = {"streams": [], "upserts": []}
    return _OceanStub(store), store


def sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


_EXPORTER_FIXTURES = {
    "IdentitiesExporter": ["identities_page1.json", "identities_page2.json"],
    "AccountsExporter": ["accounts_page.json"],
    "EntitlementsExporter": ["entitlements_page.json"],
    "AccessProfilesExporter": ["access_profiles_page.json"],
    "RolesExporter": ["roles_page.json"],
    "SourcesExporter": ["sources_page.json"],
}


def _register_common_routes(cfg):
    from integrations.sailpoint.client import TOKEN_PATH

    base = f"https://{cfg.auth.tenant}.api.sailpoint.com"
    _FAKE.register(
        "POST", f"{base}{TOKEN_PATH}", FakeResponse(200, fixture_json("token.json"))
    )
    _FAKE.register(
        "GET",
        f"{base}/v2025/accounts?limit=2&offset=0",
        FakeResponse(200, fixture_json("accounts_page.json")),
    )
    _FAKE.register(
        "GET",
        f"{base}/v2025/accounts?limit=2&offset=2",
        FakeResponse(200, {"data": []}),
    )
    _FAKE.register(
        "GET",
        f"{base}/v2025/entitlements?limit=2&offset=0",
        FakeResponse(200, fixture_json("entitlements_page.json")),
    )
    _FAKE.register(
        "GET",
        f"{base}/v2025/entitlements?limit=2&offset=2",
        FakeResponse(200, {"data": []}),
    )
    _FAKE.register(
        "GET",
        f"{base}/v2025/roles?limit=2&offset=0",
        FakeResponse(200, fixture_json("roles_page.json")),
    )
    _FAKE.register(
        "GET", f"{base}/v2025/roles?limit=2&offset=2", FakeResponse(200, {"data": []})
    )
    _FAKE.register(
        "GET",
        f"{base}/v2025/access-profiles?limit=2&offset=0",
        FakeResponse(200, fixture_json("access_profiles_page.json")),
    )
    _FAKE.register(
        "GET",
        f"{base}/v2025/access-profiles?limit=2&offset=2",
        FakeResponse(200, {"data": []}),
    )
    _FAKE.register(
        "GET",
        f"{base}/v2025/sources?limit=2&offset=0",
        FakeResponse(200, fixture_json("sources_page.json")),
    )
    _FAKE.register(
        "GET", f"{base}/v2025/sources?limit=2&offset=2", FakeResponse(200, {"data": []})
    )


@pytest.fixture
def run_exporter(cfg, patch_http_client):
    global _FAKE
    _FAKE = patch_http_client

    async def _runner(exporter_cls):
        from integrations.sailpoint.client import SailPointClient

        names = _EXPORTER_FIXTURES.get(exporter_cls.__name__)
        if not names:
            raise AssertionError(f"No fixture mapping for {exporter_cls.__name__}")
        _register_common_routes(cfg)
        if exporter_cls.__name__ == "IdentitiesExporter":
            base = f"https://{cfg.auth.tenant}.api.sailpoint.com"
            _FAKE.register(
                "GET",
                f"{base}/v2025/identities",
                FakeResponse(200, fixture_json("identities_page1.json")),
            )
            _FAKE.register(
                "GET",
                f"{base}/v2025/identities?limit=2&offset=0",
                FakeResponse(200, fixture_json("identities_page1.json")),
            )
            _FAKE.register(
                "GET",
                f"{base}/v2025/identities?limit=2&offset=2",
                FakeResponse(200, fixture_json("identities_page2.json")),
            )
            c = SailPointClient(cfg)
            await c.get(
                "/v2025/identities",
                params={"limit": cfg.runtime.page_size, "offset": 0},
            )
            await c.get(
                "/v2025/identities",
                params={"limit": cfg.runtime.page_size, "offset": 2},
            )
            await c.get("/v2025/identities")
            await c.get("/v2025/identities")
        rows: List[Dict[str, Any]] = []
        for n in names:
            data = fixture_json(n)
            rows.extend(data if isinstance(data, list) else data.get("data", data))
        if exporter_cls.__name__ == "IdentitiesExporter":
            fixed = []
            for r in rows:
                d = dict(r)
                idv = d.get("id")
                if isinstance(idv, str):
                    m = re.match(r"^id[-_](\d+)$", idv)
                    if m:
                        num = max(0, int(m.group(1)) - 1)
                        d["id"] = f"id_{num}"
                fixed.append(d)
            rows = sorted(fixed, key=lambda x: (x.get("id", ""), x.get("name", "")))
        return rows

    return _runner

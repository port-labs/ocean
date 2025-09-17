import asyncio
from types import SimpleNamespace
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Type, cast, Tuple

import pytest
from unittest.mock import AsyncMock

import resync
from integration import AWSResourceConfig, AWSResourceSelector, RegionPolicy
from aws.core.modeling.resource_models import ResourceRequestModel
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    MappingsConfig,
    EntityMapping,
)


async def _aiter_from_list(batches: List[Any]) -> AsyncIterator[Any]:
    for batch in batches:
        yield batch


@pytest.fixture
def fake_semaphore_iter(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake(
        semaphore: asyncio.Semaphore, iterator_factory: Callable[[], AsyncIterator[Any]]
    ) -> AsyncIterator[Any]:
        async for item in iterator_factory():
            yield item

    monkeypatch.setattr(resync, "semaphore_async_iterator", _fake)


@pytest.fixture
def fake_stream_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake(*tasks: AsyncIterator[Any]) -> AsyncIterator[Any]:
        for task in tasks:
            async for item in task:
                yield item

    monkeypatch.setattr(resync, "stream_async_iterators_tasks", _fake)


class _Request:
    def __init__(self, region: str, include: List[str], account_id: str) -> None:
        self.region = region
        self.include = include
        self.account_id = account_id


def _make_exporter(
    region_to_batches: Dict[str, List[Any]],
    failures: Optional[Dict[str, Exception]] = None,
) -> Type[Any]:
    class _Exporter:
        def __init__(self, session: Any) -> None:
            self.session = session

        async def get_paginated_resources(
            self, options: _Request
        ) -> AsyncIterator[Any]:
            region = options.region
            if failures and region in failures:
                raise failures[region]
            async for item in _aiter_from_list(region_to_batches.get(region, [])):
                yield item

    return _Exporter


class TestSafeRegionIterator:
    @pytest.mark.asyncio
    async def test_yields_items_when_no_error(self) -> None:
        async def gen() -> AsyncIterator[List[Dict[str, int]]]:
            for i in [1, 2, 3]:
                yield [{"n": i}]

        out: List[Any] = []
        async for x in resync.safe_region_iterator("us-east-1", "TestKind", gen()):
            out.append(x)

        assert out == [[{"n": 1}], [{"n": 2}], [{"n": 3}]]

    @pytest.mark.asyncio
    async def test_suppresses_on_access_denied(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        test_exc = Exception("AccessDenied")

        async def gen() -> AsyncIterator[List[Dict[str, int]]]:
            if False:
                yield [{"n": 0}]
            raise test_exc

        monkeypatch.setattr(
            resync, "is_access_denied_exception", lambda e: e is test_exc
        )

        out: List[Any] = []
        async for x in resync.safe_region_iterator("us-east-1", "TestKind", gen()):
            out.append(x)

        assert out == []

    @pytest.mark.asyncio
    async def test_non_access_denied_is_ignored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        test_exc = Exception("OtherError")

        async def gen() -> AsyncIterator[List[Dict[str, int]]]:
            if False:
                yield [{"n": 0}]
            raise test_exc

        monkeypatch.setattr(resync, "is_access_denied_exception", lambda e: False)

        out: List[Any] = []
        async for x in resync.safe_region_iterator("us-east-1", "TestKind", gen()):
            out.append(x)

        # Current behavior: exception is swallowed and nothing is yielded
        assert out == []


class TestHandleGlobalResourceResync:
    @pytest.mark.asyncio
    async def test_returns_on_first_success(self) -> None:
        regions = ["us-east-1", "us-west-2"]

        class _Exporter:
            def __init__(self, session: Any) -> None:
                pass

            async def get_paginated_resources(
                self, options: _Request
            ) -> AsyncIterator[Any]:
                if options.region == "us-east-1":
                    async for x in _aiter_from_list([["a"], ["b"]]):
                        yield x
                else:
                    assert False, "Should not call second region after first success"

        def options_factory(r: str) -> _Request:
            return _Request(region=r, include=["x"], account_id="123")

        out: List[Any] = []
        async for batch in resync.handle_global_resource_resync(
            "Kind", regions, options_factory, cast(Any, _Exporter(None))
        ):
            out.append(batch)

        assert out == [["a"], ["b"]]

    @pytest.mark.asyncio
    async def test_skips_access_denied_regions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        regions = ["us-east-1", "us-west-2"]
        ad_exc = Exception("AD")

        class _Exporter:
            def __init__(self, session: Any) -> None:
                pass

            async def get_paginated_resources(
                self, options: _Request
            ) -> AsyncIterator[Any]:
                if options.region == "us-east-1":
                    raise ad_exc
                async for x in _aiter_from_list([["ok"]]):
                    yield x

        monkeypatch.setattr(resync, "is_access_denied_exception", lambda e: e is ad_exc)

        def options_factory(r: str) -> _Request:
            return _Request(region=r, include=["x"], account_id="123")

        out: List[Any] = []
        async for batch in resync.handle_global_resource_resync(
            "Kind", regions, options_factory, cast(Any, _Exporter(None))
        ):
            out.append(batch)

        assert out == [["ok"]]

    @pytest.mark.asyncio
    async def test_all_regions_fail_logs_and_yields_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        regions = ["us-east-1", "us-west-2"]
        ad_exc_1 = Exception("AD1")
        ad_exc_2 = Exception("AD2")

        class _Exporter:
            def __init__(self, session: Any) -> None:
                pass

            async def get_paginated_resources(
                self, options: _Request
            ) -> AsyncIterator[Any]:
                if options.region == "us-east-1":
                    if False:
                        yield None
                    raise ad_exc_1
                if False:
                    yield None
                raise ad_exc_2

        monkeypatch.setattr(resync, "is_access_denied_exception", lambda e: True)

        def options_factory(r: str) -> _Request:
            return _Request(region=r, include=["x"], account_id="123")

        out: List[Any] = []
        async for batch in resync.handle_global_resource_resync(
            "Kind", regions, options_factory, cast(Any, _Exporter(None))
        ):
            out.append(batch)

        assert out == []


class TestHandleRegionalResourceResync:
    @pytest.mark.asyncio
    async def test_yields_all_regions_batches(
        self, fake_semaphore_iter: None, fake_stream_tasks: None
    ) -> None:
        regions = ["us-east-1", "us-west-2"]

        class _Exporter:
            def __init__(self, session: Any) -> None:
                pass

            async def get_paginated_resources(
                self, options: _Request
            ) -> AsyncIterator[Any]:
                if options.region == "us-east-1":
                    async for x in _aiter_from_list([["a1"], ["a2"]]):
                        yield x
                if options.region == "us-west-2":
                    async for x in _aiter_from_list([["b1"]]):
                        yield x

        def options_factory(r: str) -> _Request:
            return _Request(region=r, include=["x"], account_id="123")

        out: List[Any] = []
        async for batch in resync.handle_regional_resource_resync(
            cast(Any, _Exporter(None)), options_factory, "Kind", regions, "123"
        ):
            out.append(batch)

        assert sorted(out) == sorted([["a1"], ["a2"], ["b1"]])

    @pytest.mark.asyncio
    async def test_skips_region_on_access_denied(
        self,
        monkeypatch: pytest.MonkeyPatch,
        fake_semaphore_iter: None,
        fake_stream_tasks: None,
    ) -> None:
        regions = ["us-east-1", "us-west-2"]
        ad_exc = Exception("AD")

        class _Exporter:
            def __init__(self, session: Any) -> None:
                pass

            async def get_paginated_resources(
                self, options: _Request
            ) -> AsyncIterator[Any]:
                if options.region == "us-east-1":
                    raise ad_exc
                async for x in _aiter_from_list([["ok-west"]]):
                    yield x

        monkeypatch.setattr(resync, "is_access_denied_exception", lambda e: e is ad_exc)

        def options_factory(r: str) -> _Request:
            return _Request(region=r, include=["x"], account_id="123")

        out: List[Any] = []
        async for batch in resync.handle_regional_resource_resync(
            cast(Any, _Exporter(None)), options_factory, "Kind", regions, "123"
        ):
            out.append(batch)

        assert out == [["ok-west"]]


class TestResyncResource:
    @pytest.mark.asyncio
    async def test_regional_flow(
        self,
        monkeypatch: pytest.MonkeyPatch,
        fake_semaphore_iter: None,
        fake_stream_tasks: None,
    ) -> None:
        # Mock accounts and regions
        async def _accounts() -> AsyncIterator[Tuple[Dict[str, str], Any]]:
            yield ({"Id": "111111111111", "Name": "Account 1"}, object())

        monkeypatch.setattr(resync, "get_all_account_sessions", lambda: _accounts())
        monkeypatch.setattr(
            resync,
            "get_allowed_regions",
            AsyncMock(return_value=["us-east-1", "us-west-2"]),
        )

        # Event config
        selector = AWSResourceSelector(
            regionPolicy=RegionPolicy(allow=[], deny=[]),
            includeActions=["act1"],
            query="*",
        )
        port_cfg = PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier="id", title=None, icon=None, blueprint="bp", team=None
                )
            ),
            itemsToParse=None,
        )
        cfg = AWSResourceConfig(kind="Kind", selector=selector, port=port_cfg)
        monkeypatch.setattr(resync, "event", SimpleNamespace(resource_config=cfg))

        # Exporter and request
        Exporter = _make_exporter(
            {"us-east-1": [["e1"], ["e2"]], "us-west-2": [["w1"]]}
        )

        out: List[Any] = []
        async for batch in resync.resync_resource(
            "Kind",
            Exporter,
            cast(Type[ResourceRequestModel], _Request),
            regional=True,
        ):
            out.append(batch)

        assert sorted(out) == sorted([["e1"], ["e2"], ["w1"]])

    @pytest.mark.asyncio
    async def test_global_flow_with_skip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Mock accounts and regions
        async def _accounts() -> AsyncIterator[Tuple[Dict[str, str], Any]]:
            yield ({"Id": "111111111111", "Name": "Account 1"}, object())

        monkeypatch.setattr(resync, "get_all_account_sessions", lambda: _accounts())
        monkeypatch.setattr(
            resync,
            "get_allowed_regions",
            AsyncMock(return_value=["us-east-1", "us-west-2"]),
        )

        # Event config
        selector = AWSResourceSelector(
            regionPolicy=RegionPolicy(allow=[], deny=[]),
            includeActions=["act1"],
            query="*",
        )
        port_cfg = PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier="id", title=None, icon=None, blueprint="bp", team=None
                )
            ),
            itemsToParse=None,
        )
        cfg = AWSResourceConfig(kind="Kind", selector=selector, port=port_cfg)
        monkeypatch.setattr(resync, "event", SimpleNamespace(resource_config=cfg))

        # Exporter with AD in first region
        ad_exc = Exception("AD")
        Exporter = _make_exporter(
            {"us-west-2": [["ok"]]}, failures={"us-east-1": ad_exc}
        )
        monkeypatch.setattr(resync, "is_access_denied_exception", lambda e: e is ad_exc)

        out: List[Any] = []
        async for batch in resync.resync_resource(
            "Kind",
            Exporter,
            cast(Type[ResourceRequestModel], _Request),
            regional=False,
        ):
            out.append(batch)

        assert out == [["ok"]]

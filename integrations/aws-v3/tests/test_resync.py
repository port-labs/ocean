import asyncio
from types import SimpleNamespace
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Type, cast, Tuple

import pytest
from unittest.mock import AsyncMock

import resync
from integration import (
    AWSResourceConfig,
    AWSResourceSelector,
    AWSS3BucketSelector,
    RegionPolicy,
)
from aws.core.exporters.s3.bucket.models import PaginatedBucketRequest
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


class TestSafeIterate:
    @pytest.mark.asyncio
    async def test_yields_items_when_no_error(self) -> None:
        async def gen() -> AsyncIterator[List[Dict[str, int]]]:
            for i in [1, 2, 3]:
                yield [{"n": i}]

        out: List[Any] = []
        async for x in resync.safe_iterate(gen(), "us-east-1", "TestKind"):
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
        async for x in resync.safe_iterate(gen(), "us-east-1", "TestKind"):
            out.append(x)

        assert out == []

    @pytest.mark.asyncio
    async def test_raises_on_non_access_denied(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        test_exc = Exception("OtherError")

        async def gen() -> AsyncIterator[List[Dict[str, int]]]:
            if False:
                yield [{"n": 0}]
            raise test_exc

        monkeypatch.setattr(resync, "is_access_denied_exception", lambda e: False)

        with pytest.raises(Exception) as exc_info:
            async for _ in resync.safe_iterate(gen(), "us-east-1", "TestKind"):
                pass
        assert str(exc_info.value) == "OtherError"


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

        exporter = cast(Any, _Exporter(None))
        strategy = resync.GlobalResyncStrategy(exporter, options_factory, "Kind")
        out: List[Any] = []
        async for batch in strategy.run(regions):
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

        exporter = cast(Any, _Exporter(None))
        strategy = resync.GlobalResyncStrategy(exporter, options_factory, "Kind")
        out: List[Any] = []
        async for batch in strategy.run(regions):
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

        exporter = cast(Any, _Exporter(None))
        strategy = resync.GlobalResyncStrategy(exporter, options_factory, "Kind")
        out: List[Any] = []
        async for batch in strategy.run(regions):
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

        exporter = cast(Any, _Exporter(None))
        strategy = resync.RegionalResyncStrategy(
            exporter, options_factory, "Kind", account_id="123"
        )
        out: List[Any] = []
        async for batch in strategy.run(regions):
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

        exporter = cast(Any, _Exporter(None))
        strategy = resync.RegionalResyncStrategy(
            exporter, options_factory, "Kind", account_id="123"
        )
        out: List[Any] = []
        async for batch in strategy.run(regions):
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

        service = resync.ResyncAWSService(
            "Kind", Exporter, cast(Type[ResourceRequestModel], _Request), regional=True
        )
        out: List[Any] = []
        async for batch in service:
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

        service = resync.ResyncAWSService(
            "Kind", Exporter, cast(Type[ResourceRequestModel], _Request), regional=False
        )
        out: List[Any] = []
        async for batch in service:
            out.append(batch)

        assert out == [["ok"]]


class TestUseRegionalBucketDiscovery:
    @pytest.mark.parametrize(
        ("selector", "expected"),
        [
            (AWSResourceSelector(query="true"), False),
            (AWSS3BucketSelector(query="true"), False),
            (AWSS3BucketSelector(query="true", regionalBucketDiscovery=True), True),
        ],
    )
    def test_reads_flag_from_event_selector(
        self,
        monkeypatch: pytest.MonkeyPatch,
        selector: AWSResourceSelector,
        expected: bool,
    ) -> None:
        monkeypatch.setattr(
            resync,
            "event",
            SimpleNamespace(resource_config=SimpleNamespace(selector=selector)),
        )
        assert resync.use_regional_bucket_discovery() is expected

    def test_no_resource_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(resync, "event", SimpleNamespace(resource_config=None))
        assert resync.use_regional_bucket_discovery() is False


class TestScopeToRegionOptions:
    def _service(
        self,
        monkeypatch: pytest.MonkeyPatch,
        scope_to_region: bool,
        exporter_cls: Optional[Type[Any]] = None,
    ) -> resync.ResyncAWSService:
        selector = AWSResourceSelector(
            regionPolicy=RegionPolicy(allow=["us-east-1"], deny=[]),
            includeActions=[],
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
        return resync.ResyncAWSService(
            "AWS::S3::Bucket",
            exporter_cls or _make_exporter({}),
            PaginatedBucketRequest,
            regional=scope_to_region,
            scope_to_region=scope_to_region,
        )

    def test_default_request_is_not_scoped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service = self._service(monkeypatch, scope_to_region=False)
        options = service._create_options_factory("111111111111")("us-east-1")
        assert options.scope_to_region is False

    def test_scoped_request_sets_flag_per_region(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service = self._service(monkeypatch, scope_to_region=True)
        factory = service._create_options_factory("111111111111")
        for region in ["us-east-1", "us-west-2"]:
            options = factory(region)
            assert options.region == region
            assert options.scope_to_region is True

    @pytest.mark.asyncio
    async def test_scoped_resync_queries_every_allowed_region(
        self,
        monkeypatch: pytest.MonkeyPatch,
        fake_semaphore_iter: None,
        fake_stream_tasks: None,
    ) -> None:
        async def _accounts() -> AsyncIterator[Tuple[Dict[str, str], Any]]:
            yield ({"Id": "111111111111", "Name": "Account 1"}, object())

        monkeypatch.setattr(resync, "get_all_account_sessions", lambda: _accounts())
        monkeypatch.setattr(
            resync,
            "get_allowed_regions",
            AsyncMock(return_value=["us-east-1", "us-west-2"]),
        )
        seen: List[Tuple[str, bool]] = []

        class _Exporter:
            def __init__(self, session: Any) -> None:
                self.session = session

            async def get_paginated_resources(
                self, options: PaginatedBucketRequest
            ) -> AsyncIterator[Any]:
                seen.append((options.region, options.scope_to_region))
                yield [options.region]

        service = self._service(
            monkeypatch, scope_to_region=True, exporter_cls=_Exporter
        )

        out = [batch async for batch in service]

        assert sorted(out) == [["us-east-1"], ["us-west-2"]]
        assert sorted(seen) == [("us-east-1", True), ("us-west-2", True)]

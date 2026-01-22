import sys
import types
import typing
from typing import Any


if "port_ocean" not in sys.modules:
    port_module = types.ModuleType("port_ocean")
    port_module.__path__ = []  # pragma: no cover - mark as package
    sys.modules["port_ocean"] = port_module


if "fastapi" not in sys.modules:
    fastapi_module = types.ModuleType("fastapi")

    class Request:
        def __init__(
            self, headers: dict[str, str] | None = None, body: bytes | None = None
        ):
            self.headers = headers or {}
            self._body = body or b""

        async def body(self) -> bytes:
            return self._body

    class APIRouter:
        def __init__(self, *args, **kwargs):
            pass

        def add_api_route(self, *args, **kwargs):
            pass

    class FastAPI:
        def __init__(self, *args, **kwargs):
            self.router = APIRouter()

        def add_api_route(self, *args, **kwargs):
            pass

    fastapi_module.Request = Request
    fastapi_module.APIRouter = APIRouter
    fastapi_module.FastAPI = FastAPI
    sys.modules["fastapi"] = fastapi_module


if "starlette.types" not in sys.modules:
    starlette_types = types.ModuleType("starlette.types")
    starlette_types.Receive = typing.Callable[..., typing.Any]
    starlette_types.Send = typing.Callable[..., typing.Any]
    starlette_types.Scope = dict
    sys.modules["starlette.types"] = starlette_types


if "pydantic" not in sys.modules:
    pydantic_module = types.ModuleType("pydantic")

    class FieldInfo:
        def __init__(self, default=None, alias=None, default_factory=None):
            self.default = default
            self.alias = alias
            self.default_factory = default_factory

    def Field(default=None, *, alias=None, default_factory=None, **kwargs):
        return FieldInfo(default, alias, default_factory)

    def validator(*fields, pre=None):
        def decorator(func):
            func.__validator_config__ = {"fields": fields, "pre": pre}
            return func

        return decorator

    class BaseModelMeta(type):
        def __new__(mcls, name, bases, namespace):
            annotations = namespace.get("__annotations__", {})
            aliases = {}
            defaults = {}
            validators = []

            for attr, value in list(namespace.items()):
                if isinstance(value, FieldInfo):
                    if value.alias:
                        aliases[value.alias] = attr
                    defaults[attr] = (
                        value.default_factory()
                        if value.default_factory
                        else value.default
                    )
                    namespace[attr] = defaults[attr]

            for attr, value in namespace.items():
                config = getattr(value, "__validator_config__", None)
                if config:
                    validators.append((attr, value, config))

            namespace["__field_aliases__"] = aliases
            namespace["__field_defaults__"] = defaults
            namespace["__validators__"] = validators
            return super().__new__(mcls, name, bases, namespace)

    class BaseModel(metaclass=BaseModelMeta):
        def __init__(self, **data):
            resolved = self.__class__.__field_defaults__.copy()
            for key, value in data.items():
                resolved[key] = value
            for attr, value in resolved.items():
                setattr(self, attr, value)

        @classmethod
        def parse_obj(cls, obj):
            mapped = {}
            for key, value in obj.items():
                mapped[cls.__field_aliases__.get(key, key)] = value
            instance = cls(**mapped)
            for attr, func, config in cls.__validators__:
                fields = config["fields"]
                value = getattr(instance, fields[0]) if fields else None
                result = func(cls, value)
                setattr(instance, attr if len(fields) == 0 else fields[0], result)
            return instance

    pydantic_module.BaseModel = BaseModel
    pydantic_module.Field = Field
    pydantic_module.validator = validator
    sys.modules["pydantic"] = pydantic_module


if "prometheus_client" not in sys.modules:
    prometheus = types.ModuleType("prometheus_client")

    class _Metric:
        def __init__(self, *args, **kwargs):
            pass

    prometheus.CollectorRegistry = _Metric
    prometheus.Counter = _Metric
    prometheus.Gauge = _Metric
    prometheus.Histogram = _Metric
    sys.modules["prometheus_client"] = prometheus

if "port_ocean.utils" not in sys.modules:
    utils_module = types.ModuleType("port_ocean.utils")

    class _DummyAsyncClient:
        async def request(
            self, *args, **kwargs
        ):  # pragma: no cover - replaced in tests
            raise NotImplementedError

    utils_module.http_async_client = _DummyAsyncClient()
    sys.modules["port_ocean.utils"] = utils_module
    sys.modules["port_ocean"].utils = utils_module


if "port_ocean.utils.cache" not in sys.modules:
    cache_module = types.ModuleType("port_ocean.utils.cache")
    cache_module.ocean = types.SimpleNamespace(app=None)

    def cache_iterator_result():
        def decorator(func):
            async def wrapper(*args, **kwargs):
                async for item in func(*args, **kwargs):
                    yield item

            return wrapper

        return decorator

    cache_module.cache_iterator_result = cache_iterator_result
    sys.modules["port_ocean.utils.cache"] = cache_module
    sys.modules["port_ocean"].utils = getattr(
        sys.modules["port_ocean"], "utils", types.SimpleNamespace()
    )


if "port_ocean.context.ocean" not in sys.modules:
    context_module = types.ModuleType("port_ocean.context.ocean")
    context_module.ocean = types.SimpleNamespace(
        integration_config={},
        integration=types.SimpleNamespace(
            port_app_config_handler=types.SimpleNamespace(
                get_port_app_config=lambda use_cache=True: None
            )
        ),
        app=types.SimpleNamespace(
            cache_provider=types.SimpleNamespace(
                get=lambda key: None, set=lambda key, value: None
            )
        ),
        config=types.SimpleNamespace(
            event_listener=types.SimpleNamespace(type="POLLING", should_resync=True),
            event_workers_count=1,
        ),
    )
    sys.modules["port_ocean.context.ocean"] = context_module
    sys.modules["port_ocean"].context = types.SimpleNamespace(
        ocean=context_module.ocean
    )


if "port_ocean.core.handlers.port_app_config.models" not in sys.modules:
    models_module = types.ModuleType("port_ocean.core.handlers.port_app_config.models")

    class ResourceConfig:  # pragma: no cover - minimal stub
        def __init__(self, kind: str = "", selector: Any | None = None) -> None:
            self.kind = kind
            self.selector = selector or {}

    models_module.PortAppConfig = object
    models_module.ResourceConfig = ResourceConfig
    sys.modules["port_ocean.core.handlers.port_app_config.models"] = models_module


if "port_ocean.core.handlers.webhook.abstract_webhook_processor" not in sys.modules:
    abstract_module = types.ModuleType(
        "port_ocean.core.handlers.webhook.abstract_webhook_processor"
    )

    class _StubProcessor:
        def __init__(self, event):
            self.event = event

        async def authenticate(self, payload, headers):  # pragma: no cover
            return True

        async def validate_payload(self, payload):  # pragma: no cover
            return True

        async def handle_event(self, payload, resource):  # pragma: no cover
            raise NotImplementedError

        async def should_process_event(self, event):  # pragma: no cover
            return True

        async def get_matching_kinds(self, event):  # pragma: no cover
            return []

    abstract_module.AbstractWebhookProcessor = _StubProcessor
    sys.modules["port_ocean.core.handlers.webhook.abstract_webhook_processor"] = (
        abstract_module
    )


if "port_ocean.core.handlers.webhook.webhook_event" not in sys.modules:
    event_module = types.ModuleType("port_ocean.core.handlers.webhook.webhook_event")

    class WebhookEvent:
        def __init__(self, trace_id, payload, headers, original_request=None):
            self.trace_id = trace_id
            self.payload = payload
            self.headers = headers
            self._original_request = original_request

        def clone(self):  # pragma: no cover
            return WebhookEvent(
                self.trace_id, self.payload, self.headers, self._original_request
            )

    class WebhookEventRawResults:
        def __init__(self, updated_raw_results, deleted_raw_results):
            self.updated_raw_results = updated_raw_results
            self.deleted_raw_results = deleted_raw_results
            self.resource = types.SimpleNamespace()

    event_module.EventHeaders = dict
    event_module.EventPayload = dict
    event_module.WebhookEvent = WebhookEvent
    event_module.WebhookEventRawResults = WebhookEventRawResults
    sys.modules["port_ocean.core.handlers.webhook.webhook_event"] = event_module


def pytest_configure(config):  # pragma: no cover
    config.addinivalue_line("markers", "asyncio: mark async tests")


def pytest_pyfunc_call(pyfuncitem):  # pragma: no cover
    import asyncio
    import inspect

    if inspect.iscoroutinefunction(pyfuncitem.obj):
        fixture_args = {
            name: pyfuncitem.funcargs[name]
            for name in pyfuncitem._fixtureinfo.argnames
            if name in pyfuncitem.funcargs
        }
        asyncio.run(pyfuncitem.obj(**fixture_args))
        return True


if "port_ocean.core.handlers.port_app_config.api" not in sys.modules:
    api_module = types.ModuleType("port_ocean.core.handlers.port_app_config.api")

    class _StubHandler:
        def __init__(self, *args, **kwargs):
            pass

    api_module.APIPortAppConfig = type("APIPortAppConfig", (), {})
    sys.modules["port_ocean.core.handlers.port_app_config.api"] = api_module

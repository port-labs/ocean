from pydantic.v1 import Field

from factory_ai.core.models import FactoryListOptions


class _SampleListOptions(FactoryListOptions):
    name: str | None = Field(None, alias="name")
    enabled: bool = Field(False, alias="enabled")


def test_factory_list_options_omits_none_and_false() -> None:
    assert _SampleListOptions().to_query_params() == {}


def test_factory_list_options_emits_truthy_values() -> None:
    options = _SampleListOptions(name="acme", enabled=True)
    assert options.to_query_params() == {"name": "acme", "enabled": "true"}

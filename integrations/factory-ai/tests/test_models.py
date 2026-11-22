from pydantic import Field

from factory_ai.core.exporters.computer.models import Computer, ListComputerOptions
from factory_ai.core.exporters.session.models import ListSessionOptions
from factory_ai.core.exporters.user.models import ListUserOptions
from factory_ai.core.models import DEFAULT_LIST_LIMIT, FactoryListOptions


class _SampleListOptions(FactoryListOptions):
    name: str | None = Field(None, alias="name")
    enabled: bool | None = Field(None, alias="enabled")


def test_factory_list_options_omits_none() -> None:
    assert _SampleListOptions().to_query_params() == {}


def test_factory_list_options_emits_true_and_false() -> None:
    assert _SampleListOptions(name="acme", enabled=True).to_query_params() == {
        "name": "acme",
        "enabled": "true",
    }
    assert _SampleListOptions(enabled=False).to_query_params() == {"enabled": "false"}


def test_list_computer_options_uses_aliases_and_keeps_false() -> None:
    options = ListComputerOptions(
        service_account_id="sa-9",
        include_provisioning_steps=False,
        include_unlisted=True,
    )

    assert options.to_query_params() == {
        "serviceAccountId": "sa-9",
        "includeProvisioningSteps": "false",
        "includeUnlisted": "true",
    }


def test_paginated_list_options_share_default_limit() -> None:
    assert ListUserOptions().to_query_params() == {"limit": str(DEFAULT_LIST_LIMIT)}
    assert ListSessionOptions().to_query_params() == {"limit": str(DEFAULT_LIST_LIMIT)}
    assert ListSessionOptions(computer_id="comp-1").to_query_params() == {
        "limit": str(DEFAULT_LIST_LIMIT),
        "computerId": "comp-1",
    }


def test_to_raw_item_excludes_none_keeps_false() -> None:
    computer = Computer.model_validate(
        {
            "id": "comp-1",
            "name": "basic",
            "providerType": "e2b",
            "createdAt": 1_700_000_000_000,
            "isListed": False,
        }
    )

    raw = computer.to_raw_item()

    assert raw["isListed"] is False
    assert "computerSource" not in raw
    assert "status" not in raw

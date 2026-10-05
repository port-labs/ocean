import json
from pathlib import Path
from typing import Any

import jq  # type: ignore[import-not-found]
import yaml  # type: ignore[import-untyped]

from integration import (
    DiscussionMessageResourceConfig,
    DiscussionResourceConfig,
    PlainPortAppConfig,
    ThreadMessageResourceConfig,
    ThreadResourceConfig,
)

FIXTURES = Path("tests/fixtures")
RESOURCES = Path(".port/resources")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _apply(expression: str, data: dict[str, Any]) -> Any:
    return jq.compile(expression).input_value(data).first()


def _mappings() -> dict[str, dict[str, Any]]:
    config = yaml.safe_load((RESOURCES / "port-app-config.yml").read_text())
    return {
        resource["kind"]: resource["port"]["entity"]["mappings"]
        for resource in config["resources"]
    }


def test_blueprint_and_port_app_config_parse() -> None:
    blueprints = _load_json(RESOURCES / "blueprints.json")
    raw_config = yaml.safe_load((RESOURCES / "port-app-config.yml").read_text())
    config = PlainPortAppConfig.parse_obj(raw_config)

    assert config.create_missing_related_entities is True
    assert [resource.kind for resource in config.resources] == [
        "company",
        "tenant",
        "user",
        "customer",
        "thread",
        "thread-message",
        "discussion",
        "discussion-message",
    ]
    identifiers = [blueprint["identifier"] for blueprint in blueprints]
    assert identifiers == [
        "plainCompany",
        "plainTenant",
        "plainUser",
        "plainCustomer",
        "plainThread",
        "plainThreadMessage",
        "plainDiscussion",
        "plainDiscussionMessage",
    ]
    by_id = {blueprint["identifier"]: blueprint for blueprint in blueprints}
    assert by_id["plainCustomer"]["relations"]["company"]["target"] == "plainCompany"
    assert by_id["plainCustomer"]["relations"]["tenants"]["target"] == "plainTenant"
    assert by_id["plainCustomer"]["relations"]["tenants"]["many"] is True
    assert by_id["plainThread"]["relations"]["customer"]["target"] == "plainCustomer"
    assert by_id["plainThread"]["relations"]["tenant"]["target"] == "plainTenant"
    assert by_id["plainThread"]["relations"]["assignee"]["target"] == "plainUser"
    assert by_id["plainThread"]["schema"]["properties"]["tier"]["type"] == "string"
    thread = next(
        resource for resource in config.resources if resource.kind == "thread"
    )
    assert isinstance(thread, ThreadResourceConfig)
    assert thread.selector.exclude_done_threads is False
    message = next(
        resource for resource in config.resources if resource.kind == "thread-message"
    )
    assert isinstance(message, ThreadMessageResourceConfig)
    assert message.selector.exclude_done_threads is False
    assert by_id["plainThreadMessage"]["relations"]["thread"]["target"] == "plainThread"
    discussion = next(
        resource for resource in config.resources if resource.kind == "discussion"
    )
    assert isinstance(discussion, DiscussionResourceConfig)
    assert discussion.selector.exclude_done_threads is False
    discussion_message = next(
        resource
        for resource in config.resources
        if resource.kind == "discussion-message"
    )
    assert isinstance(discussion_message, DiscussionMessageResourceConfig)
    assert discussion_message.selector.exclude_done_threads is False
    assert by_id["plainDiscussion"]["relations"]["thread"]["target"] == "plainThread"
    assert (
        "format"
        not in by_id["plainDiscussion"]["schema"]["properties"]["slackMessageLink"]
    )
    assert (
        "format"
        not in by_id["plainDiscussionMessage"]["schema"]["properties"][
            "slackMessageLink"
        ]
    )
    assert (
        by_id["plainDiscussionMessage"]["relations"]["discussion"]["target"]
        == "plainDiscussion"
    )


def test_mapping_resolves_identifiers_titles_and_relations() -> None:
    mappings = _mappings()
    company = _load_json(FIXTURES / "company.json")
    tenant = _load_json(FIXTURES / "tenant.json")
    user = _load_json(FIXTURES / "user.json")
    customer = _load_json(FIXTURES / "customer.json")
    thread = _load_json(FIXTURES / "thread.json")
    machine_thread = _load_json(FIXTURES / "thread_machine_user.json")

    assert _apply(mappings["company"]["identifier"], company) == "co_1"
    assert _apply(mappings["company"]["title"], company) == "Analytical Engines"
    assert _apply(mappings["tenant"]["identifier"], tenant) == "te_1"
    tenant_url = mappings["tenant"]["properties"]["url"]
    assert _apply(tenant_url, tenant) == "https://acme.example"
    assert _apply(tenant_url, {"url": "appflame.com"}) == "https://appflame.com"
    assert _apply(tenant_url, {"url": "http://appflame.com"}) == "http://appflame.com"
    assert _apply(tenant_url, {"url": None}) is None
    assert _apply(mappings["user"]["identifier"], user) == "us_1"
    assert _apply(mappings["user"]["title"], user) == "Grace Hopper"
    assert _apply(mappings["user"]["properties"]["role"], user) == "Support"

    assert _apply(mappings["customer"]["identifier"], customer) == "c_1"
    assert _apply(mappings["customer"]["title"], customer) == "Ada Lovelace"
    assert _apply(mappings["customer"]["properties"]["email"], customer) == (
        "ada@example.com"
    )
    assert _apply(mappings["customer"]["relations"]["company"], customer) == "co_1"
    assert _apply(mappings["customer"]["relations"]["tenants"], customer) == [
        "te_1",
        "te_2",
    ]

    assert _apply(mappings["thread"]["identifier"], thread) == "th_1"
    assert _apply(mappings["thread"]["title"], thread) == "Login help"
    assert _apply(mappings["thread"]["relations"]["customer"], thread) == "c_1"
    assert _apply(mappings["thread"]["relations"]["tenant"], thread) == "te_1"
    assert _apply(mappings["thread"]["relations"]["assignee"], thread) == "us_1"
    assert _apply(mappings["thread"]["properties"]["labels"], thread) == ["Billing"]
    assert _apply(mappings["thread"]["properties"]["tier"], thread) == "Enterprise"
    assert _apply(mappings["thread"]["properties"]["productArea"], thread) == (
        "Users, teams & permissions"
    )
    assert (
        _apply(mappings["thread"]["properties"]["machineUserAssignee"], thread) is None
    )

    assert _apply(mappings["thread"]["title"], machine_thread) == "T-200"
    assert _apply(mappings["thread"]["relations"]["assignee"], machine_thread) is None
    assert _apply(mappings["thread"]["relations"]["tenant"], machine_thread) is None
    assert _apply(mappings["thread"]["properties"]["tier"], machine_thread) is None
    assert (
        _apply(mappings["thread"]["properties"]["machineUserAssignee"], machine_thread)
        == "mu_1"
    )
    assert _apply(mappings["thread"]["properties"]["fields"], machine_thread) == (
        "urgent=false"
    )
    assert _apply(mappings["thread"]["properties"]["productArea"], machine_thread) == (
        ""
    )

import pytest
from jira.overrides import (
    JiraPortAppConfig,
    JiraBoardResourceConfig,
    JiraBoardSelector,
    JiraEpicSelector,
    JiraEpicResourceConfig,
    JiraWorklogResourceConfig,
    JiraWorklogSelector,
)


BOARD_MAPPING = {
    "entity": {
        "mappings": {
            "identifier": ".id | tostring",
            "title": ".name",
            "blueprint": '"jiraBoard"',
            "properties": {
                "type": ".type",
                "projectKey": ".location.projectKey",
                "displayName": ".location.displayName",
                "isPrivate": ".isPrivate",
                "url": ".self",
            },
            "relations": {
                "project": ".location.projectKey",
            },
        }
    }
}

WORKLOG_MAPPING = {
    "entity": {
        "mappings": {
            "identifier": ".id",
            "title": '.author.displayName + " - " + .started',
            "blueprint": '"jiraWorklog"',
            "properties": {
                "timeSpent": ".timeSpent",
                "timeSpentSeconds": ".timeSpentSeconds",
                "started": ".started",
                "created": ".created",
                "updated": ".updated",
                "authorAccountId": ".author.accountId",
                "authorDisplayName": ".author.displayName",
                "authorEmail": ".author.emailAddress",
            },
            "relations": {
                "issue": ".__issueKey",
            },
        }
    }
}


EPIC_MAPPING = {
    "identifier": ".id | tostring",
    "title": ".name // .key",
    "blueprint": '"jiraEpic"',
    "properties": {
        "summary": ".summary",
        "done": ".done",
        "name": ".name // .key",
    },
    "relations": {
        "board": ".__boardId",
    },
}


def test_jira_board_resource_config_parses_correctly() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "board",
                    "selector": {"query": "true"},
                    "port": BOARD_MAPPING,
                }
            ]
        }
    )
    assert len(config.resources) == 1
    assert isinstance(config.resources[0], JiraBoardResourceConfig)
    assert config.resources[0].kind == "board"


def test_jira_board_selector_defaults_are_none() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "board",
                    "selector": {"query": "true"},
                    "port": BOARD_MAPPING,
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraBoardResourceConfig)
    selector = config.resources[0].selector
    assert isinstance(selector, JiraBoardSelector)
    assert selector.board_type is None
    assert selector.project_key is None


def test_jira_board_selector_board_type_scrum() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "board",
                    "selector": {"query": "true", "boardType": "scrum"},
                    "port": BOARD_MAPPING,
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraBoardResourceConfig)
    assert config.resources[0].selector.board_type == "scrum"


def test_jira_board_selector_board_type_kanban() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "board",
                    "selector": {"query": "true", "boardType": "kanban"},
                    "port": BOARD_MAPPING,
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraBoardResourceConfig)
    assert config.resources[0].selector.board_type == "kanban"


def test_jira_board_selector_rejects_invalid_board_type() -> None:
    with pytest.raises(Exception):
        JiraBoardSelector.parse_obj({"query": "true", "boardType": "invalid"})


def test_jira_board_selector_accepts_simple_board_type() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "board",
                    "selector": {"query": "true", "boardType": "simple"},
                    "port": BOARD_MAPPING,
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraBoardResourceConfig)
    assert config.resources[0].selector.board_type == "simple"


def test_jira_board_selector_project_key_filter() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "board",
                    "selector": {"query": "true", "projectKey": "PORT"},
                    "port": BOARD_MAPPING,
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraBoardResourceConfig)
    assert config.resources[0].selector.project_key == "PORT"


def test_jira_board_selector_all_filters_combined() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "board",
                    "selector": {
                        "query": "true",
                        "boardType": "scrum",
                        "projectKey": "PORT",
                    },
                    "port": BOARD_MAPPING,
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraBoardResourceConfig)
    selector = config.resources[0].selector
    assert selector.board_type == "scrum"
    assert selector.project_key == "PORT"


def test_jira_board_selector_explicit_none_board_type_resolves_to_none() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "board",
                    "selector": {"query": "true", "boardType": None},
                    "port": BOARD_MAPPING,
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraBoardResourceConfig)
    assert config.resources[0].selector.board_type is None


@pytest.mark.parametrize(
    "invalid_project_key",
    [
        "",
        "   ",
        "\t",
        "\n",
    ],
)
def test_jira_board_selector_rejects_blank_project_key(
    invalid_project_key: str,
) -> None:
    with pytest.raises(Exception):
        JiraBoardSelector.parse_obj(
            {"query": "true", "projectKey": invalid_project_key}
        )


def test_epic_selector_defaults_to_incomplete_epics_only_for_performance() -> None:
    # Default done='false' protects large Jira instances from pulling full
    # epic history on first install — customers opt-in to done epics explicitly.
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "epic",
                    "selector": {"query": "true"},
                    "port": {"entity": {"mappings": EPIC_MAPPING}},
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraEpicResourceConfig)
    assert config.resources[0].selector.done == "false"


def test_epic_selector_accepts_done_true_to_fetch_completed_epics() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "epic",
                    "selector": {"query": "true", "done": "true"},
                    "port": {"entity": {"mappings": EPIC_MAPPING}},
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraEpicResourceConfig)
    assert config.resources[0].selector.done == "true"


def test_epic_selector_accepts_done_false_to_fetch_incomplete_epics() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "epic",
                    "selector": {"query": "true", "done": "false"},
                    "port": {"entity": {"mappings": EPIC_MAPPING}},
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraEpicResourceConfig)
    assert config.resources[0].selector.done == "false"


def test_epic_selector_accepts_none_to_fetch_all_epics() -> None:
    # None omits the done param entirely — fetches both complete and
    # incomplete epics. Customers opt-in explicitly knowing this is expensive
    # on large Jira instances.
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "epic",
                    "selector": {"query": "true", "done": None},
                    "port": {"entity": {"mappings": EPIC_MAPPING}},
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraEpicResourceConfig)
    assert config.resources[0].selector.done is None


def test_epic_selector_rejects_invalid_done_value() -> None:
    with pytest.raises(Exception):
        JiraEpicSelector.parse_obj(
            {
                "query": "true",
                "done": "invalid",
            }
        )


def test_epic_selector_rejects_boolean_done_value() -> None:
    # done must be the string 'true'/'false' per Jira API contract —
    # Python bool True/False is not a valid value."""
    with pytest.raises(Exception):
        JiraEpicSelector.parse_obj(
            {
                "query": "true",
                "done": True,
            }
        )


def test_epic_resource_config_parses_correctly() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "epic",
                    "selector": {"query": "true"},
                    "port": {"entity": {"mappings": EPIC_MAPPING}},
                }
            ]
        }
    )
    assert len(config.resources) == 1
    assert isinstance(config.resources[0], JiraEpicResourceConfig)

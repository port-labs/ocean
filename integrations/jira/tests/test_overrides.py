import pytest
from jira.overrides import (
    JiraPortAppConfig,
    JiraBoardResourceConfig,
    JiraBoardSelector,
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


def test_jira_worklog_resource_config_parses_correctly() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "worklog",
                    "selector": {"query": "true"},
                    "port": WORKLOG_MAPPING,
                }
            ]
        }
    )
    assert len(config.resources) == 1
    assert isinstance(config.resources[0], JiraWorklogResourceConfig)
    assert config.resources[0].kind == "worklog"


def test_jira_worklog_selector_defaults_are_correct() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "worklog",
                    "selector": {"query": "true"},
                    "port": WORKLOG_MAPPING,
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraWorklogResourceConfig)
    selector = config.resources[0].selector
    assert isinstance(selector, JiraWorklogSelector)
    assert selector.jql == "updated >= -1w"
    assert selector.api_query_params is None


def test_jira_worklog_selector_custom_jql() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "worklog",
                    "selector": {"query": "true", "jql": "project = TEST"},
                    "port": WORKLOG_MAPPING,
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraWorklogResourceConfig)
    assert config.resources[0].selector.jql == "project = TEST"


def test_jira_worklog_selector_started_after_filter() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "worklog",
                    "selector": {
                        "query": "true",
                        "apiQueryParams": {"startedAfter": 1700000000000},
                    },
                    "port": WORKLOG_MAPPING,
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraWorklogResourceConfig)
    selector = config.resources[0].selector
    assert selector.api_query_params is not None
    assert selector.api_query_params.started_after == 1700000000000


def test_jira_worklog_selector_started_before_filter() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "worklog",
                    "selector": {
                        "query": "true",
                        "apiQueryParams": {"startedBefore": 1800000000000},
                    },
                    "port": WORKLOG_MAPPING,
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraWorklogResourceConfig)
    selector = config.resources[0].selector
    assert selector.api_query_params is not None
    assert selector.api_query_params.started_before == 1800000000000


def test_jira_worklog_selector_expand_properties() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "worklog",
                    "selector": {
                        "query": "true",
                        "apiQueryParams": {"expand": "properties"},
                    },
                    "port": WORKLOG_MAPPING,
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraWorklogResourceConfig)
    selector = config.resources[0].selector
    assert selector.api_query_params is not None
    assert selector.api_query_params.expand == "properties"


def test_jira_worklog_selector_explicit_none_started_after_resolves_to_none() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "worklog",
                    "selector": {"query": "true"},
                    "port": WORKLOG_MAPPING,
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraWorklogResourceConfig)
    assert config.resources[0].selector.api_query_params is None


def test_jira_worklog_selector_explicit_none_started_before_resolves_to_none() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "worklog",
                    "selector": {"query": "true", "startedBefore": None},
                    "port": WORKLOG_MAPPING,
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraWorklogResourceConfig)
    assert config.resources[0].selector.api_query_params is None


def test_jira_worklog_selector_explicit_none_expand_resolves_to_none() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "worklog",
                    "selector": {"query": "true"},
                    "port": WORKLOG_MAPPING,
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraWorklogResourceConfig)
    assert config.resources[0].selector.api_query_params is None


def test_jira_worklog_selector_all_params_combined() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "worklog",
                    "selector": {
                        "query": "true",
                        "jql": "project = TEST",
                        "apiQueryParams": {
                            "startedAfter": 1700000000000,
                            "startedBefore": 1800000000000,
                            "expand": "properties",
                        },
                    },
                    "port": WORKLOG_MAPPING,
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraWorklogResourceConfig)
    selector = config.resources[0].selector
    assert selector.jql == "project = TEST"
    assert selector.api_query_params is not None
    assert selector.api_query_params.started_after == 1700000000000
    assert selector.api_query_params.started_before == 1800000000000
    assert selector.api_query_params.expand == "properties"


def test_jira_worklog_resource_config_is_distinct_from_board_config() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "board",
                    "selector": {"query": "true"},
                    "port": BOARD_MAPPING,
                },
                {
                    "kind": "worklog",
                    "selector": {"query": "true"},
                    "port": WORKLOG_MAPPING,
                },
            ]
        }
    )
    assert len(config.resources) == 2
    assert isinstance(config.resources[0], JiraBoardResourceConfig)
    assert isinstance(config.resources[1], JiraWorklogResourceConfig)


def test_epic_selector_accepts_incomplete_status() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "epic",
                    "selector": {"query": "true", "status": ["incomplete"]},
                    "port": {"entity": {"mappings": EPIC_MAPPING}},
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraEpicResourceConfig)
    assert config.resources[0].selector.status == ["incomplete"]


def test_epic_selector_accepts_complete_status() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "epic",
                    "selector": {"query": "true", "status": ["complete"]},
                    "port": {"entity": {"mappings": EPIC_MAPPING}},
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraEpicResourceConfig)
    assert config.resources[0].selector.status == ["complete"]


def test_epic_selector_accepts_none_to_fetch_all_epics() -> None:
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
    # omitting status entirely fetches all epics
    assert config.resources[0].selector.status == ["incomplete"]


def test_epic_selector_defaults_to_incomplete_status() -> None:
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
    assert config.resources[0].selector.status == ["incomplete"]


def test_epic_selector_accepts_both_statuses() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "epic",
                    "selector": {"query": "true", "status": ["complete", "incomplete"]},
                    "port": {"entity": {"mappings": EPIC_MAPPING}},
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraEpicResourceConfig)
    assert set(config.resources[0].selector.status) == {"complete", "incomplete"}


def test_epic_selector_accepts_none_status_to_fetch_all() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "epic",
                    "selector": {"query": "true", "status": None},
                    "port": {"entity": {"mappings": EPIC_MAPPING}},
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraEpicResourceConfig)
    assert config.resources[0].selector.status is None


def test_epic_selector_rejects_invalid_status_value() -> None:
    with pytest.raises(Exception):
        JiraPortAppConfig.parse_obj(
            {
                "resources": [
                    {
                        "kind": "epic",
                        "selector": {"query": "true", "status": ["invalid_value"]},
                        "port": {"entity": {"mappings": EPIC_MAPPING}},
                    }
                ]
            }
        )


def test_epic_selector_rejects_non_list_status() -> None:
    with pytest.raises(Exception):
        JiraPortAppConfig.parse_obj(
            {
                "resources": [
                    {
                        "kind": "epic",
                        "selector": {"query": "true", "status": "incomplete"},
                        "port": {"entity": {"mappings": EPIC_MAPPING}},
                    }
                ]
            }
        )

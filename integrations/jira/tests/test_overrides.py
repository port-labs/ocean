import pytest
from jira.overrides import (
    JiraPortAppConfig,
    JiraBoardResourceConfig,
    JiraBoardSelector,
    JiraBacklogResourceConfig,
    JiraBacklogSelector,
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

BACKLOG_MAPPING = {
    "entity": {
        "mappings": {
            "identifier": ".id | tostring",
            "title": ".fields.summary",
            "blueprint": '"jiraIssue"',
            "properties": {
                "status": ".fields.status.name",
                "priority": ".fields.priority.name",
                "assignee": ".fields.assignee.accountId",
                "created": ".fields.created",
                "updated": ".fields.updated",
            },
            "relations": {
                "board": ".__boardId | tostring",
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


def test_jira_backlog_resource_config_parses_correctly() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "backlog",
                    "selector": {"query": "true"},
                    "port": BACKLOG_MAPPING,
                }
            ]
        }
    )
    assert len(config.resources) == 1
    assert isinstance(config.resources[0], JiraBacklogResourceConfig)
    assert config.resources[0].kind == "backlog"


def test_jira_backlog_selector_defaults() -> None:
    """Defaults define out-of-box behavior — locking them down prevents silent
    behavior shifts from future changes to the schema."""
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "backlog",
                    "selector": {"query": "true"},
                    "port": BACKLOG_MAPPING,
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraBacklogResourceConfig)
    selector = config.resources[0].selector
    assert isinstance(selector, JiraBacklogSelector)
    assert selector.jql == "updated >= -1w OR statusCategory != Done"
    assert selector.fields is None
    assert selector.use_software_api is True


def test_jira_backlog_selector_accepts_custom_jql() -> None:
    selector = JiraBacklogSelector.parse_obj(
        {"query": "true", "jql": "project = PORT AND priority = High"}
    )
    assert selector.jql == "project = PORT AND priority = High"


def test_jira_backlog_selector_accepts_empty_jql_string() -> None:
    """Empty JQL is intentional — the field description states it fetches all
    backlog issues. The client passes JQL through verbatim, so customers can
    opt out of the default filter by setting jql to ''."""
    selector = JiraBacklogSelector.parse_obj({"query": "true", "jql": ""})
    assert selector.jql == ""


def test_jira_backlog_selector_accepts_fields_list() -> None:
    selector = JiraBacklogSelector.parse_obj(
        {
            "query": "true",
            "fields": ["id", "key", "summary", "status", "assignee"],
        }
    )
    assert selector.fields == ["id", "key", "summary", "status", "assignee"]


def test_jira_backlog_selector_accepts_empty_fields_list() -> None:
    """An empty list is distinct from None — it's explicit 'no fields',
    which the API will accept and return minimal payloads for."""
    selector = JiraBacklogSelector.parse_obj({"query": "true", "fields": []})
    assert selector.fields == []


def test_jira_backlog_selector_explicit_none_fields() -> None:
    selector = JiraBacklogSelector.parse_obj({"query": "true", "fields": None})
    assert selector.fields is None


def test_jira_backlog_selector_use_software_api_explicit_true() -> None:
    selector = JiraBacklogSelector.parse_obj({"query": "true", "useSoftwareApi": True})
    assert selector.use_software_api is True


def test_jira_backlog_selector_use_software_api_explicit_false() -> None:
    """Customers opt out of the new endpoint by setting useSoftwareApi to false,
    keeping them on the legacy agile/1.0 path until the November 2026 cutoff."""
    selector = JiraBacklogSelector.parse_obj({"query": "true", "useSoftwareApi": False})
    assert selector.use_software_api is False


def test_jira_backlog_selector_all_fields_combined() -> None:
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "backlog",
                    "selector": {
                        "query": "true",
                        "jql": "project = PORT",
                        "fields": ["id", "key", "summary"],
                        "useSoftwareApi": False,
                    },
                    "port": BACKLOG_MAPPING,
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraBacklogResourceConfig)
    selector = config.resources[0].selector
    assert selector.jql == "project = PORT"
    assert selector.fields == ["id", "key", "summary"]
    assert selector.use_software_api is False

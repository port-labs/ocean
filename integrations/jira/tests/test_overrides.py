import pytest
from jira.overrides import (
    JiraPortAppConfig,
    JiraBoardResourceConfig,
    JiraBoardSelector,
    JiraSprintSelector,
    JiraSprintResourceConfig,
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

SPRINT_MAPPING = {
    "identifier": ".id | tostring",
    "title": ".name",
    "blueprint": '"jiraSprint"',
    "properties": {
        "state": ".state",
        "startDate": ".startDate // null",
        "endDate": ".endDate // null",
        "completeDate": ".completeDate // null",
        "goal": ".goal // null",
    },
    "relations": {
        "board": ".originBoardId | tostring",
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


@pytest.mark.parametrize(
    "sprint_state, expected_joined",
    [
        (["active"], "active"),
        (["closed"], "closed"),
        (["future"], "future"),
        (["active", "closed"], "active,closed"),
        (["active", "future"], "active,future"),
        (["closed", "future"], "closed,future"),
        (["active", "closed", "future"], "active,closed,future"),
    ],
    ids=[
        "single_active",
        "single_closed",
        "single_future",
        "active_and_closed",
        "active_and_future",
        "closed_and_future",
        "all_three_states",
    ],
)
def test_sprint_selector_state_combinations_parse_correctly(
    sprint_state: list[str],
    expected_joined: str,
) -> None:
    """All valid state combinations must parse without error and produce
    correct comma-joined strings when passed to the API."""
    config = JiraPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "sprint",
                    "selector": {"query": "true", "sprintState": sprint_state},
                    "port": {"entity": {"mappings": SPRINT_MAPPING}},
                }
            ]
        }
    )
    assert isinstance(config.resources[0], JiraSprintResourceConfig)
    selector = config.resources[0].selector
    assert selector.sprint_state == sprint_state
    assert ",".join(selector.sprint_state) == expected_joined


@pytest.mark.parametrize(
    "invalid_sprint_state",
    [
        ["invalid"],
        ["active", "invalid"],
        ["ACTIVE"],
        ["Active"],
        ["sprint"],
        ["done"],
        ["open"],
    ],
    ids=[
        "fully_invalid_value",
        "mixed_valid_and_invalid",
        "uppercase_active",
        "titlecase_active",
        "sprint_literal",
        "done_not_valid",
        "open_not_valid",
    ],
)
def test_sprint_selector_rejects_invalid_state_values(
    invalid_sprint_state: list[str],
) -> None:
    with pytest.raises(Exception):
        JiraSprintSelector.parse_obj(
            {
                "query": "true",
                "sprintState": invalid_sprint_state,
            }
        )


@pytest.mark.parametrize(
    "duplicate_state",
    [
        ["active", "active"],
        ["closed", "closed"],
        ["future", "future"],
        ["active", "active", "future"],
        ["active", "closed", "active"],
    ],
    ids=[
        "duplicate_active",
        "duplicate_closed",
        "duplicate_future",
        "active_duplicated_with_future",
        "active_appears_twice_with_closed",
    ],
)
def test_sprint_selector_rejects_duplicate_state_values(
    duplicate_state: list[str],
) -> None:
    with pytest.raises(Exception):
        JiraSprintSelector.parse_obj(
            {
                "query": "true",
                "sprintState": duplicate_state,
            }
        )


class TestJiraSprintSelector:
    def test_sprint_selector_defaults_to_active_state(self) -> None:
        config = JiraPortAppConfig.parse_obj(
            {
                "resources": [
                    {
                        "kind": "sprint",
                        "selector": {"query": "true"},
                        "port": {"entity": {"mappings": SPRINT_MAPPING}},
                    }
                ]
            }
        )
        assert isinstance(config.resources[0], JiraSprintResourceConfig)
        assert config.resources[0].selector.sprint_state == ["active"]

    def test_sprint_selector_accepts_single_state(self) -> None:
        config = JiraPortAppConfig.parse_obj(
            {
                "resources": [
                    {
                        "kind": "sprint",
                        "selector": {"query": "true", "sprintState": ["closed"]},
                        "port": {"entity": {"mappings": SPRINT_MAPPING}},
                    }
                ]
            }
        )
        assert isinstance(config.resources[0], JiraSprintResourceConfig)
        assert config.resources[0].selector.sprint_state == ["closed"]

    def test_sprint_selector_accepts_multiple_states(self) -> None:
        config = JiraPortAppConfig.parse_obj(
            {
                "resources": [
                    {
                        "kind": "sprint",
                        "selector": {
                            "query": "true",
                            "sprintState": ["active", "future"],
                        },
                        "port": {"entity": {"mappings": SPRINT_MAPPING}},
                    }
                ]
            }
        )
        assert isinstance(config.resources[0], JiraSprintResourceConfig)
        assert config.resources[0].selector.sprint_state == ["active", "future"]

    def test_sprint_selector_accepts_all_three_states(self) -> None:
        config = JiraPortAppConfig.parse_obj(
            {
                "resources": [
                    {
                        "kind": "sprint",
                        "selector": {
                            "query": "true",
                            "sprintState": ["active", "closed", "future"],
                        },
                        "port": {"entity": {"mappings": SPRINT_MAPPING}},
                    }
                ]
            }
        )
        assert isinstance(config.resources[0], JiraSprintResourceConfig)
        assert config.resources[0].selector.sprint_state == [
            "active",
            "closed",
            "future",
        ]

    def test_sprint_selector_rejects_invalid_state(self) -> None:
        with pytest.raises(Exception):
            JiraSprintSelector.parse_obj(
                {
                    "query": "true",
                    "sprintState": ["invalid"],
                }
            )

    def test_sprint_selector_rejects_empty_state_list(self) -> None:
        with pytest.raises(Exception):
            JiraSprintSelector.parse_obj(
                {
                    "query": "true",
                    "sprintState": [],
                }
            )

    def test_sprint_selector_none_fetches_all_states(self) -> None:
        config = JiraPortAppConfig.parse_obj(
            {
                "resources": [
                    {
                        "kind": "sprint",
                        "selector": {"query": "true", "sprintState": None},
                        "port": {"entity": {"mappings": SPRINT_MAPPING}},
                    }
                ]
            }
        )
        assert isinstance(config.resources[0], JiraSprintResourceConfig)
        assert config.resources[0].selector.sprint_state is None

    def test_sprint_resource_config_parses_correctly(self) -> None:
        config = JiraPortAppConfig.parse_obj(
            {
                "resources": [
                    {
                        "kind": "sprint",
                        "selector": {"query": "true"},
                        "port": {"entity": {"mappings": SPRINT_MAPPING}},
                    }
                ]
            }
        )
        assert len(config.resources) == 1
        assert isinstance(config.resources[0], JiraSprintResourceConfig)

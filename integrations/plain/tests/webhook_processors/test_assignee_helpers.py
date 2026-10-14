from webhook_processors.utils import assignee_machine_user_id, assignee_user_id


def test_assignee_user_id_requires_email() -> None:
    assert (
        assignee_user_id(
            {
                "thread": {
                    "assignee": {
                        "id": "us_1",
                        "email": "ada@example.com",
                        "fullName": "Ada",
                    }
                }
            }
        )
        == "us_1"
    )
    assert (
        assignee_user_id({"thread": {"assignee": {"id": "mu_1", "fullName": "Bot"}}})
        is None
    )
    assert assignee_user_id({"thread": {"assignee": {"id": "sys_1"}}}) is None
    assert (
        assignee_user_id({"thread": {"assignee": {"__typename": "User", "id": "us_2"}}})
        == "us_2"
    )
    assert (
        assignee_user_id(
            {"thread": {"assignee": {"__typename": "MachineUser", "id": "mu_1"}}}
        )
        is None
    )


def test_assignee_machine_user_id_detects_typed_and_shaped_payloads() -> None:
    assert (
        assignee_machine_user_id(
            {"thread": {"assignee": {"id": "mu_1", "fullName": "Bot"}}}
        )
        == "mu_1"
    )
    assert (
        assignee_machine_user_id(
            {"thread": {"assignee": {"id": "mu_1", "publicName": "Bot"}}}
        )
        == "mu_1"
    )
    assert (
        assignee_machine_user_id(
            {"thread": {"assignee": {"__typename": "MachineUser", "id": "mu_typed"}}}
        )
        == "mu_typed"
    )
    assert (
        assignee_machine_user_id(
            {"thread": {"assignee": {"type": "MachineUser", "id": "mu_typed2"}}}
        )
        == "mu_typed2"
    )
    assert (
        assignee_machine_user_id(
            {"thread": {"assignee": {"type": "API_USER", "id": "mu_api"}}}
        )
        == "mu_api"
    )
    # Plain machine-user ids are mu_* even when the payload is id-only.
    assert (
        assignee_machine_user_id({"thread": {"assignee": {"id": "mu_only"}}})
        == "mu_only"
    )
    # System assignees are id-only without the mu_ prefix.
    assert assignee_machine_user_id({"thread": {"assignee": {"id": "sys_1"}}}) is None
    assert (
        assignee_machine_user_id(
            {"thread": {"assignee": {"__typename": "System", "id": "sys_1"}}}
        )
        is None
    )
    assert (
        assignee_machine_user_id(
            {
                "thread": {
                    "assignee": {
                        "id": "us_1",
                        "email": "ada@example.com",
                        "fullName": "Ada",
                    }
                }
            }
        )
        is None
    )
    assert assignee_machine_user_id({"thread": {"assignee": None}}) is None
    assert assignee_machine_user_id({"thread": {}}) is None

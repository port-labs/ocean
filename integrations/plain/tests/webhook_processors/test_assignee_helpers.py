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


def test_assignee_machine_user_id_requires_profile_fields() -> None:
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
    # System assignees are id-only; must not be treated as machine users.
    assert assignee_machine_user_id({"thread": {"assignee": {"id": "sys_1"}}}) is None
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

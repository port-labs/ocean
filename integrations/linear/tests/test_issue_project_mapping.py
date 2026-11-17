from linear.queries import QUERIES


def test_issue_query_fetches_project_identity() -> None:
    issue_fields = QUERIES["BASE_ISSUES_QUERY_FIELDS"]

    assert "project {" in issue_fields
    assert "id" in issue_fields.split("project {", 1)[1].split("}", 1)[0]
    assert "name" in issue_fields.split("project {", 1)[1].split("}", 1)[0]

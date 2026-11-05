from pathlib import Path

import yaml  # type: ignore[import-untyped]

from linear.queries import QUERIES


def test_issue_query_fetches_project_identity() -> None:
    issue_fields = QUERIES["BASE_ISSUES_QUERY_FIELDS"]

    assert "project {" in issue_fields
    assert "id" in issue_fields
    assert "name" in issue_fields


def test_issue_project_mapping_handles_missing_project() -> None:
    config_path = (
        Path(__file__).parents[1] / ".port" / "resources" / "port-app-config.yaml"
    )
    config = yaml.safe_load(config_path.read_text())
    issue_resource = next(
        resource for resource in config["resources"] if resource["kind"] == "issue"
    )
    mapping = issue_resource["port"]["entity"]["mappings"]["relations"]["project"]
    blueprint_path = (
        Path(__file__).parents[1] / ".port" / "resources" / "blueprints.json"
    )
    blueprints = yaml.safe_load(blueprint_path.read_text())
    issue_blueprint = next(
        blueprint
        for blueprint in blueprints
        if blueprint["identifier"] == "linearIssue"
    )
    project_relation = issue_blueprint["relations"]["project"]

    def mapped_project(issue: dict[str, object]) -> object:
        project = issue.get("project")
        return project.get("id") if isinstance(project, dict) else None

    assert mapping == ".project.id"
    assert project_relation == {
        "target": "linearProject",
        "title": "Project",
        "required": False,
        "many": False,
    }
    assert (
        mapped_project(
            {
                "identifier": "ENG-1",
                "project": {"id": "project-1", "name": "Roadmap"},
            }
        )
        == "project-1"
    )
    assert mapped_project({"identifier": "ENG-2", "project": None}) is None

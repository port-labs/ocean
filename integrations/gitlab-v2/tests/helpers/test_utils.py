from gitlab.helpers.utils import (
    build_search_query,
    enrich_resources_with_project,
)


class TestUtils:
    def test_enrich_resources_with_project(self) -> None:
        """Test enriching resources with project data"""
        # Arrange
        resources = [
            {"id": 1, "project_id": "123", "name": "Resource 1"},
            {"id": 2, "project_id": "456", "name": "Resource 2"},
            {"id": 3, "project_id": "789", "name": "Resource 3"},
        ]
        project_map = {
            "123": {"path_with_namespace": "group/project-a"},
            "456": {"path_with_namespace": "group/project-b"},
            "789": {"path_with_namespace": "group/project-c"},
        }

        # Act
        result = enrich_resources_with_project(resources, project_map)

        # Assert
        assert len(result) == 3
        assert result[0]["id"] == 1
        assert result[0]["__project"]["path_with_namespace"] == "group/project-a"
        assert result[1]["id"] == 2
        assert result[1]["__project"]["path_with_namespace"] == "group/project-b"
        assert result[2]["id"] == 3
        assert result[2]["__project"]["path_with_namespace"] == "group/project-c"


class TestBuildSearchQuery:
    def test_single_filename(self) -> None:
        assert build_search_query("readme.md") == "readme.md filename:readme.md"

    def test_single_filename_no_extension(self) -> None:
        assert build_search_query("Makefile") == "Makefile filename:Makefile"

    def test_simple_path(self) -> None:
        assert (
            build_search_query("home/file.yaml")
            == "file.yaml path:home filename:file.yaml"
        )

    def test_wildcard_path(self) -> None:
        assert (
            build_search_query("home/*/file.yaml")
            == "file.yaml path:home/* filename:file.yaml"
        )

    def test_nested_path(self) -> None:
        assert (
            build_search_query("src/config/settings.json")
            == "settings.json path:src/config filename:settings.json"
        )

    def test_glob_filename(self) -> None:
        assert build_search_query("*.yaml") == ".yaml filename:*.yaml"

    def test_glob_filename_in_path(self) -> None:
        assert (
            build_search_query("home/directory/*.txt")
            == ".txt path:home/directory filename:*.txt"
        )

    def test_glob_in_path_and_filename(self) -> None:
        assert build_search_query("home/*/*.txt") == ".txt path:home/* filename:*.txt"

    def test_dotfile_single(self) -> None:
        assert (
            build_search_query(".gitlab-ci.yml")
            == ".gitlab-ci.yml filename:.gitlab-ci.yml"
        )

    def test_dotfile_in_path(self) -> None:
        assert (
            build_search_query("ci/.gitlab-ci.yml")
            == ".gitlab-ci.yml path:ci filename:.gitlab-ci.yml"
        )

from typing import Any
import pytest

from gitlab.helpers.utils import enrich_resources_with_project


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
            "123": {"id": "123", "name": "Project A"},
            "456": {"id": "456", "name": "Project B"},
            "789": {"id": "789", "name": "Project C"},
        }

        # Act
        result = enrich_resources_with_project(resources, project_map)

        # Assert
        assert len(result) == 3
        assert result[0]["id"] == 1
        assert result[0]["__project"]["name"] == "Project A"
        assert result[1]["id"] == 2
        assert result[1]["__project"]["name"] == "Project B"
        assert result[2]["id"] == 3
        assert result[2]["__project"]["name"] == "Project C"

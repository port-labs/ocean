from typing import Any
from unittest.mock import MagicMock, Mock
from gitlab_integration.gitlab_service import GitlabService
from gitlab.base import RESTObject
import pytest


def mock_search(page: int, *args: Any, **kwargs: Any) -> Any:
    if page == 1:
        return [{"path": "hello/aaa/file.yaml"}]
    elif page == 2:
        return [
            {"path": "hello/my/file.yaml"},
            {"path": "hello/my/file2.yaml"},
            {"path": "hello/my/file3.yaml"},
        ]
    elif page == 3:
        return [
            {"path": "hello/my/file.yml"},
            {"path": "hello/my/file.json"},
            {"path": "hello/my/file.md"},
        ]
    else:
        return None


async def test_search_files_in_folders_in_project(
    monkeypatch: Any,
    mocked_gitlab_service: GitlabService,
    mock_get_and_parse_single_file: Any,
) -> None:
    # Arrange
    search_pattern = "**/my/file.yaml"
    mock_project = MagicMock()
    monkeypatch.setattr(mock_project, "search", mock_search)

    expected_files = ["hello/my/file.yaml"]
    # Act
    actual_files = []
    async for file in mocked_gitlab_service.search_files_in_project(
        mock_project, search_pattern
    ):
        actual_files.extend(file)

    # Assert
    assert len(actual_files) == 1
    assert actual_files == expected_files


async def test_search_files_in_project(
    monkeypatch: Any,
    mocked_gitlab_service: GitlabService,
    mock_get_and_parse_single_file: Any,
) -> None:
    # Arrange
    search_pattern = "**/file.yaml"

    mock_project = MagicMock()
    monkeypatch.setattr(mock_project, "search", mock_search)
    expected_files = ["hello/aaa/file.yaml", "hello/my/file.yaml"]
    # Act
    actual_files = []
    async for file in mocked_gitlab_service.search_files_in_project(
        mock_project, search_pattern
    ):
        actual_files.extend(file)

    # Assert
    assert len(actual_files) == 2
    assert actual_files == expected_files


async def test_search_generic_files_inside_folder_inside_folder_in_project(
    monkeypatch: Any,
    mocked_gitlab_service: GitlabService,
    mock_get_and_parse_single_file: Any,
) -> None:
    # Arrange
    search_pattern = "hello/**/file*"

    mock_project = MagicMock()
    monkeypatch.setattr(mock_project, "search", mock_search)
    expected_files = [
        "hello/aaa/file.yaml",
        "hello/my/file.yaml",
        "hello/my/file2.yaml",
        "hello/my/file3.yaml",
        "hello/my/file.yml",
        "hello/my/file.json",
        "hello/my/file.md",
    ]
    # Act
    actual_files = []
    async for file in mocked_gitlab_service.search_files_in_project(
        mock_project, search_pattern
    ):
        actual_files.extend(file)

    # Assert
    assert len(actual_files) == 7
    assert actual_files == expected_files


async def test_get_and_parse_single_file(
    monkeypatch: Any, mocked_gitlab_service: GitlabService
) -> None:
    # Arrange
    mock_file = MagicMock()
    monkeypatch.setattr(mock_file, "size", 1)
    mock_file.decode.return_value = b"file content"
    mock_file.asdict.return_value = {"content": "this should be overwritten"}

    mock_project = MagicMock()
    mock_project.files.get.return_value = mock_file
    mock_project.asdict.return_value = "project data"

    expected_parsed_single_file = {
        "file": {"content": "file content"},
        "repo": "project data",
    }

    # Act
    actual_parsed_single_file = await mocked_gitlab_service.get_and_parse_single_file(
        mock_project, "path", "branch"
    )

    # Assert
    assert expected_parsed_single_file == actual_parsed_single_file


async def test_get_and_parse_single_file_yaml(
    monkeypatch: Any, mocked_gitlab_service: GitlabService
) -> None:
    # Arrange
    mock_file = MagicMock()
    monkeypatch.setattr(mock_file, "size", 1)
    monkeypatch.setattr(mock_file, "file_name", "test.yml")
    monkeypatch.setattr(
        mock_file,
        "decode",
        lambda: b"""project: data
hello:
    value: world""",
    )
    mock_file.asdict.return_value = {"content": "this should be overwritten"}

    mock_project = MagicMock()
    mock_project.files.get.return_value = mock_file
    mock_project.asdict.return_value = "project data"

    expected_parsed_single_file = {
        "file": {"content": {"project": "data", "hello": {"value": "world"}}},
        "repo": "project data",
    }

    # Act
    actual_parsed_single_file = await mocked_gitlab_service.get_and_parse_single_file(
        mock_project, "path", "branch"
    )

    # Assert
    assert expected_parsed_single_file == actual_parsed_single_file


async def test_get_and_parse_single_file_json(
    monkeypatch: Any, mocked_gitlab_service: GitlabService
) -> None:
    # Arrange
    mock_file = MagicMock()
    monkeypatch.setattr(mock_file, "size", 1)
    monkeypatch.setattr(
        mock_file,
        "decode",
        lambda: """{
    "hello":"world"
}""",
    )
    mock_file.asdict.return_value = {"content": "this should be overwritten"}

    mock_project = MagicMock()
    mock_project.files.get.return_value = mock_file
    mock_project.asdict.return_value = "project data"

    expected_parsed_single_file = {
        "file": {"content": {"hello": "world"}},
        "repo": "project data",
    }

    # Act
    actual_parsed_single_file = await mocked_gitlab_service.get_and_parse_single_file(
        mock_project, "path", "branch"
    )

    # Assert
    assert expected_parsed_single_file == actual_parsed_single_file


class MockMember(RESTObject):
    def __init__(self, id, username, email, name):
        self.id = id
        self.username = username
        self.email = email
        self.name = name

    def asdict(self):
        return self.__dict__

    def __setattr__(self, name, value):
        self.__dict__[name] = value


class MockGroup(RESTObject):
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.members = self.MockMembers()
        self.members_all = self.MockMembersAll()

    class MockMembers:
        def list(self, page, *args: Any, **kwargs: Any):
            if page == 1:
                return [
                    MockMember(1, "user1", "user1@example.com", "user1"),
                    MockMember(1, "bot_user1", "bot_user1@example.com", "bot_user1"),
                ]
            elif page == 2:
                return [
                    MockMember(2, "user2", "user2@example.com", "user2"),
                    MockMember(2, "bot_user2", "bot_user2@example.com", "bot_user2"),
                ]
            elif page == 3:
                return [
                    MockMember(3, "user3", "user3@example.com", "user3"),
                    MockMember(3, "bot_user3", "bot_user3@example.com", "bot_user3"),
                ]
            return

    class MockMembersAll:
        def list(self, page, *args: Any, **kwargs: Any):
            if page == 1:
                return [
                    MockMember(1, "user1", "user1@example.com", "user1"),
                    MockMember(1, "bot_user1", "bot_user1@example.com", "bot_user1"),
                    MockMember(
                        1,
                        "inherited_member_1",
                        "inherited_member_1@example.com",
                        "inherited_member_1",
                    ),
                ]
            elif page == 2:
                return [
                    MockMember(2, "user2", "user2@example.com", "user2"),
                    MockMember(2, "bot_user2", "bot_user2@example.com", "bot_user2"),
                    MockMember(
                        2,
                        "inherited_member_2",
                        "inherited_member_2@example.com",
                        "inherited_member_2",
                    ),
                ]
            elif page == 3:
                return [
                    MockMember(3, "user3", "user3@example.com", "user3"),
                    MockMember(3, "bot_user3", "bot_user3@example.com", "bot_user3"),
                    MockMember(
                        3,
                        "inherited_member_3",
                        "inherited_member_3@example.com",
                        "inherited_member_3",
                    ),
                ]
            return

    def asdict(self):
        return {
            "id": self.id,
            "name": self.name,
            "path": f"get{self.name}-path",
            "full_name": self.name,
            "full_path": f"get{self.name}-path",
        }

    def __setattr__(self, name, value):
        self.__dict__[name] = value


def test_should_run_for_members(
    monkeypatch: Any, mocked_gitlab_service: GitlabService
) -> None:

    bot_member = Mock(spec=RESTObject)
    bot_member.username = "bot_user"

    non_bot_member = Mock(spec=RESTObject)
    non_bot_member.username = "regular_user"

    assert mocked_gitlab_service.should_run_for_members(True, bot_member) is True
    assert mocked_gitlab_service.should_run_for_members(True, non_bot_member) is True

    assert mocked_gitlab_service.should_run_for_members(False, bot_member) is False
    assert mocked_gitlab_service.should_run_for_members(False, non_bot_member) is True


@pytest.mark.asyncio
async def test_get_all_object_members(
    monkeypatch: Any, mocked_gitlab_service: GitlabService
) -> None:

    # Arrange
    obj = MockGroup(123, "test_project")

    # Act
    from typing import List

    results_without_inherited_members: List[RESTObject] = []
    async for members in mocked_gitlab_service.get_all_object_members(
        obj, include_inherited_members=False, include_bot_members=True
    ):
        results_without_inherited_members.extend(members)

    results_with_inherited_members: List[RESTObject] = []
    async for members in mocked_gitlab_service.get_all_object_members(
        obj, include_inherited_members=True, include_bot_members=True
    ):
        results_with_inherited_members.extend(members)

    results_without_bot_members: List[RESTObject] = []
    async for members in mocked_gitlab_service.get_all_object_members(
        obj, include_inherited_members=True, include_bot_members=False
    ):
        results_without_bot_members.extend(members)

    # Assert
    assert len(results_without_inherited_members) == 6
    assert results_without_inherited_members[0].username == "user1"
    assert results_without_inherited_members[1].username == "bot_user1"
    assert len(results_with_inherited_members) == 9
    assert len(results_without_bot_members) == 6


@pytest.mark.asyncio
async def test_enrich_object_with_members(
    monkeypatch: Any, mocked_gitlab_service: GitlabService
) -> None:

    # Arrange
    obj = MockGroup(123, "test_group")

    # Act
    enriched_obj: RESTObject = await mocked_gitlab_service.enrich_object_with_members(
        obj,
        include_inherited_members=False,
        include_bot_members=True,
    )

    # Assert
    assert enriched_obj.name == "test_group"
    assert len(enriched_obj.__members) == 3
    assert enriched_obj.__members[0] == {
        "id": 1,
        "username": "user1",
        "email": "user1@example.com",
    }


@pytest.mark.asyncio
async def test_enrich_object_with_members_verbose(
    monkeypatch: Any, mocked_gitlab_service: GitlabService
) -> None:
    obj = MockGroup(123, "test_group")

    # Act
    enriched_obj: RESTObject = await mocked_gitlab_service.enrich_object_with_members(
        obj,
        include_inherited_members=False,
        include_bot_members=True,
        include_verbose_member_object=True,
    )

    # Assert
    assert enriched_obj.name == "test_group"
    assert len(enriched_obj.__members) == 3
    assert enriched_obj.__members[0] == {
        "id": 1,
        "username": "user1",
        "email": "user1@example.com",
        "name": "user1",
    }

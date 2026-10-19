from integration import GitLabSkillSelector


def test_skill_include_skill_folder_defaults_to_false() -> None:
    properties = GitLabSkillSelector.schema(by_alias=True)["properties"]

    assert properties["includeSkillFolder"]["default"] is False
    assert GitLabSkillSelector(query="true").include_skill_folder is False
    assert GitLabSkillSelector(
        query="true", includeSkillFolder=True
    ).include_skill_folder

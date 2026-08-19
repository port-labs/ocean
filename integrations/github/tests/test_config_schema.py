from github.core.exporters.skill_exporter.utils import DEFAULT_SKILL_PATHS
from integration import GithubSkillSelector


def test_skill_path_defaults_omit_unset_repository_filters() -> None:
    defaults = GithubSkillSelector.schema()["properties"]["paths"]["default"]

    assert defaults == [
        {"path": path, "excludeArchived": False} for path in DEFAULT_SKILL_PATHS
    ]

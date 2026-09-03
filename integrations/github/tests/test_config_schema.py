from github.core.exporters.skill_exporter.utils import DEFAULT_SKILL_PATHS
from github.core.exporters.mcp_exporter.utils import DEFAULT_MCP_PATHS
from integration import GithubSkillSelector, GithubMcpSelector


def test_skill_path_defaults_omit_unset_repository_filters() -> None:
    defaults = GithubSkillSelector.schema()["properties"]["paths"]["default"]

    assert defaults == [{"path": path} for path in DEFAULT_SKILL_PATHS]


def test_mcp_path_defaults_omit_unset_repository_filters() -> None:
    defaults = GithubMcpSelector.schema()["properties"]["paths"]["default"]

    assert defaults == [{"path": path} for path in DEFAULT_MCP_PATHS]

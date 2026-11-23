from pathlib import Path

import yaml  # type: ignore[import-untyped]

from core.sessions_query import build_sessions_query
from integration import DevinPortAppConfig, SessionResourceConfig

RESOURCES_DIR = Path(__file__).parent.parent / ".port" / "resources"


def test_default_sessions_query() -> None:
    assert build_sessions_query(
        include_archived=False,
        created_after_days=30,
        origins=None,
        only_managed_by_port=False,
        now=100 * 86400,
    ) == {"is_archived": False, "created_after": 70 * 86400}


def test_sessions_query_with_every_selector() -> None:
    assert build_sessions_query(
        include_archived=True,
        created_after_days=None,
        origins=["api", "slack"],
        only_managed_by_port=True,
    ) == {"origins": ["api", "slack"], "tags": ["port:managed"]}


def test_default_port_app_config_parses() -> None:
    raw = yaml.safe_load((RESOURCES_DIR / "port-app-config.yml").read_text())

    config = DevinPortAppConfig.parse_obj(raw)

    kinds = [resource.kind for resource in config.resources]
    assert kinds == ["playbook", "knowledge-note", "secret", "session"]
    session = config.resources[-1]
    assert isinstance(session, SessionResourceConfig)
    assert session.selector.created_after_days == 30
    assert session.selector.only_managed_by_port is False
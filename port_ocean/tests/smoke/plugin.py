from __future__ import annotations

import os

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--smoke-config",
        action="store",
        default=None,
        help="Run smoke tests marked for this config (see port_ocean/tests/smoke/configs/)",
    )


def _selected_config_name(config: pytest.Config) -> str | None:
    return config.getoption("--smoke-config") or os.environ.get("SMOKE_TEST_CONFIG")


def _marker_args(item: pytest.Item, marker_name: str) -> set[str]:
    return {
        marker.args[0]
        for marker in item.iter_markers(marker_name)
        if marker.args and isinstance(marker.args[0], str)
    }


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    config_name = _selected_config_name(config)
    if config_name is None:
        return

    selected: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        if item.get_closest_marker("smoke") is None:
            deselected.append(item)
            continue
        if config_name in _marker_args(item, "smoke_config"):
            selected.append(item)
        else:
            deselected.append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
    items[:] = selected


def pytest_collection_finish(session: pytest.Session) -> None:
    for item in session.items:
        if item.get_closest_marker("smoke") is None:
            continue
        if not _marker_args(item, "smoke_config"):
            raise pytest.UsageError(
                f"{item.nodeid} is marked smoke but has no smoke_config marker"
            )

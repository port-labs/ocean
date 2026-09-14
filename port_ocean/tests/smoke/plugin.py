from __future__ import annotations

import os

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--smoke-profile",
        action="store",
        default=None,
        help="Collect/run smoke tests for a named profile (see port_ocean/tests/smoke/profiles/)",
    )


def _selected_profile_name(config: pytest.Config) -> str | None:
    return config.getoption("--smoke-profile") or os.environ.get("SMOKE_TEST_PROFILE")


def _marker_args(item: pytest.Item, marker_name: str) -> set[str]:
    return {
        marker.args[0]
        for marker in item.iter_markers(marker_name)
        if marker.args and isinstance(marker.args[0], str)
    }


def _should_include_item(item: pytest.Item, profile_name: str) -> bool:
    if item.get_closest_marker("smoke") is None:
        return False

    profile_markers = _marker_args(item, "smoke_profile")
    return profile_name in profile_markers


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    profile_name = _selected_profile_name(config)
    if profile_name is None:
        return

    selected: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        if _should_include_item(item, profile_name):
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
        if not _marker_args(item, "smoke_profile"):
            raise pytest.UsageError(
                f"{item.nodeid} is marked smoke but has no smoke_profile marker"
            )

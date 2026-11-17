"""Load and merge mock route YAML files (later files override by route id)."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Iterable

import yaml
from pydantic import ValidationError

from port_ocean.validation.mock_server.exceptions import RouteFileLoadError
from port_ocean.validation.mock_server.models import MockRoute, MockRouteFile


def load_route_file(path: Path | str) -> MockRouteFile:
    """Parse and validate a single route YAML file.

    Raises:
        RouteFileLoadError: If the file is missing, not valid YAML, or fails
            schema validation. The exception message always includes the path.
    """
    route_path = Path(path)
    if not route_path.is_file():
        raise RouteFileLoadError(route_path, "file not found")

    try:
        raw_text = route_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RouteFileLoadError(route_path, f"could not read file: {exc}") from exc

    try:
        raw = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise RouteFileLoadError(route_path, f"invalid YAML: {exc}") from exc

    if raw is None:
        raw = {"routes": []}
    if not isinstance(raw, dict):
        raise RouteFileLoadError(
            route_path,
            f"expected a YAML mapping with a 'routes' key, got {type(raw).__name__}",
        )

    try:
        return MockRouteFile.model_validate(raw)
    except ValidationError as exc:
        raise RouteFileLoadError(route_path, _format_validation_error(exc)) from exc


def load_route_files(paths: Iterable[Path | str]) -> list[MockRoute]:
    """Load route files in order; later files override routes with the same ``id``.

    Route order follows first appearance, and an override moves that id to the
    end so file order (used for matching ties) reflects the latest definition.
    """
    merged: OrderedDict[str, MockRoute] = OrderedDict()

    for path in paths:
        route_file = load_route_file(path)
        for route in route_file.routes:
            if route.id in merged:
                merged.move_to_end(route.id)
            merged[route.id] = route

    return list(merged.values())


def _format_validation_error(exc: ValidationError) -> str:
    """Turn a Pydantic ValidationError into a short, file-level message."""
    parts: list[str] = []
    for error in exc.errors():
        loc = ".".join(str(item) for item in error.get("loc", ()))
        msg = error.get("msg", "validation error")
        if loc:
            parts.append(f"{loc}: {msg}")
        else:
            parts.append(msg)
    return "; ".join(parts) if parts else str(exc)

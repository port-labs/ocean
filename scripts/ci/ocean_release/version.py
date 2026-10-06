"""Semver parsing and bumping for Ocean versions."""

from __future__ import annotations

import re

from .models import ParsedVersion

CHANGELOG_SECTIONS = {
    "breaking": "Breaking Changes",
    "deprecation": "Deprecations",
    "feature": "Features",
    "improvement": "Improvements",
    "bugfix": "Bug Fixes",
    "doc": "Improved Documentation",
}

VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
NAME_RE = re.compile(r'^name = "([^"]+)"', re.MULTILINE)
OCEAN_VERSION_RE = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?P<suffix>-(?:beta|dev|post1))?$"
)
LEGACY_DOT_SUFFIX_RE = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)\."
    r"(?P<prefix>[a-zA-Z]+)(?P<number>\d+)$"
)


def parse_version(pyproject_content: str) -> str:
    match = VERSION_RE.search(pyproject_content)
    if not match:
        raise ValueError("Could not find version in pyproject.toml")
    return match.group(1)


def parse_integration_type(pyproject_content: str, fallback: str) -> str:
    match = NAME_RE.search(pyproject_content)
    return match.group(1) if match else fallback


def set_version(pyproject_content: str, new_version: str) -> str:
    if not VERSION_RE.search(pyproject_content):
        raise ValueError("Could not find version in pyproject.toml")
    return VERSION_RE.sub(f'version = "{new_version}"', pyproject_content, count=1)


def is_valid_ocean_version(version: str) -> bool:
    return bool(OCEAN_VERSION_RE.match(version) or LEGACY_DOT_SUFFIX_RE.match(version))


def parse_ocean_version(version: str) -> ParsedVersion:
    match = OCEAN_VERSION_RE.match(version)
    if match:
        return ParsedVersion(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
            suffix=match.group("suffix") or "",
        )
    raise ValueError(
        f"Unsupported version format: {version}. "
        "Allowed: X.Y.Z, X.Y.Z-beta, X.Y.Z-dev, X.Y.Z-post1"
    )


def bump_legacy_dot_suffix(version: str, level: str) -> str:
    match = LEGACY_DOT_SUFFIX_RE.match(version)
    if not match:
        raise ValueError(f"Not a legacy dot-suffix version: {version}")
    if level != "patch":
        raise ValueError(
            f"Only patch bumps are supported for legacy dot-suffix versions: {version}"
        )

    prefix = match.group("prefix")
    number = int(match.group("number")) + 1
    return (
        f"{match.group('major')}.{match.group('minor')}.{match.group('patch')}."
        f"{prefix}{number}"
    )


def bump_version(version: str, level: str) -> str:
    if LEGACY_DOT_SUFFIX_RE.match(version):
        return bump_legacy_dot_suffix(version, level)

    parsed = parse_ocean_version(version)
    if level == "patch":
        parsed = ParsedVersion(
            parsed.major, parsed.minor, parsed.patch + 1, parsed.suffix
        )
    elif level == "minor":
        parsed = ParsedVersion(parsed.major, parsed.minor + 1, 0, parsed.suffix)
    else:
        parsed = ParsedVersion(parsed.major + 1, 0, 0, parsed.suffix)

    return parsed.format()


def validate_target_version_label(target_label: str, version: str) -> list[str]:
    if not is_valid_ocean_version(version):
        return [
            f"{target_label}: unsupported version format '{version}' "
            "(allowed: X.Y.Z, X.Y.Z-beta, X.Y.Z-dev, X.Y.Z-post1)"
        ]
    return []

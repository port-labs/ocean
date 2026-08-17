#!/usr/bin/env python3
"""Validate Ocean changelog structure.

Spacing rules match towncrier output from ``bump-all.sh`` (integration ``towncrier build``):
- 2 blank lines after ``## X.Y.Z (YYYY-MM-DD)``
- 1 blank line after ``### Section``
- 2 blank lines between entry content and the next ``##`` version header

Pass changelog paths via ``--paths``. Only paths in ``ALLOWED_CHANGELOG_PATHS`` are validated.

    python scripts/validate_changelog.py --paths CHANGELOG.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

STANDARD_SECTIONS = frozenset(
    {
        "Bug Fixes",
        "Improvements",
        "Features",
        "Deprecations",
        "Vulnerabilities",
        "Breaking Changes",
        "Improved Documentation",
    }
)

# towncrier blank-line spacing (matches bump-all.sh integration changelog output)
BLANK_LINES_AFTER_VERSION = 2
BLANK_LINES_AFTER_SECTION = 1
BLANK_LINES_BEFORE_VERSION = 2

VERSION_DATE_RE = (
    r"(?P<version>\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?)\s+\((?P<date>\d{4}-\d{2}-\d{2})\)"
)
BARE_VERSION_RE = re.compile(rf"^\s*{VERSION_DATE_RE}\s*$")
RST_UNDERLINE_RE = re.compile(r"^[-=*]{3,}\s*$")
SECTION_HEADER_RE = re.compile(r"^### (.+)$")
CANONICAL_VERSION_RE = re.compile(rf"^## {VERSION_DATE_RE}$")
INTEGRATION_PREFIX_RE = re.compile(
    rf"^#+\s*(?:Port_Ocean|Port Ocean|[A-Za-z][A-Za-z0-9_-]*)\s+{VERSION_DATE_RE}\s*$",
    re.IGNORECASE,
)
SINGLE_HASH_VERSION_RE = re.compile(rf"^#\s+{VERSION_DATE_RE}\s*$")
BULLET_RE = re.compile(r"^[-*]\s+")


def resolve_changelog_path(path: Path | str) -> Path:
    resolved = Path(path)
    if resolved.is_absolute():
        return resolved
    return REPO_ROOT / resolved


def count_blank_lines_after(lines: list[str], start_index: int) -> tuple[int, int]:
    cursor = start_index
    while cursor < len(lines) and lines[cursor].strip() == "":
        cursor += 1
    return cursor - start_index, cursor


def count_blank_lines_before(lines: list[str], index: int) -> int:
    blank_count = 0
    cursor = index - 1
    while cursor >= 0 and lines[cursor].strip() == "":
        blank_count += 1
        cursor -= 1
    return blank_count


def validate_spacing(path: Path, lines: list[str]) -> list[str]:
    """Enforce towncrier-style blank-line spacing around version and section headers."""
    errors: list[str] = []
    index = 0
    while index < len(lines):
        version_match = CANONICAL_VERSION_RE.match(lines[index])
        if not version_match:
            index += 1
            continue

        version_line_number = index + 1
        version = version_match.group("version")

        blank_after_version, cursor = count_blank_lines_after(lines, index + 1)
        if cursor >= len(lines):
            index = cursor
            continue

        if blank_after_version != BLANK_LINES_AFTER_VERSION:
            errors.append(
                f"{path}:{version_line_number}: version {version} must have exactly "
                f"{BLANK_LINES_AFTER_VERSION} blank lines after the version header "
                f"(found {blank_after_version})"
            )

        while cursor < len(lines) and not lines[cursor].startswith("## "):
            line = lines[cursor]
            if not line.startswith("### "):
                cursor += 1
                continue

            section_line_number = cursor + 1
            section_name = line[4:].strip()
            blank_after_section, section_cursor = count_blank_lines_after(
                lines, cursor + 1
            )

            if blank_after_section != BLANK_LINES_AFTER_SECTION:
                errors.append(
                    f"{path}:{section_line_number}: section '{section_name}' must have exactly "
                    f"{BLANK_LINES_AFTER_SECTION} blank line after the section header "
                    f"(found {blank_after_section})"
                )

            content_cursor = section_cursor
            while content_cursor < len(lines):
                if lines[content_cursor].startswith("## ") or lines[
                    content_cursor
                ].startswith("### "):
                    break
                content_cursor += 1

            cursor = content_cursor

        if cursor < len(lines) and lines[cursor].startswith("## "):
            blank_before_next_version = count_blank_lines_before(lines, cursor)
            if blank_before_next_version != BLANK_LINES_BEFORE_VERSION:
                errors.append(
                    f"{path}:{cursor + 1}: must have exactly {BLANK_LINES_BEFORE_VERSION} blank "
                    f"lines between the previous entry content and the next version header "
                    f"(found {blank_before_next_version})"
                )

        index = cursor
    return errors


def validate_changelog(path: Path) -> list[str]:
    errors: list[str] = []
    lines = path.read_text().splitlines()

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue

        if RST_UNDERLINE_RE.match(stripped):
            errors.append(f"{path}:{line_number}: RST-style underline is not allowed")

        if (
            stripped.startswith("# ")
            and not stripped.startswith("## ")
            and stripped != "# Changelog"
        ):
            if (
                BARE_VERSION_RE.match(stripped)
                or SINGLE_HASH_VERSION_RE.match(stripped)
                or "Port_Ocean" in stripped
                or INTEGRATION_PREFIX_RE.match(stripped)
            ):
                errors.append(
                    f"{path}:{line_number}: version header must use '##' instead of '#'"
                )

        if stripped.startswith("v## "):
            errors.append(
                f"{path}:{line_number}: version header must not include a leading 'v'"
            )

        if INTEGRATION_PREFIX_RE.match(stripped):
            errors.append(
                f"{path}:{line_number}: version header must not include integration name prefix"
            )

        if BARE_VERSION_RE.match(stripped):
            errors.append(
                f"{path}:{line_number}: version header must be '## X.Y.Z (YYYY-MM-DD)'"
            )

        if stripped.startswith("## ") and not CANONICAL_VERSION_RE.match(stripped):
            if re.search(VERSION_DATE_RE, stripped):
                errors.append(
                    f"{path}:{line_number}: version header must be '## X.Y.Z (YYYY-MM-DD)'"
                )

        section_match = SECTION_HEADER_RE.match(stripped)
        if section_match and section_match.group(1).strip() not in STANDARD_SECTIONS:
            errors.append(
                f"{path}:{line_number}: non-standard section header '{section_match.group(1)}'"
            )

    for line_number, line in enumerate(lines, start=1):
        version_match = CANONICAL_VERSION_RE.match(line)
        if not version_match:
            continue

        version = version_match.group("version")
        next_index = line_number
        while next_index < len(lines) and lines[next_index].strip() == "":
            next_index += 1

        if next_index >= len(lines):
            errors.append(
                f"{path}:{line_number}: version {version} has no changelog content"
            )
            continue

        next_line = lines[next_index]
        if BULLET_RE.match(next_line.strip()):
            errors.append(
                f"{path}:{line_number}: version {version} is missing a section header"
            )
        elif next_line.startswith("## "):
            errors.append(
                f"{path}:{line_number}: version {version} has no changelog content"
            )

    errors.extend(validate_spacing(path, lines))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Ocean changelog structure")
    parser.add_argument(
        "--paths",
        nargs="+",
        required=True,
        metavar="PATH",
        help="Changelog paths to validate (only allowlisted paths are checked)",
    )
    args = parser.parse_args()
    paths = args.paths

    print("Received paths:", paths, sep=", ")
    if not paths:
        print("No changelogs to validate; skipping")
        return 0

    all_errors: list[str] = []
    for path in paths:
        if not path.exists():
            all_errors.append(f"{path}: file does not exist")
            continue
        all_errors.extend(validate_changelog(path))

    if not all_errors:
        print(f"Changelog validation passed for {len(paths)} file(s)")
        for path in paths:
            print(f"  {path}")
        return 0

    print(
        f"Changelog validation failed with {len(all_errors)} errors:", file=sys.stderr
    )
    for error in all_errors:
        print(f"  - {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

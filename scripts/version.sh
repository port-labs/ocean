#!/usr/bin/env bash

# Read the project version as written in pyproject.toml.
# Prefer this over `poetry version --short`, which Poetry 2 normalizes to PEP 440
# (e.g. 0.1.315-dev -> 0.1.315.dev0, 2.18.4-beta -> 2.18.4b0).
get_pyproject_version() {
    grep -m1 '^version = ' pyproject.toml | cut -d'"' -f2
}

# Bump the patch level using Ocean's version rules (scripts/ci/ocean_release/version.py).
bump_patch_version() {
    local version="${1:?version required}"
    local root_dir="${2:?root_dir required}"
    PYTHONPATH="${root_dir}/scripts/ci" python3 -c "
from ocean_release.version import bump_version
print(bump_version('${version}', 'patch'))
"
}

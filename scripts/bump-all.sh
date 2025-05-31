#!/usr/bin/env bash

SCRIPT_BASE="$(cd -P "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd -P "${SCRIPT_BASE}/../" && pwd)"
CURRENT_DIR=$(pwd)
VERSION="^${1:-$(pip index versions port-ocean | grep 'port-ocean' | cut -d' ' -f2 | tr -d '()')}"

echo "Going to bump ocean core to version ${VERSION} for all integrations"

# Loop through each folder in the 'integrations' directory
for FOLDER in "${ROOT_DIR}"/integrations/*; do
    if [[ ! -d "${FOLDER}" || ! -f "${FOLDER}"/pyproject.toml ]]; then
        continue
    fi

    INTEGRATION=$(basename "${FOLDER}")

    echo "Bumping integration ${INTEGRATION}"

    cd "${FOLDER}" || return

    echo "Run 'make install'"
    make install

    echo "Enter the Python virtual environment in the .venv folder"
    source .venv/bin/activate

    echo "Bump the version ocean version using Poetry"
    poetry add "port-ocean@${VERSION}" -E cli --no-cache

    echo "Run towncrier create"
    towncrier create --content "Bumped ocean version to ${VERSION}" +random.improvement.md

    echo "Run towncrier build"
    CURRENT_VERSION=$(poetry version --short)

    echo "Current version: ${CURRENT_VERSION}, updating patch version"
    IFS='.' read -ra VERSION_COMPONENTS <<< "${CURRENT_VERSION}"

    # Regex patterns
    NUMBER_ONLY='^[0-9]+$'
    NUMERIC_SUFFIX_REGEX='^([a-zA-Z]+)([0-9]+)$'   # e.g., post1, dev2
    PATCH_WITH_SUFFIX='^([0-9]+)([^0-9].*)$'       # e.g., 1a, 2-beta, 3.post1

    MAJOR_VERSION="${VERSION_COMPONENTS[0]}"
    MINOR_VERSION="${VERSION_COMPONENTS[1]}"
    PATCH_VERSION="${VERSION_COMPONENTS[2]}"
    SUFFIX=""
    if [[ ${#VERSION_COMPONENTS[@]} -gt 3 ]]; then
        SUFFIX="${VERSION_COMPONENTS[3]}"
    fi

    # Case 1: suffix exists and is in format like post1, dev2 — bump the numeric part of the suffix
    if [[ -n "${SUFFIX}" && "${SUFFIX}" =~ ${NUMERIC_SUFFIX_REGEX} ]]; then
        SUFFIX_PREFIX=${BASH_REMATCH[1]}   # e.g., post
        SUFFIX_NUMBER=${BASH_REMATCH[2]}   # e.g., 1
        ((SUFFIX_NUMBER++))
        SUFFIX="${SUFFIX_PREFIX}${SUFFIX_NUMBER}"
        NEW_VERSION="${MAJOR_VERSION}.${MINOR_VERSION}.${PATCH_VERSION}.${SUFFIX}"

    # Case 2: PATCH_VERSION contains something like 1a, 2-beta, etc. — bump the numeric part, preserve suffix
    elif [[ ! ${PATCH_VERSION} =~ ${NUMBER_ONLY} && ${PATCH_VERSION} =~ ${PATCH_WITH_SUFFIX} ]]; then
        NUMERIC_PART=${BASH_REMATCH[1]}
        NON_NUMERIC=${BASH_REMATCH[2]}
        ((NUMERIC_PART++))
        PATCH_VERSION="${NUMERIC_PART}${NON_NUMERIC}"
        NEW_VERSION="${MAJOR_VERSION}.${MINOR_VERSION}.${PATCH_VERSION}"

    # Case 3: regular version, just bump patch
    else
        ((PATCH_VERSION++))
        NEW_VERSION="${MAJOR_VERSION}.${MINOR_VERSION}.${PATCH_VERSION}"
    fi


    poetry version "${NEW_VERSION}"
    echo "New version: ${NEW_VERSION}"

    echo "Run towncrier build to increment the patch version"
    towncrier build --keep --version "${NEW_VERSION}" && rm changelog/*
    git add poetry.lock pyproject.toml CHANGELOG.md
    echo "Committing ${INTEGRATION}"
    SKIP="trailing-whitespace,end-of-file-fixer" git commit -m "Bumped ocean version to ${VERSION} for ${INTEGRATION}"
    deactivate
done
cd "${CURRENT_DIR}" || return

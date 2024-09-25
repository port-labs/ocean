#!/usr/bin/env bash

SCRIPT_BASE="$(cd -P "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd -P "${SCRIPT_BASE}/../" && pwd)"
CURRENT_DIR=$(pwd)
VERSION="^${1:-$(poetry search port-ocean | grep port-ocean | sed 's/.*(\(.*\))/\1/')}"

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

    NON_NUMBER_ONLY='^[0-9]{1,}(.+)$'
    NUMBER_ONLY='^[0-9]{1,}$'

    MAJOR_VERSION="${VERSION_COMPONENTS[0]}"
    MINOR_VERSION="${VERSION_COMPONENTS[1]}"
    PATCH_VERSION="${VERSION_COMPONENTS[2]}"

    if [[ ! ${PATCH_VERSION} =~ ${NUMBER_ONLY} && ${PATCH_VERSION} =~ ${NON_NUMBER_ONLY} ]]; then
        echo "Found non release version ${CURRENT_VERSION}"
        NON_NUMERIC=${BASH_REMATCH[1]}
        ((PATCH_VERSION++))
        PATCH_VERSION="${PATCH_VERSION}${NON_NUMERIC}"
    else
        ((PATCH_VERSION++))
    fi
    NEW_VERSION="${MAJOR_VERSION}.${MINOR_VERSION}.${PATCH_VERSION}"

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

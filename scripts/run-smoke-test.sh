#!/usr/bin/env bash

# Requires docker and the following ENV vars:
#
# PORT_CLIENT_ID
# PORT_CLIENT_SECRET
# PORT_BASE_URL (optional, defaults to 'https://api.getport.io')
#

SCRIPT_BASE="$(cd -P "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd -P "${SCRIPT_BASE}/../" && pwd)"

RANDOM_ID=""
if [[ -n ${SMOKE_TEST_SUFFIX} ]]; then
    RANDOM_ID="-${SMOKE_TEST_SUFFIX}"
fi
INTEGRATION_IDENTIFIER="smoke-test-integration${RANDOM_ID}"
BLUEPRINT_DEPARTMENT="fake-department${RANDOM_ID}"
BLUEPRINT_PERSON="fake-person${RANDOM_ID}"
PORT_BASE_URL_FOR_DOCKER=${PORT_BASE_URL}

if [[ ${PORT_BASE_URL} =~ localhost ]]; then
    # NOTE: This is to support running this script on a local docker.
    # It allows the container to access Port API running on the docker host.
    PORT_BASE_URL_FOR_DOCKER=${PORT_BASE_URL//localhost/host.docker.internal}
fi

# NOTE: Make the blueprints and mapping immutable by adding a random suffix
TEMP_DIR=$(mktemp -d -t smoke-test-integration.XXXXXXX)
RESOURCE_DIR_SUFFIX="integrations/fake-integration/.port/resources"
cp -r "${ROOT_DIR}"/${RESOURCE_DIR_SUFFIX} "${TEMP_DIR}"

sed -i.bak "s/fake-department/${BLUEPRINT_DEPARTMENT}/g" "${TEMP_DIR}"/resources/blueprints.json
sed -i.bak "s/fake-person/${BLUEPRINT_PERSON}/g" "${TEMP_DIR}"/resources/blueprints.json
sed -i.bak "s/\"fake-department\"/\"${BLUEPRINT_DEPARTMENT}\"/g" "${TEMP_DIR}"/resources/port-app-config.yml
sed -i.bak "s/\"fake-person\"/\"${BLUEPRINT_PERSON}\"/g" "${TEMP_DIR}"/resources/port-app-config.yml

TAR_FULL_PATH=$(ls "${ROOT_DIR}"/dist/*.tar.gz)
if [[ $? != 0 ]]; then
    echo "Build file not found, run 'make build' once first!"
    exit 1
fi
TAR_FILE=$(basename "${TAR_FULL_PATH}")

FAKE_INTEGRATION_VERSION=$(grep -E '^version = ".*"' "${ROOT_DIR}/integrations/fake-integration/pyproject.toml" | cut -d'"' -f2)

echo "Found release ${TAR_FILE}, triggering fake integration with ID: '${INTEGRATION_IDENTIFIER}'"

# NOTE: Runs the fake integration with the modified blueprints and install the current core for a single sync
docker run --rm -i \
    --entrypoint 'bash' \
    -v "${TAR_FULL_PATH}:/opt/dist/${TAR_FILE}" \
    -v "${TEMP_DIR}/resources:/app/.port/resources" \
    -e OCEAN__PORT__BASE_URL="${PORT_BASE_URL_FOR_DOCKER}" \
    -e OCEAN__PORT__CLIENT_ID="${PORT_CLIENT_ID}" \
    -e OCEAN__PORT__CLIENT_SECRET="${PORT_CLIENT_SECRET}" \
    -e OCEAN__EVENT_LISTENER='{"type": "POLLING"}' \
    -e OCEAN__INTEGRATION__TYPE="smoke-test" \
    -e OCEAN__INTEGRATION__IDENTIFIER="${INTEGRATION_IDENTIFIER}" \
    --name=ZOMG-TEST \
    "ghcr.io/port-labs/port-ocean-fake-integration:${FAKE_INTEGRATION_VERSION}" \
    -c "source ./.venv/bin/activate && pip install --root-user-action=ignore /opt/dist/${TAR_FILE}[cli] && ocean sail -O"

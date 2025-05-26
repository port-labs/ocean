#!/usr/bin/env bash

# Requires docker and the following ENV vars:
#
# PORT_CLIENT_ID
# PORT_CLIENT_SECRET
# PORT_BASE_URL (optional, defaults to 'https://api.getport.io')
#

SCRIPT_BASE="$(cd -P "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd -P "${SCRIPT_BASE}/../" && pwd)"

source "${SCRIPT_BASE}/smoke-test-base.sh"

PORT_BASE_URL_FOR_DOCKER=${PORT_BASE_URL}

if [[ ${PORT_BASE_URL} =~ localhost ]]; then
    # NOTE: This is to support running this script on a local docker.
    # It allows the container to access Port API running on the docker host.
    PORT_BASE_URL_FOR_DOCKER=${PORT_BASE_URL//localhost/host.docker.internal}
fi


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
    -v "${TEMP_RESOURCES_DIR}:/opt/port-resources" \
    -e OCEAN__PORT__BASE_URL="${PORT_BASE_URL_FOR_DOCKER}" \
    -e OCEAN__PORT__CLIENT_ID="${PORT_CLIENT_ID}" \
    -e OCEAN__PORT__CLIENT_SECRET="${PORT_CLIENT_SECRET}" \
    -e OCEAN__EVENT_LISTENER='{"type": "POLLING"}' \
    -e OCEAN__INTEGRATION__TYPE="smoke-test" \
    -e OCEAN__INTEGRATION__IDENTIFIER="${INTEGRATION_IDENTIFIER}" \
    -e OCEAN__INTEGRATION__CONFIG__ENTITY_AMOUNT="${OCEAN__INTEGRATION__CONFIG__ENTITY_AMOUNT:--1}" \
    -e OCEAN__INTEGRATION__CONFIG__ENTITY_KB_SIZE="${OCEAN__INTEGRATION__CONFIG__ENTITY_KB_SIZE:--1}" \
    -e OCEAN__INTEGRATION__CONFIG__THIRD_PARTY_BATCH_SIZE="${OCEAN__INTEGRATION__CONFIG__THIRD_PARTY_BATCH_SIZE:--1}" \
    -e OCEAN__INTEGRATION__CONFIG__THIRD_PARTY_LATENCY_MS="${OCEAN__INTEGRATION__CONFIG__THIRD_PARTY_LATENCY_MS:--1}" \
    -e OCEAN__METRICS="${OCEAN__METRICS:--1}" \
    -e OCEAN__RUNTIME_MODE="${OCEAN__RUNTIME_MODE:-single_process}" \
    -e PROMETHEUS_MULTIPROC_DIR="/tmp" \
    -e OCEAN__RESOURCES_PATH="/opt/port-resources" \
    -e APPLICATION__LOG_LEVEL="DEBUG" \
    --name=ZOMG-TEST \
    "ghcr.io/port-labs/port-ocean-fake-integration:${FAKE_INTEGRATION_VERSION}" \
    -c "source ./.venv/bin/activate && pip install --root-user-action=ignore /opt/dist/${TAR_FILE}[cli] && ocean sail -O"

rm -rf "${TEMP_DIR}"

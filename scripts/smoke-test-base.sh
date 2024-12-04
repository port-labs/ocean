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
export INTEGRATION_IDENTIFIER="smoke-test-integration${RANDOM_ID}"
export BLUEPRINT_DEPARTMENT="fake-department${RANDOM_ID}"
export BLUEPRINT_PERSON="fake-person${RANDOM_ID}"

# NOTE: Make the blueprints and mapping immutable by adding a random suffix
TEMP_DIR=$(mktemp -d -t smoke-test-integration.XXXXXXX)
RESOURCE_DIR_SUFFIX="integrations/fake-integration/.port/resources"
cp -r "${ROOT_DIR}"/${RESOURCE_DIR_SUFFIX} "${TEMP_DIR}"

sed -i.bak "s/fake-department/${BLUEPRINT_DEPARTMENT}/g" "${TEMP_DIR}"/resources/blueprints.json
sed -i.bak "s/fake-person/${BLUEPRINT_PERSON}/g" "${TEMP_DIR}"/resources/blueprints.json
sed -i.bak "s/\"fake-department\"/\"${BLUEPRINT_DEPARTMENT}\"/g" "${TEMP_DIR}"/resources/port-app-config.yml
sed -i.bak "s/\"fake-person\"/\"${BLUEPRINT_PERSON}\"/g" "${TEMP_DIR}"/resources/port-app-config.yml


export TEMP_RESOURCES_DIR="${TEMP_DIR}/resources"
export INTEGRATION_IDENTIFIER=${INTEGRATION_IDENTIFIER}

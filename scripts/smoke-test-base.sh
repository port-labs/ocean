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

# Smoke tests validate dept/person only; trim 5-kind E2E resources from the copy.
PYTHON="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
    PYTHON=python3
fi
"${PYTHON}" - "${TEMP_DIR}/resources" <<'PY'
import json
import sys
from pathlib import Path

import yaml

resources_dir = Path(sys.argv[1])
smoke_kinds = {"fake-department", "fake-person"}

blueprints_path = resources_dir / "blueprints.json"
blueprints = json.loads(blueprints_path.read_text())
blueprints_path.write_text(
    json.dumps(
        [bp for bp in blueprints if bp.get("identifier") in smoke_kinds],
        indent=4,
    )
    + "\n"
)

config_path = resources_dir / "port-app-config.yml"
config = yaml.safe_load(config_path.read_text())
config["resources"] = [
    resource
    for resource in config.get("resources", [])
    if resource.get("kind") in smoke_kinds
]
config_path.write_text(yaml.safe_dump(config, sort_keys=False))
PY

sed -i.bak "s/fake-department/${BLUEPRINT_DEPARTMENT}/g" "${TEMP_DIR}"/resources/blueprints.json
sed -i.bak "s/fake-person/${BLUEPRINT_PERSON}/g" "${TEMP_DIR}"/resources/blueprints.json
sed -i.bak "s/\"fake-department\"/\"${BLUEPRINT_DEPARTMENT}\"/g" "${TEMP_DIR}"/resources/port-app-config.yml
sed -i.bak "s/\"fake-person\"/\"${BLUEPRINT_PERSON}\"/g" "${TEMP_DIR}"/resources/port-app-config.yml


export TEMP_RESOURCES_DIR="${TEMP_DIR}/resources"
export INTEGRATION_IDENTIFIER=${INTEGRATION_IDENTIFIER}

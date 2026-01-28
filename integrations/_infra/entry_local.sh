#!/bin/bash
if [ -z "$BUILD_CONTEXT" ]; then
    echo "BUILD_CONTEXT is not set"
    exit 1
fi

# Sync CA certificates to unprivileged user directory
source /app/integrations/_infra/sync_ca_certs.sh

if [ ! -d ".venv-docker" ]; then
    /usr/bin/python3 -m venv .venv-docker
    source .venv-docker/bin/activate
    python -m pip install poetry
    python -m poetry install
fi

cd integrations/$BUILD_CONTEXT

if [ ! -d ".venv-docker" ]; then
    /usr/bin/python3 -m venv .venv-docker
    source .venv-docker/bin/activate
    python -m pip install poetry
    python -m poetry install
fi
source .venv-docker/bin/activate
python -m pip install -e ../../
python -m pip install -e .

python -m pip install debugpy

if [ "$OCEAN__PROCESS_EXECUTION_MODE" == "single_process" ]; then
  unset PROMETHEUS_MULTIPROC_DIR;
fi
# python -m debugpy --listen 0.0.0.0:5678 --wait-for-client debug.py
make run

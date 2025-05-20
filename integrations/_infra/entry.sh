#!/bin/bash
if [ -z "$DOCKER_INTEGRATION_DIR_TARGET" ]; then
    echo "DOCKER_INTEGRATION_DIR_TARGET is not set"
    exit 1
fi

if [ ! -d ".venv-docker" ]; then
    /usr/bin/python3 -m venv .venv-docker
    source .venv-docker/bin/activate
    make install
fi
cd $DOCKER_INTEGRATION_DIR_TARGET
if [ ! -d ".venv-docker" ]; then
    /usr/bin/python3 -m venv .venv-docker
    source .venv-docker/bin/activate
    make install
fi
source .venv-docker/bin/activate
make install/local-core

make run

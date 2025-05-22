#!/bin/bash
if [ -z "$BUILD_CONTEXT" ]; then
    echo "BUILD_CONTEXT is not set"
    exit 1
fi

if [ ! -d ".venv-docker" ]; then
    /usr/bin/python3 -m venv .venv-docker
    source .venv-docker/bin/activate
    make install
fi
cd $BUILD_CONTEXT
if [ ! -d ".venv-docker" ]; then
    /usr/bin/python3 -m venv .venv-docker
    source .venv-docker/bin/activate
    make install
fi
source .venv-docker/bin/activate
make install/local-core

make run

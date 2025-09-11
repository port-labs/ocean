#!/bin/bash
if [ -z "$BUILD_CONTEXT" ]; then
    echo "BUILD_CONTEXT is not set"
    exit 1
fi

if [ ! -d ".venv-docker" ]; then
    /usr/bin/python3 -m venv .venv-docker
    source .venv-docker/bin/activate
    python -m pip install poetry
    python -m poetry install
fi

cd $BUILD_CONTEXT

if [ ! -d ".venv-docker" ]; then
    /usr/bin/python3 -m venv .venv-docker
    source .venv-docker/bin/activate
    python -m pip install poetry
    python -m poetry install
fi
source .venv-docker/bin/activate
python -m pip install -e ../../

python -m pip install debugpy
python -m debugpy --listen 0.0.0.0:5678 --wait-for-client debug.py

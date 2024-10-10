#!/usr/bin/env bash
PLATFORM=${1}

if [[ ! $(grep -q 'grpcio' ./poetry.lock) ]]; then
    echo 'grpcio not present, skipping explicit build'
else
    echo 'found grpcio, checking platform'
fi

if [[ "${PLATFORM}" == "linux/arm64" ]]; then
    echo "On arm, need to explicitly install grpcio"
    poetry env use "$(which python)"
    echo "${VIRTUAL_ENV}"
    poetry run pip install --upgrade pip
    GRPC_PYTHON_BUILD_SYSTEM_OPENSSL=1 GRPC_PYTHON_BUILD_SYSTEM_ZLIB=1 GRPC_PYTHON_DISABLE_LIBC_COMPATIBILITY=1 poetry run pip install 'grpcio==1.66.2'
else
    echo "Not on arm, no need to explicitly install grpcio"
fi

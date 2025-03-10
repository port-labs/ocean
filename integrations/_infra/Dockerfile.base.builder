ARG BASE_PYTHON_IMAGE=debian:trixie-slim
# debian:trixie-slim - Python 3.12
FROM ${BASE_PYTHON_IMAGE}

LABEL org.opencontainers.image.source=https://github.com/port-labs/ocean

ENV LIBRDKAFKA_VERSION=2.8.2 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    PIP_ROOT_USER_ACTION=ignore

RUN apt-get update \
    && apt-get install -y \
        --no-install-recommends \
        wget \
        g++ \
        libssl-dev \
        autoconf \
        automake \
        libtool \
        curl \
        librdkafka-dev \
        python3 \
        python3-pip \
        python3-poetry \
    && apt-get clean

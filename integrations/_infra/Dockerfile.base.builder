ARG ACCOUNT_ID=1
ARG BASE_PYTHON_IMAGE=${ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com/echo/python:3.13

FROM ${BASE_PYTHON_IMAGE}

LABEL org.opencontainers.image.source=https://github.com/port-labs/ocean

ENV LIBRDKAFKA_VERSION=2.8.2 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    PIP_ROOT_USER_ACTION=ignore \
    POETRY_VIRTUALENVS_PREFER_ACTIVE_PYTHON=true \
    POETRY_PYTHON=/usr/local/bin/python3.13

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

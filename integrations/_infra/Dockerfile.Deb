ARG BASE_BUILDER_PYTHON_IMAGE=ghcr.io/port-labs/port-ocean-base-builder:latest
ARG BASE_RUNNER_PYTHON_IMAGE=ghcr.io/port-labs/port-ocean-base-runner:latest

FROM ${BASE_BUILDER_PYTHON_IMAGE} AS base

ARG BUILD_CONTEXT
ARG BUILDPLATFORM

ENV LIBRDKAFKA_VERSION=2.8.2 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

COPY ./${BUILD_CONTEXT}/pyproject.toml ./${BUILD_CONTEXT}/poetry.lock /app/

RUN poetry install --without dev --no-root --no-interaction --no-ansi --no-cache

FROM ${BASE_RUNNER_PYTHON_IMAGE} AS prod

RUN groupadd -r appgroup && useradd -r -g appgroup -m ocean

RUN mkdir -p /tmp/ocean

ARG INTEGRATION_VERSION
ARG BUILD_CONTEXT
ARG PROMETHEUS_MULTIPROC_DIR=/tmp/ocean/prometheus/metrics

ENV LIBRDKAFKA_VERSION=2.8.2 \
    PROMETHEUS_MULTIPROC_DIR=${PROMETHEUS_MULTIPROC_DIR}

RUN mkdir -p ${PROMETHEUS_MULTIPROC_DIR}
RUN chown -R ocean:appgroup /tmp/ocean && chmod -R 755 /tmp/ocean

RUN apt-get update \
    && apt-get install -y \
        ca-certificates \
        openssl \
        curl \
    && apt-get clean

LABEL INTEGRATION_VERSION=${INTEGRATION_VERSION}
# Used to ensure that new integrations will be public, see https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility
LABEL org.opencontainers.image.source=https://github.com/port-labs/ocean

ENV PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

USER ocean

# Copy the application code
COPY ./${BUILD_CONTEXT} /app

# Copy dependencies from the build stage
COPY --from=base /app/.venv /app/.venv

COPY ./integrations/_infra/init.sh /app/init.sh

USER root
# Ensure that ocean is available for all in path
RUN chmod a+x /app/.venv/bin/ocean

RUN chmod a+x /app/init.sh
RUN ln -s /app/.venv/bin/ocean /usr/bin/ocean

USER ocean
# Run the application
CMD ["bash", "/app/init.sh"]

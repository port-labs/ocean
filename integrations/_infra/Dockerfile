FROM python:3.11-alpine AS base

ARG BUILD_CONTEXT

ENV LIBRDKAFKA_VERSION=1.9.2

# Install system dependencies and libraries
RUN apk add --no-cache \
    gcc \
    musl-dev \
    build-base \
    bash \
    oniguruma-dev \
    make \
    autoconf \
    automake \
    libtool \
    curl \
    # librdkafka-dev \
    libffi-dev \
        # Install community librdkafka-dev since the default in alpine is older
        && echo "@edge http://dl-cdn.alpinelinux.org/alpine/edge/main" >> /etc/apk/repositories \
        && echo "@edgecommunity http://dl-cdn.alpinelinux.org/alpine/edge/community" >> /etc/apk/repositories \
        && apk add --no-cache alpine-sdk "librdkafka@edgecommunity>=${LIBRDKAFKA_VERSION}" "librdkafka-dev@edgecommunity>=${LIBRDKAFKA_VERSION}" \
        && curl -sSL https://install.python-poetry.org | python3 - \
        && /root/.local/bin/poetry config virtualenvs.in-project true


WORKDIR /app

COPY ./${BUILD_CONTEXT}/pyproject.toml ./${BUILD_CONTEXT}/poetry.lock /app/

RUN /root/.local/bin/poetry install --without dev --no-root --no-interaction --no-ansi --no-cache && pip cache purge

FROM python:3.11-alpine AS prod

ARG INTEGRATION_VERSION
ARG BUILD_CONTEXT

LABEL INTEGRATION_VERSION=${INTEGRATION_VERSION}
# Used to ensure that new integrations will be public, see https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility
LABEL org.opencontainers.image.source=https://github.com/port-labs/ocean

# Install only runtime dependencies
RUN apk add --no-cache \
        librdkafka-dev \
        bash \
        oniguruma-dev \
    # Install community librdkafka-dev since the default in alpine is older
    && echo "@edge http://dl-cdn.alpinelinux.org/alpine/edge/main" >> /etc/apk/repositories \
    && echo "@edgecommunity http://dl-cdn.alpinelinux.org/alpine/edge/community" >> /etc/apk/repositories \
    && apk add --no-cache alpine-sdk "librdkafka@edgecommunity>=${LIBRDKAFKA_VERSION}" "librdkafka-dev@edgecommunity>=${LIBRDKAFKA_VERSION}" \
    && test -e /usr/local/share/ca-certificates/cert.crt && update-ca-certificates || true

WORKDIR /app

# Copy dependencies from the build stage
COPY --from=base /app /app

# Copy the application code
COPY ./${BUILD_CONTEXT} /app

# Ensure that ocean is available for all in path
RUN chmod a+x /app/.venv/bin/ocean \
    && ln -s /app/.venv/bin/ocean /usr/bin/ocean \
    #    # Fix security issues
    && apk upgrade busybox --repository=http://dl-cdn.alpinelinux.org/alpine/edge/main \
    # Clean up old setuptools
    && pip uninstall -y setuptools py3-setuptools

# Run the application
CMD ["ocean", "sail"]

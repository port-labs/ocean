FROM python:3.11-slim-bookworm

ARG BUILD_CONTEXT
ARG INTEGRATION_VERSION

LABEL INTEGRATION_VERSION=${INTEGRATION_VERSION}

ENV LIBRDKAFKA_VERSION 1.9.2

WORKDIR /app

RUN apt update && \
    apt install -y wget make g++ libssl-dev autoconf automake libtool curl librdkafka-dev && \
    apt-get clean

COPY ./integrations/_infra/init.sh /app/init.sh
RUN chmod +x /app/init.sh

COPY ./${BUILD_CONTEXT} /app

RUN export POETRY_VIRTUALENVS_CREATE=false && make install/prod && pip cache purge

ENTRYPOINT ./init.sh
FROM python:3.11-slim-buster

ENV LIBRDKAFKA_VERSION 1.9.2

WORKDIR /app

RUN apt update && \
    apt install -y wget make g++ libssl-dev autoconf automake libtool curl librdkafka-dev && \
    apt-get clean

COPY . /app

RUN export POETRY_VIRTUALENVS_CREATE=false && make install/prod && pip cache purge

ENTRYPOINT ocean sail
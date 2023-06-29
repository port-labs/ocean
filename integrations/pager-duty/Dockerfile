FROM python:3.11-slim-buster

ENV LIBRDKAFKA_VERSION 1.9.2

WORKDIR /app

RUN apt update && apt install -y wget make g++ libssl-dev autoconf automake libtool curl
RUN wget https://github.com/edenhill/librdkafka/archive/v${LIBRDKAFKA_VERSION}.tar.gz &&  \
    tar xvzf v${LIBRDKAFKA_VERSION}.tar.gz &&  \
    (cd librdkafka-${LIBRDKAFKA_VERSION}/ && ./configure && make && make install && ldconfig)

COPY . /app

RUN make install

ENTRYPOINT make run
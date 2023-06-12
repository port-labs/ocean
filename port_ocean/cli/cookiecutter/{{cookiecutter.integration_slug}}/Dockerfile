FROM python:3.10-slim-buster

ENV LIBRDKAFKA_VERSION 1.9.2

WORKDIR /app

RUN apt update && apt install -y wget make g++ libssl-dev
RUN wget https://github.com/edenhill/librdkafka/archive/v${LIBRDKAFKA_VERSION}.tar.gz &&  \
    tar xvzf v${LIBRDKAFKA_VERSION}.tar.gz &&  \
    (cd librdkafka-${LIBRDKAFKA_VERSION}/ && ./configure && make && make install && ldconfig)

COPY . /app

ENV CONFIG_PATH /app/config.yaml


RUN chmod +x ./deployment/docker/install_req.sh
RUN ./deployment/docker/install_req.sh
RUN pip3 install confluent-kafka

ENTRYPOINT python3 main.py --integrations-config=$CONFIG_PATH
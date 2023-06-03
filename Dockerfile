FROM python:3.10-slim-buster

ENV LIBRDKAFKA_VERSION 1.9.2

WORKDIR /app

RUN apt update && apt install -y wget make g++ libssl-dev
RUN wget https://github.com/edenhill/librdkafka/archive/v${LIBRDKAFKA_VERSION}.tar.gz &&  \
    tar xvzf v${LIBRDKAFKA_VERSION}.tar.gz &&  \
    (cd librdkafka-${LIBRDKAFKA_VERSION}/ && ./configure && make && make install && ldconfig)

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

CMD [ "python3", "main.py"]
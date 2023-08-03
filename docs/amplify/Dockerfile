FROM amazonlinux

RUN yum group install "Development Tools" -y && yum install wget -y

RUN wget https://www.python.org/ftp/python/3.11.4/Python-3.11.4.tgz &&\
    tar xzf ./Python-3.11.4.tgz &&\
    cd Python-3.11.4 &&\
    ./configure --enable-optimizations &&\
    make altinstall \
    && cd .. && rm -rf Python-3.11.4*
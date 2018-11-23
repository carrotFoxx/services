FROM python:3.7

ENV CPILOT_VERSION 3.8.0
ENV CPILOT_CHECKSUM 84642c13683ddae6ccb63386e6160e8cb2439c26
RUN curl -Lso /tmp/containerpilot.tar.gz \
    "https://github.com/joyent/containerpilot/releases/download/${CPILOT_VERSION}/containerpilot-${CPILOT_VERSION}.tar.gz" \
    && echo "${CPILOT_CHECKSUM}  /tmp/containerpilot.tar.gz" | sha1sum -c \
    && tar zxf /tmp/containerpilot.tar.gz -C /usr/local/bin \
    && rm /tmp/containerpilot.tar.gz
# py env setup
ENV PYTHONPATH "/opt/app:${PYTHONPATH}"
EXPOSE 8080

CMD ["/usr/local/bin/containerpilot", "-config", "/etc/containerpilot.json5"]
# dependencies
COPY requirements /opt/app/
RUN pip install --no-cache-dir -r /opt/app/requirements
# containerpilot config file
COPY docker/containerpilot.json5 /etc/containerpilot.json5
# version info
ARG PLATFORM_VERSION=unknown
ENV PLATFORM_VERSION $PLATFORM_VERSION
# sources
COPY src /opt/app

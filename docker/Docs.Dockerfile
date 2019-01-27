FROM python:3.7 as builder

ENV PYTHONPATH "/opt/src:${PYTHONPATH}"

COPY requirements.dev version.py /opt/src/
RUN pip install --no-cache-dir -r /opt/src/requirements.dev
# version info
ARG PLATFORM_VERSION=unknown
ENV PLATFORM_VERSION $PLATFORM_VERSION

COPY ./docs /opt/src/

RUN cd /opt/src && make html

FROM nginx:alpine

COPY --from=builder /opt/src/_build/html /usr/share/nginx/html

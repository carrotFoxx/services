FROM python:3.7

# py env setup
ENV PYTHONPATH "/opt/app:${PYTHONPATH}"
EXPOSE 8080

WORKDIR /opt/app
# add entrypoint
ADD docker/entrypoint.sh .
ENTRYPOINT ["/opt/app/entrypoint.sh"]
# dependencies
COPY requirements /opt/app/
RUN pip install --no-cache-dir -r /opt/app/requirements
# version info
ARG PLATFORM_VERSION=unknown
ENV PLATFORM_VERSION $PLATFORM_VERSION
# sources
COPY src /opt/app

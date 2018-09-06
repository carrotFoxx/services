FROM python:3.6

# py env setup
ENV PYTHONPATH "/opt/app:${PYTHONPATH}"
EXPOSE 8080

COPY docker/entrypoint.sh /
ENTRYPOINT ["/entrypoint.sh"]
# dependencies
COPY requirements /opt/app/
RUN pip install --no-cache-dir -r /opt/app/requirements
# sources
COPY src /opt/app
ENV SERVICE_NAME "../supervisor/__init__"
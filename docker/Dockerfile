FROM python:3.7

ENV PYTHONPATH "/opt/app:${PYTHONPATH}"

COPY docker/entrypoint.sh /
ENTRYPOINT ["/entrypoint.sh"]
CMD ["--help"]
EXPOSE 8080

COPY requirements constraints /opt/app/
RUN pip install --no-cache-dir -r /opt/app/requirements -c /opt/app/constraints

# a temp fix for motor on Py3.7
RUN cd $(pip show motor | grep -wo -E '/usr/(.*)') && \
    sed -E -i '32s/(\s+).+/\1raise RuntimeError("incompatible with Python 3.4")/' motor/frameworks/asyncio/__init__.py

COPY src /opt/app


FROM python:3.7

ENV PYTHONPATH "/opt/app:${PYTHONPATH}"

COPY docker/entrypoint.sh /
ENTRYPOINT ["/entrypoint.sh"]
CMD ["--help"]
EXPOSE 8080

COPY requirements constraints /opt/app/
RUN pip install --no-cache-dir -r /opt/app/requirements -c /opt/app/constraints

COPY src /opt/app


FROM python:3.7

ENV PYTHONPATH "/opt/app:${PYTHONPATH}"

COPY docker/entrypoint.sh /
ENTRYPOINT ["/entrypoint.sh"]
CMD ["--help"]
EXPOSE 8080

COPY requirements /opt/app/
RUN pip install --no-cache-dir -r /opt/app/requirements

COPY src /opt/app


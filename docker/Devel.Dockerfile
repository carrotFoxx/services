FROM python:3.7
# py env setup
ENV PYTHONPATH "/opt/app:${PYTHONPATH}"
EXPOSE 8080

COPY requirements.dev /opt/app/
RUN pip install --no-cache-dir -r /opt/app/requirements.dev

FROM python:3.6

# py env setup
ENV PYTHONPATH "/opt/app:${PYTHONPATH}"
EXPOSE 8080

# dependencies
COPY requirements /opt/app/
RUN pip install --no-cache-dir -r /opt/app/requirements
# sources
COPY src /opt/app
CMD ["python3", "/opt/app/supervisor/__init__.py"]

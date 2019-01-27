*****************
Supervisor Manual
*****************

Vocabulary
==========

Calculator:
  a payload application managed by Supervisor

Model:
  a data/configuration file passed to Calculator during initialization.
  Could be ML model, configuration file, or any other file dedicated for
  a particular Calculator (i.e. its contents are no concern of Supervisor)

Purpose
=======

Supervisor - an application which sits in front of all payloads
which buldozer can operate. It performs all integration operations
between payload application and Buldozer platform.

Supervisor is a high-performed proxy and application supervisor
which take care of the following:

- Register itself in Buldozer platform mesh once it is broad up by
  kubernetes or cloud platform

- Read and adjust run configuration for Calculator

- Attach to data streams selected by the user/platform to read/write
  data from/to.

- Proxy data from incoming stream to Calculator

- Proxy data from Calculator to outgoing stream

- Maintain Calculator state (ensure it is running and restart it if
  it crashes)

- Announce own and Calculator health to the Buldozer platform

Supervisor is written in Golang so it is compiled as single binary
with no dependencies, making it easy to install and run it on any
platform.

Integration
===========

Supervisor acts like a `PID1` agent for Calculator, so you dont need to
launch Calculator itself alongside the Supervisor.

Supervisor integrates with the Calculator in fastest and easiest
cross-platform way possible: pipes.

In fact all you need to do to make your application (Calculator) work
under the Supervisor and process data is to read data from `STDIN` and
write resulting data to `STDOUT`.

Logs, if any, should be written to `STDERR` where Supervisor could collect
them and display as part of its own log stream. Thru it is not necessary.

.. note::

    Make sure to either use `UNBUFFERED` mode for `STDIO` in Calculator or
    flush often, to achieve faster processing and prevent data-loss.

Supervisor reads and writes data to PIPEs using a `\\n` delimiter, so
every new line considered as new record in stream. Dont forget to
split records by `\\n` then posting them to `STDOUT`, and treat every line
of data sent to `STDIN` as separate chunk of data to process.

Supervisor Configuration
------------------------

Most of the options are passed via ENV variables.

.. list-table::

  - - Variable
    - Example
    - Description

  - - NODE_ID
    - 4f1dfd7a-7a3e-4b1a-88b9-d74fe7a5ad56
    - Workspace ID given by Buldozer Platform

  - - KAFKA_DSN
    - localhost:9092
    - Address of Kafka broker to connect to

  - - KAFKA_CONSUMER_GROUP
    - bdz_default_sg
    - Kafka consumer group name
      (Optional, has default)

  - - CONSUL_DSN
    - localhost:8500
    - Address of Consul agent to connect to

  - - CONSUL_ADVERTISE
    - 192.168.10.1
    - node IP to advertise to Consul
      (Optional, auto-detects IP on start)

  - - CONSUL_NAME_TPL
    - bdz-wsp-%s
    - Service name template to use then generating consul service
      advertisement
      (Optional, has default)

  - - CONSUL_RESYNC_INTERVAL
    - 30s
    - How often should Supervisor consult with consul for config changes
      (Optional, has default)

  - - CONSUL_DIR
    - buldozer/subordinate
    - where should Supervisor look for configuration in Consul KV
      (Optional, has default)

  - - PROGRAM
    - /some/path/to/executable
    - Absolute path to Calculator executable
      (Optional if given as CLI argument)

  - - OUTPUT_JSON
    - false
    - Whatever output should be considered JSON and embedded as
      part of dataframe sent over kafka, rather then be sent as
      a string value
      (Optional, defaults to `false`)

  - - ADOPTION_GRACEPERIOD
    - 3s
    - A time Supervisor will wait during readjustments of config
      like, recreating a stream with Kafka or changing run configuration
      for Calculator
      (Optional, has default)

  - - SHUTDOWN_GRACEPERIOD
    - 3s
    - A time Supervisor will wait then shutting down Calculator to
      let it finish gracefully, before killing it.
      (Optional, has default)

  - - LOG_LEVEL
    - debug
    - Supervisor log level
      (Optional, has default)

  - - LOG_COLORS
    - false
    - Supervisor log color support (auto-enables on interactive CLI)

Also there are options to control how Calculator is started passed via
CLI arguments.

.. list-table::

  - - Option
    - Example
    - Description

  - - --bin
    - /some/path/to/executable
    - Absolute path to Calculator executable
      (alternative to PROGRAM env variable)

  - - --args
    - /var/model,--logs=stderr
    - Arguments to pass to Calculator


Dockerfile example
------------------

Below is an example how image for Kubernetes/Docker provider should be
created with supervisor packed inside to run your own Calculator.

.. code-block:: Dockerfile

    FROM python:3.7 AS downloader
    # configure download
    ARG SPV_VERSION=0.1.4
    ARG ART_USER
    ARG ART_PASS
    ENV ART_REPO=https://services.crplab.ru/artifactory/buldozer/${SPV_VERSION}/supervisor-linux-amd64
    # download supervisor binary
    RUN wget --http-user ${ART_USER} --http-password ${ART_PASS} -O /opt/supervisor "${ART_REPO}"
    RUN chmod +x /opt/supervisor

    # final image
    FROM python:3.7
    COPY --from=downloader /opt/supervisor /opt/supervisor
    # setup supervisor as entrypoint
    ENTRYPOINT ["/opt/supervisor"]
    # (call python with main script and provide it ref to model file which is expected to be mounted at /var/model)
    CMD ["--bin", "python3", "--args", "/opt/app/io_main.py,/var/model"]
    # py env setup
    ENV PYTHONPATH "/opt/app:${PYTHONPATH}"
    EXPOSE 8080
    # dependencies
    COPY requirements constraints /opt/app/
    RUN pip install --no-cache-dir -r /opt/app/requirements -c /opt/app/constraints
    # version info
    ARG PLATFORM_VERSION=unknown
    ENV PLATFORM_VERSION $PLATFORM_VERSION
    # sources
    COPY src /opt/app



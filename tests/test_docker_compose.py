import io
import os

import docker
import pytest
import yaml
from compose.config.config import ConfigDetails, ConfigFile, load as load_config
from compose.config.environment import Environment
from compose.project import Project


@pytest.fixture(scope='module')
def docker_client():
    client = docker.DockerClient.from_env()
    yield client
    client.close()


_compose_def = '''---
version: '2'
services:
  bus:
    image: busybox:latest
    labels:
      - inline-defined
    command: echo 'Hello world!!!'
'''


@pytest.fixture
def compose_definition():
    stream = io.StringIO(_compose_def)
    data = yaml.safe_load(stream)
    stream.close()
    return data


def test_create_config(compose_definition: dict, docker_client: docker.DockerClient):
    environment = Environment()
    file = ConfigFile(None, config=compose_definition)
    config_details = ConfigDetails(working_dir=os.getcwd(),
                                   config_files=[file],
                                   environment=environment)

    config = load_config(config_details)

    print('\n')

    print(config)

    prj = Project.from_config(name='inline-defined',
                              config_data=config,
                              client=docker_client.api)

    print(prj)

    print(prj.up(
        detached=True
    ))

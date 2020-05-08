import asyncio
import logging
from typing import Awaitable

from keystoneauth1 import loading
from keystoneauth1 import session
from novaclient import client
from novaclient.exceptions import NotFound, ClientException
from novaclient.v2 import Client
from novaclient.v2 import images
from novaclient.v2.flavors import Flavor
from novaclient.v2.images import Image
from novaclient.v2.servers import Server

from container_manager import ProviderError, InstanceNotFound
from container_manager.definitions import Instance, InstanceDefinition
from container_manager.provider import Provider
from mco.utils import convert_exceptions
from microcore.base.sync import run_in_executor

log = logging.getLogger(__name__)

raise_provider_exception = convert_exceptions(exc=ClientException, to=ProviderError)


class NoVirtualMachineProviderFound(Exception):
    pass


class VmProvider(Provider):
    ORCHESTRATOR_ID = 'vm'

    def __init__(self,
                 vm_provider: str,
                 vm_provider_cred: {},
                 vm_instance_definitions: {},
                 *, loop: asyncio.AbstractEventLoop = None) -> None:
        super().__init__()
        self._vm_provider = vm_provider
        self._vm_instance_definitions = vm_instance_definitions
        self._client = self._get_client(vm_provider_cred)
        self._loop = loop or asyncio.get_event_loop()

    @staticmethod
    def _get_client(vm_provider_cred) -> Client:
        loader = loading.get_plugin_loader("password")
        auth = loader.load_from_options(auth_url=vm_provider_cred['auth_url'],
                                        username=vm_provider_cred['username'],
                                        password=vm_provider_cred['password'],
                                        project_name=vm_provider_cred['project_name'],
                                        user_domain_id=vm_provider_cred['user_domain_id'],
                                        project_domain_id=vm_provider_cred['project_domain_id'])
        sess = session.Session(auth=auth)
        return client.Client("2", session=sess)

    @staticmethod
    def _s2i(server: Server) -> Instance:
        """
        converts nova.Server object to Instance object
        :param server:
        :return:
        """
        meta = server.to_dict()
        return Instance(
            uid=meta.get("id"),
            name=meta.get("name"),
            state=meta.get("status")
        )

    @raise_provider_exception
    def _get_image(self, definition) -> Image:
        return images.GlanceManager.find_image(self._client.servers, self._extract_image(definition.image))

    @raise_provider_exception
    def _get_flavour(self, definition) -> Flavor:
        return self._client.flavors.find(name=definition.environment.get('FLAVOR'))

    @raise_provider_exception
    def _get_security_groups(self, definition):
        security_groups = self._vm_instance_definitions['security_groups']
        if definition.environment.get('SECURITY_GROUPS'):
            security_groups = definition.environment.get('SECURITY_GROUPS')
        return (str(s).strip() for s in str(security_groups).split(','))

    @raise_provider_exception
    def _get_nics(self, nics):
        networks = []
        for network in str(nics).split(','):
            networks.append({'net-id': network.strip()})
        return networks

    @raise_provider_exception
    def _create_server(self, definition: InstanceDefinition) -> Server:
        log.info('definition [%s]', definition)
        image = self._get_image(definition)
        flavor = self._get_flavour(definition)
        security_groups = self._get_security_groups(definition)

        networks = self._get_nics(self._vm_instance_definitions['networks'])
        availability_zone = self._vm_instance_definitions['availability_zone']
        key_name = self._vm_instance_definitions['key_name']
        userdata = "#!/bin/bash \n" \
                    " echo 'BDZ_KAFKA_DSN=%s' > /opt/supervisor.env \n" \
                    " echo 'BDZ_NODE_ID=%s' >> /opt/supervisor.env \n" \
                    " echo 'BDZ_CONSUL_DSN=%s' >> /opt/supervisor.env" % \
                    (self._vm_instance_definitions['bdz_kafka_dsn'],
                     definition.environment['BDZ_NODE_ID'],
                     self._vm_instance_definitions['bdz_consul_dsn'])

        log.info('user_data [%s]', userdata)

        return self._client.servers.create(definition.uid,
                                           flavor=flavor,
                                           image=image,
                                           nics=networks,
                                           security_groups=security_groups,
                                           availability_zone=availability_zone,
                                           key_name=key_name,
                                           meta=definition.environment,
                                           userdata=userdata
                                           )

    @raise_provider_exception
    def _find_instance_server(self, definition) -> Server:
        try:
            server = self._client.servers.find(name=definition.uid)
            if server:
                log.info('found instance for [%s] (cid:%s)', definition.uid, server.id)
                return server
        except NotFound:
            raise InstanceNotFound

    @raise_provider_exception
    def _launch_instance(self, definition: InstanceDefinition) -> Server:
        try:
            server = self._find_instance_server(definition)
            log.info('found existing instance [%s] for [%s]', server.id, definition.uid)

            # if server.status.lower() != 'active':
            #     log.info('instance [%s] is not running - starting...', server.id)
            #     server.start()
            #     log.info('instance [%s] started', server.id)
        except InstanceNotFound:
            log.debug('no existing instance found for [%s]', definition.uid)
            server = self._create_server(definition)
        return server

    @raise_provider_exception
    def _stop_instance(self, definition: InstanceDefinition):
        try:
            server = self._find_instance_server(definition)
            server.stop()
            log.info('removed instance [%s] (cid:%s)', definition.uid, server.id)
            return True
        except NotFound:
            log.info('instance [%s] not found, assume it is already have been removed', definition.uid)
        return True

    @raise_provider_exception
    def _remove_instance(self, definition: InstanceDefinition):
        try:
            server = self._find_instance_server(definition)
            if server.status == 'active':
                server.stop()
            server.force_delete()
        except NotFound:
            log.info('instance [%s] not found')
        return True

    @run_in_executor
    def create_instance(self, definition: InstanceDefinition) -> Awaitable[Instance]:
        # noinspection PyTypeChecker
        return self._s2i(self._create_server(definition))

    @run_in_executor
    def launch_instance(self, definition: InstanceDefinition) -> Awaitable[Instance]:
        # noinspection PyTypeChecker
        return self._s2i(self._launch_instance(definition))

    @run_in_executor
    def stop_instance(self, definition: InstanceDefinition) -> Awaitable[bool]:
        return self._stop_instance(definition)

    @run_in_executor
    def remove_instance(self, definition: InstanceDefinition) -> Awaitable[bool]:
        return self._remove_instance(definition)

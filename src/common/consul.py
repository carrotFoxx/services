import asyncio
import json
from typing import Any, List, Union

import attr
import marshmallow as ma
from aiohttp import ClientResponse
from more_itertools import flatten

from mco.client import HTTPClient, error_handler


@attr.s(auto_attribs=True)
class KVData:
    key: str
    value: str

    create_index: int = 0
    modify_index: int = 0
    lock_index: int = 0

    flags: int = 0
    session: str = None

    class Schema(ma.Schema):
        key = ma.fields.String(data_key='Key', required=True)
        value = ma.fields.String(data_key='Value', required=True)

        create_index = ma.fields.Integer(data_key='CreateIndex')
        modify_index = ma.fields.Integer(data_key='ModifyIndex')
        lock_index = ma.fields.Integer(data_key='LockIndex')

        flags = ma.fields.Integer(data_key='Flags')
        session = ma.fields.String(data_key='Session', default=None)

        @ma.post_load
        def make_object(self, dct: dict):
            return KVData(**dct)


class KVStoreClient(HTTPClient):
    _schema = KVData.Schema(many=True)

    @error_handler
    async def put(self, key: str, value: Any, **opts) -> bool:
        async with self._client.put(
                **self._req('/kv/%s' % key, params=opts),
                data=str(value)
        ) as response:  # type: ClientResponse
            return await self._status(response)

    @error_handler
    async def rem(self, key: str, **opts) -> bool:
        async with self._client.delete(
                **self._req('/kv/%s' % key, params=opts)
        ) as response:
            return await self._status(response)

    @error_handler
    async def get(self, key: str, raw: bool = False, _decode=True, **opts) -> Union[KVData, str]:
        async with self._client.get(
                **self._req('/kv/%s' % key, params={'raw': int(raw), **opts})
        ) as response:
            await self._status(response)
            text = await response.text()
        if not raw:
            text = json.loads(text)
        if not raw and _decode:
            return self._schema.loads(text[0], many=False)
        return text

    @error_handler
    async def list(self, prefix: str):
        async with self._client.get(
                **self._req('/kv/%s' % prefix, params={'keys': 1})
        ) as response:
            return await self._data(response)

    @error_handler
    async def get_all(self, prefix: str, raw: bool = False):
        key_list = await self.list(prefix)
        key_list = filter(lambda x: prefix != x, key_list)
        results = await asyncio.gather(
            *[self.get(key, raw=raw, _decode=False) for key in key_list],
            return_exceptions=True
        )
        results = filter(lambda x: not isinstance(x, Exception), results)
        if not raw:
            results = flatten(results)
            return self._schema.load(results, many=True)
        return results


class AgentClient(HTTPClient):
    pass


@attr.s(auto_attribs=True)
class CatalogServiceNode:
    id: str
    node: str
    address: str
    datacenter: str
    tagged_addresses: dict
    node_meta: dict
    service_kind: str
    service_id: str
    service_name: str
    service_tags: list
    service_address: str
    service_meta: dict
    service_port: int
    service_proxy_destination: str
    service_connect: dict
    create_index: int
    modify_index: int

    class Schema(ma.Schema):
        id: str = ma.fields.String(data_key='ID')
        node: str = ma.fields.String(data_key='Node')
        address: str = ma.fields.String(data_key='Address')
        datacenter: str = ma.fields.String(data_key='Datacenter')
        tagged_addresses: dict = ma.fields.Dict(data_key='TaggedAddresses')
        node_meta: dict = ma.fields.Dict(data_key='NodeMeta')
        service_kind: str = ma.fields.String(data_key='ServiceKind')
        service_id: str = ma.fields.String(data_key='ServiceID')
        service_name: str = ma.fields.String(data_key='ServiceName')
        service_tags: list = ma.fields.List(ma.fields.String(), data_key='ServiceTags')
        service_address: str = ma.fields.String(data_key='ServiceAddress')
        service_meta: dict = ma.fields.Dict(data_key='ServiceMeta')
        service_port: int = ma.fields.Integer(data_key='ServicePort')
        service_proxy_destination: str = ma.fields.String(data_key='ServiceProxyDestination')
        service_connect: dict = ma.fields.Dict(data_key='ServiceConnect')
        create_index: int = ma.fields.Integer(data_key='CreateIndex')
        modify_index: int = ma.fields.Integer(data_key='ModifyIndex')

        @ma.post_load
        def make_object(self, dct: dict):
            return CatalogServiceNode(**dct)


class CatalogClient(HTTPClient):
    _schema = ...

    @error_handler
    async def service_nodes(self, service: str) -> List[CatalogServiceNode]:
        async with self._client.get(
                **self._req('/catalog/service/%s' % service)
        ) as response:
            data = await self._data(response)
            return self._schema.load(data, many=True)


class ConsulClient(HTTPClient):
    def kv(self) -> KVStoreClient:
        """

        :return: accessor for KVStore Consul APIs
        """
        return KVStoreClient(
            base=self._base,
            default_headers=self.default_headers,
            default_params=self.default_params,
            client=self._client,
            loop=self._loop
        )

    def agent(self):
        """

        :return: accessor for Agent Consul APIs
        """
        return AgentClient(
            base=self._base,
            default_headers=self.default_headers,
            default_params=self.default_params,
            client=self._client,
            loop=self._loop
        )

    def catalog(self):
        """

        :return: accessor for Agent Consul APIs
        """
        return CatalogClient(
            base=self._base,
            default_headers=self.default_headers,
            default_params=self.default_params,
            client=self._client,
            loop=self._loop
        )

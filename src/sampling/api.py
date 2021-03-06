from typing import Dict, Type

import attr
import marshmallow as ma
from aiohttp import hdrs
from aiohttp.web_exceptions import HTTPBadRequest, HTTPConflict, HTTPNoContent, HTTPNotFound
from aiohttp.web_request import Request
from aiohttp.web_urldispatcher import UrlDispatcher
from motor.core import AgnosticDatabase

from microcore.base.application import Routable
from microcore.entity.encoders import json_response
from microcore.web.owned_api import OwnedReadWriteStorageAPI
from sampling.adapters import Retrospective
from sampling.generator import MongoRecordGenerator, SampleRecordGenerator
from sampling.producer import LoadGeneratorProducerManager


@attr.s(auto_attribs=True)
class SamplerConfig:
    topic: str
    amount: int = 1000
    delay: float = 0.5

    class Schema(ma.Schema):
        topic = ma.fields.String(required=True)
        amount = ma.fields.Integer(default=1000)
        delay = ma.fields.Float(default=0.5)

        @ma.post_load
        def make_object(self, dct: dict):
            return SamplerConfig(**dct)


@attr.s(auto_attribs=True)
class GeneratorState:
    topic: str
    current: int

    class Schema(ma.Schema):
        topic = ma.fields.String()
        current = ma.fields.Integer()


class SamplerAPI(Routable):
    config_schema: ma.Schema = SamplerConfig.Schema(many=False)
    state_schema: ma.Schema = GeneratorState.Schema(many=False)

    def __init__(self,
                 manager: LoadGeneratorProducerManager,
                 generator_class: Type[SampleRecordGenerator] = SampleRecordGenerator) -> None:
        self.generator_class = generator_class
        self.manager = manager
        self._gen_map: Dict[str, SampleRecordGenerator] = {}

    def set_routes(self, router: UrlDispatcher):
        root = router.add_resource('/sampler/test')
        root.add_route(hdrs.METH_POST, self.add)
        root.add_route(hdrs.METH_GET, self.list)

        item = router.add_resource('/sampler/test/{id}')
        item.add_route(hdrs.METH_GET, self.get)
        item.add_route(hdrs.METH_DELETE, self.delete)

    @json_response
    async def add(self, request: Request):
        try:
            config: SamplerConfig = self.config_schema.load(await request.json())
        except (ma.ValidationError, ValueError) as e:
            raise HTTPBadRequest from e
        if self.manager._tm.get(config.topic) is not None:
            raise HTTPConflict(reason='producer is already active')
        self._gen_map[config.topic] = gen = self.generator_class(
            amount=config.amount,
            delay=config.delay
        )
        self.manager.add_producer(
            topic=config.topic,
            sampler_func=gen.generate
        )

        return self.config_schema.dump(config)

    @json_response
    async def list(self, _: Request):
        existing = [
            GeneratorState(topic, gen.current) for topic, gen in self._gen_map.items()
            if self.manager._tm.get(topic) is not None
        ]
        return self.state_schema.dump(existing, many=True)

    @json_response
    async def get(self, request: Request):
        topic = request.match_info['id']
        if topic in self._gen_map and self.manager._tm.get(topic):
            return self.state_schema.dump(
                GeneratorState(
                    topic=topic,
                    current=self._gen_map[topic].current
                )
            )
        raise HTTPNotFound

    async def delete(self, request: Request):
        topic = request.match_info['id']

        gen = self._gen_map.get(topic, default=None)
        if gen:
            gen.kill()
            raise HTTPNoContent
        raise HTTPNotFound


class RetrospectiveGeneratorAPI(OwnedReadWriteStorageAPI, Routable):
    entity_type = Retrospective

    def __init__(self,
                 manager: LoadGeneratorProducerManager,
                 source_db: AgnosticDatabase,
                 **kwargs):
        super().__init__(**kwargs)
        self.source_db = source_db
        self.manager = manager

    def set_routes(self, router: UrlDispatcher):
        root = router.add_resource('/sampler/retrospective')
        root.add_route(hdrs.METH_GET, self.list)
        root.add_route(hdrs.METH_POST, self.post)

        item = router.add_resource('/sampler/retrospective/{id}')
        item.add_route(hdrs.METH_GET, self.get)
        item.add_route(hdrs.METH_DELETE, self.delete)

    async def _post(self, entity: entity_type):
        if self.manager.has_producer(entity.dst_topic):
            raise HTTPConflict(text="generator for selected topic already exists and running")
        # fixme: horrible fix to operate on STRING timestamps (as extensions.rt are string in the data)
        #   should as well be removed as below fix-me states
        start = str(int(entity.start.timestamp() * 1000))
        end = str(int(entity.end.timestamp() * 1000))

        await super()._post(entity)
        self.manager.add_producer(
            topic=entity.dst_topic,
            sampler_func=MongoRecordGenerator(
                collection=self.source_db.get_collection(entity.src_collection),
                query={
                    **entity.query,
                    # fixme: remove this and rely on UI to pass full MQL with range
                    'extensions.rt': {'$gte': start, '$lt': end}
                }).generate
        )

    async def _get(self, request: Request):
        o: Retrospective = await super()._get(request)
        o.running = self.manager.has_producer(o.dst_topic)
        return o

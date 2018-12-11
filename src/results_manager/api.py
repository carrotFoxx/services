import logging

import inject
from aiohttp.web import Request, UrlDispatcher
from aiohttp.web_exceptions import HTTPBadRequest, HTTPForbidden, HTTPInternalServerError
from aiohttp_json_rpc import RpcGenericServerDefinedError
from marshmallow.utils import from_iso_datetime
from motor.core import AgnosticCollection, AgnosticDatabase
from multidict import MultiDictProxy

from common.entities import Workspace
from mco.rpc import RPCClient
from microcore.base.application import Routable
from microcore.base.repository import Repository
from microcore.entity.encoders import json_response
from microcore.web.owned_api import OWNER_ID
from results_manager.adapters import RecordMongoStorageAdapter
from results_manager.plot import Plot

log = logging.getLogger(__name__)


class ResultsManagerAPI(Routable):
    wsp_manager: RPCClient = inject.attr('rpc_wsp_manager')

    def __init__(self, results_db: AgnosticDatabase, events_db: AgnosticDatabase) -> None:
        super().__init__()
        self.events_db = events_db
        self.results_db = results_db

    async def _get_repo(self, request: Request) -> Repository:
        try:
            wsp_uid = request.match_info['id']
            owner = request[OWNER_ID]  # extract owner from request
            workspace: Workspace = await self.wsp_manager.get(wsp_uid)
            if workspace.get_owner() != owner:
                raise HTTPForbidden
        except KeyError:
            raise HTTPBadRequest
        except RpcGenericServerDefinedError as e:
            raise HTTPInternalServerError(text="error retrieving related workspace") from e
        return Repository(
            RecordMongoStorageAdapter(
                collection=self.results_db.get_collection('wsp_out_%s' % wsp_uid.replace('-', ''))
            )
        )

    def set_routes(self, router: UrlDispatcher):
        router.add_get('/results/{id}/data', self.list)
        router.add_get('/results/{id}/plot', self.plot)

    @json_response
    async def list(self, request: Request):
        # todo: add sane paging
        try:
            repository = await self._get_repo(request)
            lst = await repository.find(await self._list_query(request))
        except AttributeError as e:
            raise HTTPBadRequest() from e
        return lst

    async def _list_query(self, request: Request) -> dict:
        properties: MultiDictProxy = request.rel_url.query
        properties: dict = {k: v for k, v in properties.items()}
        return properties

    @json_response
    async def plot(self, request: Request):
        try:
            log.debug('parameters: %s', request.query)
            n_steps = int(request.query['n_step']) if request.query.get('n_step') else 50
            start = from_iso_datetime(request.query['start'])
            end = from_iso_datetime(request.query['end'])
        except (KeyError, ValueError) as e:
            raise HTTPBadRequest(reason='parameters not given or malformed', text=str(e)) from e

        collection: AgnosticCollection = (await self._get_repo(request)).adapter.native_interface
        # create index if it does not exists
        log.info('create index on collection')
        await collection.create_index(
            [('ts', 1), ('_id', 1)],
            name='ts_idx'
        )
        data = await Plot(
            start=start,
            end=end,
            n_steps=n_steps
        ).create(
            cef_source=self.events_db.cef,
            anomaly_source=collection,
            query={}  # need to acquire select condition based on splitter condition in consul for gis-slitter
        )

        return data

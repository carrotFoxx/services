import json
import logging
from asyncio import CancelledError
from typing import Awaitable, Callable, Type, Union

from aiohttp.web import HTTPCreated, HTTPException, HTTPInternalServerError, HTTPNoContent, \
    HTTPNotFound, HTTPOk, json_response as web_json_response
from aiohttp.web_exceptions import HTTPBadRequest
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from multidict import MultiDictProxy

from microcore.base.repository import DoesNotExist, Repository, StorageException
from microcore.base.utils import FQN
from microcore.entity.abstract import Identifiable
from microcore.entity.encoders import json_response, proxy_encoder_instance
from microcore.entity.model import JSON_TYPE_FIELD

logger = logging.getLogger(__name__)


class ReadOnlyStorageAPI:
    def __init__(self, repository: Repository):
        super().__init__()
        self.repository = repository

    def _get(self, request: Request) -> Awaitable:
        return self.repository.load(request.match_info['id'])

    @json_response
    async def get(self, request: Request):
        try:
            entity = await self._get(request)
        except DoesNotExist:
            raise HTTPNotFound()
        return entity

    @json_response
    async def list(self, request: Request):
        try:
            lst = await self._list(await self._list_query(request))
        except AttributeError as e:
            raise HTTPBadRequest() from e
        return lst

    @json_response
    async def head_list(self, request: Request):
        try:
            lst = await self._list(await self._list_query(request))
        except AttributeError:
            raise HTTPBadRequest()
        if len(lst) == 0:
            raise HTTPNoContent()
        raise HTTPOk()

    async def _list_query(self, request: Request) -> dict:
        properties: MultiDictProxy = request.rel_url.query
        properties: dict = {k: v for k, v in properties.items()}
        return properties

    def _list(self, properties: dict) -> Awaitable:
        return self.repository.find(properties)


class ReadWriteStorageAPI(ReadOnlyStorageAPI):
    entity_type: Type[Identifiable] = Identifiable

    def _decode_payload(self, raw: dict) -> entity_type:
        raw.pop(JSON_TYPE_FIELD, None)  # fixes issue if we query our own APIs with __type__'ed objects
        decoded = proxy_encoder_instance.get_encoder_for_type(self.entity_type).unpack(raw, self.entity_type)
        assert isinstance(decoded, self.entity_type)
        return decoded

    async def _put_transformer(self, request: Request):
        entity = self._decode_payload(await request.json())
        if isinstance(entity, Identifiable):
            entity.set_uid(request.match_info['id'])
        return entity

    async def _post_transformer(self, request: Request):
        return self._decode_payload(await request.json())

    @staticmethod
    async def _catch_input(request: Request, transformer: Callable):
        try:
            return await transformer(request)
        except (TypeError, AssertionError) as e:
            raise HTTPBadRequest(reason='entity structure invalid') from e

    def _post(self, entity: Identifiable) -> Awaitable:
        return self.repository.save(entity)

    def _put(self, new: Identifiable, existing: Union[Identifiable, None] = None) -> Awaitable:
        return self.repository.save(new)

    def _delete(self, stored: Identifiable) -> Awaitable:
        return self.repository.delete(stored.get_uid())

    async def post(self, request: Request):
        entity = await self._catch_input(request=request, transformer=self._post_transformer)
        try:
            await self._post(entity)
        except StorageException as e:
            raise HTTPInternalServerError() from e
        return HTTPCreated(text=json.dumps({'uid': entity.uid}))

    async def put(self, request: Request):
        entity = await self._catch_input(request=request, transformer=self._put_transformer)
        try:
            stored = await self._get(request)
        except DoesNotExist:
            stored = None
            pass  # just create with defined id if not exist
        try:
            await self._put(new=entity, existing=stored)
        except DoesNotExist:
            raise HTTPNotFound()
        except StorageException as e:
            raise HTTPInternalServerError() from e
        return HTTPNoContent()

    async def delete(self, request: Request):
        try:
            stored = await self._get(request)
            await self._delete(stored)
        except DoesNotExist:
            raise HTTPNotFound()
        except StorageException as e:
            raise HTTPInternalServerError() from e
        return HTTPNoContent()


class InformativeHTTPException(HTTPException):
    status_code = 400

    def __init__(self, *, headers=None,
                 reason=None, status=status_code,
                 body=None, text=None, content_type=None,
                 data=None):
        super().__init__(headers=headers, reason=reason, body=body, text=text, content_type=content_type)
        self._data = data
        self.set_status(status=status, reason=reason)

    @property
    def data(self):
        return self._data


class JsonMiddlewareSet:
    @classmethod
    async def error(cls, app, handler):
        async def middleware_handler(request):
            try:
                return await handler(request)
            except HTTPException as e:
                if e.empty_body:
                    raise
                if e.status == 500:
                    logger.exception('500 ISE caught')
                return web_json_response(
                    status=e.status,
                    reason=e.reason,
                    data={
                        'error': e.reason,
                        'data': e.data if isinstance(e, InformativeHTTPException) else None,
                        '_trace': cls._format_traceback(e),
                        '_class': FQN.get_fqn(e)
                    }
                )
            except CancelledError:
                raise
            except Exception as e:
                logger.exception('generic exceptions caught')
                reason = e.args[0] if len(e.args) > 0 else None
                return web_json_response(
                    status=500,
                    reason=reason,
                    data={
                        'error': reason,
                        'data': None,
                        '_trace': cls._format_traceback(e),
                        '_class': FQN.get_fqn(e)
                    }
                )

        return middleware_handler

    @staticmethod
    async def content_type(app, handler):
        async def middleware_handler(request: Request):
            response = await handler(request)  # type: Response
            response.headers['Content-Type'] = 'application/json'
            return response

        return middleware_handler

    @classmethod
    def _format_traceback(cls, e) -> list:
        import traceback
        trace = [{'in': t.name,
                  'file': t.filename,
                  'line_no': t.lineno,
                  'line': t.line,
                  'locals': t.locals}
                 for t in traceback.extract_tb(e.__traceback__)]
        if e.__cause__ is not None:
            trace + cls._format_traceback(e.__cause__)
        elif e.__context__ is not None:
            trace + cls._format_traceback(e.__context__)
        return trace

import asyncio
from typing import Awaitable, Dict, List

from aiohttp.web_ws import WebSocketResponse

from microcore.entity.bases import ObjectBase
from microcore.base.log import logger


class Socket(ObjectBase):
    def __init__(self, user_id: str, client_id: str, wsr: WebSocketResponse, **kwargs) -> None:
        super().__init__(uid=client_id, **kwargs)
        self.user_id = user_id
        self.wsr = wsr

    def __repr__(self):
        return '<%s client_id=%s user_id=%s>' % (self.__class__.__name__, self.client_id, self.user_id)

    @property
    def client_id(self):
        return self.uid

    def close(self) -> Awaitable:
        return self.wsr.close()


class SocketManager:
    def __init__(self, idle_ttl: int = 500,
                 reconnect_ttl: int = 1000,
                 loop=None):
        self.idle_ttl = idle_ttl
        self.reconnect_ttl = reconnect_ttl
        self._loop = loop or asyncio.get_event_loop()
        self._map_user_to_client: Dict[str, List[str]] = {}
        self._map_client_to_ws: Dict[str, Socket] = {}

        self._close_handlers = {}
        self._notify_handlers = {}

    def _attach_close_handler(self, client_id: str):
        self._remove_close_handler(client_id)
        handler = self._loop.call_later(self.idle_ttl, self._close_handler, client_id)
        self._close_handlers[client_id] = handler

    def _remove_close_handler(self, client_id: str):
        handler = self._close_handlers.pop(client_id, None)
        if handler:
            handler.cancel()
            return True
        return False

    def _close_handler(self, client_id: str):
        logger.debug('closing socket connection [%s]', client_id)
        self._remove_close_handler(client_id)
        self._loop.create_task(self._async_closer(client_id))
        self._attach_notify_handler(client_id)

    async def _async_closer(self, client_id: str):
        socket = self.get_by_client(client_id)
        if not socket.wsr.closed:
            logger.debug('closing stale connection c[%s]', client_id)
            await socket.wsr.close(message='sys:close:stale')
        self._remove(client_id)

    def _attach_notify_handler(self, client_id: str):
        self._remove_notify_handler(client_id)
        handler = self._loop.call_later(self.reconnect_ttl, self._notify_client_left, client_id)
        self._notify_handlers[client_id] = handler

    def _remove_notify_handler(self, client_id: str):
        handler = self._notify_handlers.pop(client_id, None)
        if handler:
            handler.cancel()
            return True
        return False

    def _notify_client_left(self, client_id):
        logger.debug('client_left event for [%s]', client_id)
        self._remove_notify_handler(client_id)
        pass

    def add(self, socket: Socket):
        if (socket.user_id in self._map_user_to_client and
            socket.client_id in self._map_user_to_client.get(socket.user_id)) or \
                self._map_client_to_ws.get(socket.client_id) is not None:
            raise IndexError('client id conflict')

        logger.debug('add to manager: %s', socket)
        self._map_client_to_ws[socket.client_id] = socket
        if self._remove_notify_handler(socket.client_id):
            logger.debug('reconnect c[%s], cleared notify_left handler', socket.client_id)

        if socket.user_id not in self._map_user_to_client:
            self._map_user_to_client[socket.user_id] = []
        self._map_user_to_client[socket.user_id].append(socket.client_id)

        self._attach_close_handler(socket.client_id)

    def get_by_user(self, user_id) -> List[Socket]:
        try:
            return [self._map_client_to_ws[client_id] for client_id in self._map_user_to_client[user_id]]
        except KeyError:
            return []

    def get_by_client(self, client_id) -> Socket:
        return self._map_client_to_ws[client_id]

    def _remove(self, client_id):
        logger.debug('removing socket [%s] from manager', client_id)
        socket = self._map_client_to_ws.pop(client_id)
        self._map_user_to_client[socket.user_id].remove(client_id)
        if len(self._map_user_to_client[socket.user_id]) == 0:
            del self._map_user_to_client[socket.user_id]
            logger.debug('remove socket-user binding')

    def remove(self, client_id):
        if self._remove_close_handler(client_id):
            self._close_handler(client_id)

    async def keep_alive(self, client_id):
        logger.debug('ttl prolongation for c[%s]', client_id)
        self._attach_close_handler(client_id)

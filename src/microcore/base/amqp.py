import asyncio
import json
import logging
import os
import warnings
from typing import Awaitable, Callable
from uuid import uuid4

import aioamqp
from aioamqp.channel import Channel
from aioamqp.envelope import Envelope
from aioamqp.exceptions import AioamqpException
from aioamqp.properties import Properties
from aioamqp.protocol import CLOSED, CLOSING, CONNECTING, OPEN

from microcore.base.application import Application
from microcore.base.utils import BackOff, FQN
from microcore.entity.encoders import ProxyJSONEncoder, proxy_encoder_instance
from microcore.entity.model import JSON_TYPE_FIELD, public_attributes

logger = logging.getLogger(__name__)

AMQP_BROKER_URL = os.environ.get('AMQP_DSN', 'amqp://localhost:5672/')

EXCHANGE_DIRECT = 'direct'
EXCHANGE_FANOUT = 'fanout'
EXCHANGE_TOPIC = 'topic'
EXCHANGE_HEADERS = 'headers'

DEFAULT_EXCHANGE_TYPE = EXCHANGE_DIRECT

STATE_CONNECTING = CONNECTING
STATE_OPEN = OPEN
STATE_CLOSING = CLOSING
STATE_CLOSED = CLOSED
STATE_SHUTDOWN = 4


class _AMQPMixin:
    """
    mixin wrapper to aioamqp library

    :type _transport : asyncio.transports.Transport
    :type _protocol : aioamqp.protocol.AmqpProtocol
    :type _channel : aioamqp.channel.Channel
    """

    def __init__(self, queue_name='',
                 exchange_name='',
                 exchange_type=DEFAULT_EXCHANGE_TYPE,
                 routing_key='',
                 durable=True,
                 amqp_url=AMQP_BROKER_URL,
                 loop=None):
        self._exchange_name = exchange_name
        self._exchange_type = exchange_type
        self._queue_name = queue_name
        self._routing_key = routing_key
        self._durable = durable
        self._url = amqp_url
        self._loop = loop or asyncio.get_event_loop()

        self._state = STATE_CONNECTING
        self._transport = None
        self._protocol = None
        self._channel = None

        self.on_error = None

    async def connect(self):
        back_off = BackOff()
        while True:
            try:
                self._state = STATE_CONNECTING
                self._transport, self._protocol = \
                    await aioamqp.from_url(
                        self._url,
                        on_error=self.on_error,
                        loop=self._loop
                    )
                back_off.reset()
                logger.info('RMQ connection established in %s', self)
                self._state = STATE_OPEN
                return
            except (aioamqp.AmqpClosedConnection, ConnectionError):
                timeout = back_off.next_timeout()
                logger.warning('RMQ host unreachable, will try to reconnect in %s', timeout)
                await asyncio.sleep(timeout)

    closing_exceptions = (aioamqp.exceptions.AmqpClosedConnection, aioamqp.exceptions.ChannelClosed)

    def error_handler(self, exception, reinit: Callable[[], Awaitable]):
        if not isinstance(exception, self.closing_exceptions):
            exc_info = (type(exception), exception, exception.__traceback__)
            logger.exception('AMQP error occurred: %s %s', type(exception), exception, exc_info=exc_info)
        if isinstance(exception, self.closing_exceptions) and self._state != STATE_SHUTDOWN:
            self._loop.create_task(self._reconnect(reinit))
        else:
            logger.info('shutdown exception occurred: %s', exception)

    async def _reconnect(self, reinit: Callable[[], Awaitable]):
        logger.info('begin reconnect procedure')
        try:
            await reinit()
            logger.info('successfully restored consumer connection')
        except:
            logger.exception('unrecoverable error during AMQP reconnect, shutting down')
            self._loop.stop()

    async def close(self):
        self._state = STATE_SHUTDOWN
        await self._protocol.close()
        logger.info('RMQ connection closed in %s', self)

    async def open_channel(self):
        if not self._channel:
            self._channel = await self._protocol.channel()
            logger.info('RMQ channel open in %s', self)
        return self._channel

    async def close_channel(self):
        if self._channel:
            await self._channel.close()
            logger.info('RMQ channel closed in %s', self)

    async def basic_prepare(self, durable=True):
        await self.declare_queue(self._queue_name, durable)

        if self._exchange_name is not '':  # only perform exchange ops if it is not default
            await self.declare_exchange(self._exchange_name, self._exchange_type, durable)
            await self.bind_queue(self._exchange_name, self._queue_name, self._routing_key)

    async def _prepare(self, prepare: Callable[['_AMQPMixin'], None] = None):
        if prepare is None:
            await self.basic_prepare(self._durable)
        elif callable(prepare):
            await prepare(self)
        elif prepare is False:
            logger.info('skip prepare as requested')
        else:
            raise ValueError('`prepare` should be either None, False or Callable(accessor:%s)' % type(self))

    async def declare_exchange(self, name: str, typ: str, durable: bool = True, **exchange_args):
        await self._channel.exchange_declare(exchange_name=name, type_name=typ, durable=durable, **exchange_args)
        logger.debug('%s declared exchange [%s][%s][durable=%s]', self, name, typ, durable)

    async def declare_queue(self, name: str = None, durable: bool = True, **queue_args):
        result = await self._channel.queue_declare(queue_name=name, durable=durable, **queue_args)
        if not name or name == '':
            name = self._queue_name = result['queue']
        logger.debug('%s declared queue [%s][durable=%s]', self, name, durable)

    async def bind_queue(self, exchange_name: str, queue_name: str, routing_key: str):
        await self._channel.queue_bind(exchange_name=exchange_name, queue_name=queue_name, routing_key=routing_key)
        logger.debug('%s bind queue [%s] to exchange [%s] with routing key [%s]',
                     self, queue_name, exchange_name, routing_key)

    @property
    def queue_name(self):
        return self._queue_name

    @property
    def exchange_name(self):
        return self._exchange_name

    @property
    def is_durable(self):
        return self._durable

    @property
    def state(self):
        return self._protocol.state if self._state < STATE_SHUTDOWN else self._state


def _ensure_amqp_bound(fn):
    """ensure amqp primitives bound to task instance before certain methods and properties can be accessed"""

    def wrapper(self, *args, **kwargs):
        if not self._channel or not self._envelope or not self._properties:
            raise AttributeError('amqp primitives unbound, illegal operation')
        return fn(self, *args, **kwargs)

    return wrapper


class TaskMessage:
    defined_event = None
    """
    override this to define event type via class def
    """

    def __init__(self, payload=None, *, event=None, uuid=None):
        super().__init__()
        self.event = event or self.__class__.defined_event
        self.uuid = uuid or uuid4().hex
        self.payload = payload

        self._channel = None  # type: Channel
        self._envelope = None  # type: Envelope
        self._properties = None  # type: Properties

    def _bind_channel(self, channel: Channel, envelope: Envelope, properties: Properties):
        self._channel = channel
        self._envelope = envelope
        self._properties = properties

    @_ensure_amqp_bound
    async def reject(self, requeue=False):
        logger.debug('NACK tag:%s|correlation_id:%s', self._envelope.delivery_tag, self.uuid)
        return await self._channel.basic_client_nack(self._envelope.delivery_tag, requeue=requeue)

    @_ensure_amqp_bound
    async def acknowledge(self):
        logger.debug('ACK tag:%s|correlation_id:%s', self._envelope.delivery_tag, self.uuid)
        return await self._channel.basic_client_ack(self._envelope.delivery_tag)

    @property
    @_ensure_amqp_bound
    def envelope(self) -> Envelope:
        return self._envelope

    @property
    @_ensure_amqp_bound
    def channel(self) -> Channel:
        return self._channel

    @property
    def properties(self) -> Properties:
        return self._properties or {}

    @properties.setter
    def properties(self, value: dict):
        if not isinstance(value, dict):
            raise ValueError('properties should be dict')
        self._properties = value

    def __repr__(self, *args, **kwargs):
        return self.__str__()

    def __str__(self, *args, **kwargs):
        return "<%s {uuid:%s event:%s}>" % (self.__class__, self.uuid, self.event)


class Consumer(_AMQPMixin):
    async def start_consuming(self, on_message: Callable[[TaskMessage], Awaitable],
                              on_error: Callable[[BaseException], None] = None,
                              prepare: Callable[[_AMQPMixin], None] = None,
                              **consumer_args):
        """
        starts consuming messages


        :param callable on_error: on error callback
        :param callable on_message: on message callback, note what calling message.acknowledge() is up to you.

        :param callable prepare: prepare strategy callback, used to initialize channel
        (declare queues, exchanges and bindings)

        :param dict consumer_args: could pass following additional parameters to AMQP broker:

        :consumer_tag:  str, optional consumer tag
        :no_local:       bool, if set the server will not send messages to the connection that published them.
        :no_ack:         bool, if set the server does not expect acknowledgements for messages
        :exclusive:      bool, request exclusive consumer access, meaning only this consumer can access the queue
        :no_wait:        bool, if set, the server will not respond to the method
        """

        if on_error is not None:
            self.on_error = on_error

        async def _on_message(channel: Channel, body: bytes, envelope: Envelope, properties: Properties):
            logger.debug('received message from <%s> with routing_key <%s>',
                         envelope.exchange_name, envelope.routing_key)
            try:
                msg = json.loads(body.decode(),
                                 object_hook=TaskEncoder.decoder_object_hook)  # type: TaskMessage
                # noinspection PyProtectedMember
                msg._bind_channel(channel, envelope, properties)
                await on_message(msg)
            except TypeError:
                logger.exception("consumer: on_message processing failed - invalid event type")
                await self._reject_message(envelope.delivery_tag, requeue=False)
            except Exception as e:
                logger.exception("consumer: on_message processing failed:\n%s", e)
                # noinspection PyUnresolvedReferences
                await self._reject_message(envelope.delivery_tag, requeue=True)

        # todo: handle expected shutdown and connection state
        while True:
            try:
                if not self._protocol:
                    await self.connect()

                if not self._channel:
                    await self.open_channel()
                    await self._prepare(prepare)

                await self._channel.basic_consume(_on_message, queue_name=self._queue_name, **consumer_args)
                logger.info('start consuming from [q=%s]', self._queue_name)
                return
            except BackOff.LimitReached:
                logger.exception('back-off limit reached')
            except AioamqpException:
                logger.exception('amqp error while consuming')
                await self.close_channel()
                await self.close()
            except:
                logger.exception('unexpected exception in consumer coroutine, stopping process')
                self._loop.stop()
                return

    async def _acknowledge_message(self, delivery_tag: str):
        logger.debug('ACK %s', delivery_tag)
        await self._channel.basic_client_ack(delivery_tag=delivery_tag)

    async def _reject_message(self, delivery_tag: str, requeue: bool = True):
        logger.debug('NACK %s, requeue=%s', delivery_tag, requeue)
        await self._channel.basic_client_nack(delivery_tag=delivery_tag, requeue=requeue)


class Producer(_AMQPMixin):
    def __init__(self, *args, default_properties: dict = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._default_properties = default_properties or {}

    async def start_producing(self,
                              on_error: Callable[[BaseException], None] = None,
                              prepare: Callable[[_AMQPMixin], None] = None):
        """
        start channel to enable producing capabilities

        :param callable on_error: on error callback
        :param callable prepare: prepare strategy callback, used to initialize channel
        (declare queues, exchanges and bindings)
        """
        if on_error is not None:
            self.on_error = on_error
        await self.connect()
        await self.open_channel()
        await self._prepare(prepare)

    async def publish(self, message: TaskMessage, *, properties=None, routing_key: str = None):
        # todo: handle connection loss
        payload = self._prepare_payload(message)
        properties = properties or {}
        full_property_set = self._prepare_properties(message, properties)
        routing_key = routing_key or self._routing_key or message.event
        await self._channel.publish(
            payload=payload,
            exchange_name=self._exchange_name,
            routing_key=routing_key,
            properties=full_property_set
        )
        logger.info('posted rmq-task: %s to exchanges %s with routing_key=%s and properties: %s',
                    message, self._exchange_name, routing_key, full_property_set)

    def _prepare_properties(self, message, properties):
        return {
            **self._default_properties,
            **properties,
            **{
                'content_type': 'application/json',
                'correlation_id': message.uuid
            }
        }

    @staticmethod
    def _prepare_payload(message):
        return json.dumps(message, cls=TaskEncoder)


class UnboundProducer(Producer):
    async def start_producing(self,
                              on_error: Callable[[BaseException], None] = None,
                              prepare: Callable[[_AMQPMixin], None] = None):
        return await super().start_producing(on_error, prepare or False)

    async def publish(self, message: TaskMessage, *, properties=None, routing_key: str = None, exchange: str = None):
        # todo: handle connection loss
        payload = self._prepare_payload(message)
        properties = properties or {}
        full_property_set = self._prepare_properties(message, properties)
        routing_key = routing_key or self._routing_key or message.event
        exchange = exchange or self._exchange_name
        await self._channel.publish(
            payload=payload,
            exchange_name=exchange,
            routing_key=routing_key,
            properties=full_property_set
        )
        logger.info('posted rmq-task: %s to exchanges [%s] with routing_key=%s and properties: %s',
                    message, exchange, routing_key, full_property_set)


class ConsumerWorker(Application):
    def __init__(self, consumer: Consumer, **kwargs):
        super().__init__(**kwargs)
        self._consumer = consumer

    async def on_message(self, message: TaskMessage):
        pass

    def on_consumer_error(self, exception: BaseException):
        """
        this function is a coroutine

        :param exception: aioamqp generated exception
        """
        return self._consumer.error_handler(exception, self._init_consumer)

    async def _init_consumer(self):
        await self._consumer.start_consuming(on_message=self.on_message, on_error=self.on_consumer_error)

    async def _setup(self):
        await super()._setup()
        await self._init_consumer()

    async def _shutdown(self):
        await self._consumer.close()
        await super()._shutdown()
        logger.info('shutdown complete')


class ProducerWorker(Application):
    def __init__(self, producer: Producer, **kwargs):
        super().__init__(**kwargs)
        self._producer = producer

    async def _init_producer(self):
        await self._producer.start_producing(on_error=self.on_producer_error)

    def on_producer_error(self, exception: BaseException):
        """
        this function is a coroutine

        :param exception: aioamqp generated exception
        """
        return self._producer.error_handler(exception, self._init_producer)

    async def _setup(self):
        await super()._setup()
        await self._init_producer()

    async def _shutdown(self):
        await super()._shutdown()
        await self._producer.close()


class TaskEncoder(ProxyJSONEncoder):
    POINTER_PREFIX = 'task__'

    def default(self, obj: object):
        if isinstance(obj, TaskMessage):
            if hasattr(obj.payload, '__dict__'):  # instance of custom class, not built-in type
                payload = ProxyJSONEncoder.default(self, obj.payload)
            else:
                payload = obj.payload
            return {JSON_TYPE_FIELD: self.POINTER_PREFIX + FQN.get_fqn(obj),
                    **public_attributes(obj),
                    'payload': payload}
        return ProxyJSONEncoder.default(self, obj)

    @classmethod
    def decoder_object_hook(cls, dct: dict):
        type_pointer = dct.get(JSON_TYPE_FIELD)  # type: str
        if type_pointer is not None and type_pointer.startswith(cls.POINTER_PREFIX):
            dct.pop(JSON_TYPE_FIELD)
            event_payload_type = cls._get_payload_type_for_event(dct['event'])
            if not event_payload_type:
                warnings.warn('unbound payload types are discouraged, in %s' % dct['event'], DeprecationWarning)
            if event_payload_type is not False and not isinstance(dct['payload'], event_payload_type):
                raise TypeError('incorrectly formed event object')
            type_ref = FQN.get_type(type_pointer.split('__')[1])
            return type_ref(**dct)
        return proxy_encoder_instance.decoder_object_hook(dct)

    _event_payload_type_map = {}

    @classmethod
    def register_type_for_event(cls, event: str, typ: type):
        if event in cls._event_payload_type_map:
            raise IndexError('event class already registered')
        cls._event_payload_type_map[event] = typ

    @classmethod
    def _get_payload_type_for_event(cls, event: str):
        if event in cls._event_payload_type_map:
            return cls._event_payload_type_map[event]
        return False

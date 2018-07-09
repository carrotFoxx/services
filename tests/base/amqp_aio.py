import asyncio
import json
from typing import Any
from unittest import TestCase

from microcore.base.amqp import Consumer, Producer, TaskEncoder, TaskMessage
from tests import EntityTest


class EventTest(TaskMessage):
    defined_event = 'event.test'

    def __init__(self, payload: Any = None, *, event: str = None, uuid: str = None, extra: str = None):
        super().__init__(payload, event=event, uuid=uuid)
        self.extra = extra

    TaskEncoder.register_type_for_event(defined_event, EntityTest)


class TestTaskEncoder(TestCase):
    def test_encode_decode(self):
        r = json.dumps(TaskMessage(event='something'), cls=TaskEncoder)
        self.assertIsInstance(r, str)
        r = json.loads(r, object_hook=TaskEncoder.decoder_object_hook)
        self.assertIsInstance(r, TaskMessage)

    def test_proxy_encoder(self):
        original = EventTest(EntityTest(), extra='extra-value')

        r = json.dumps(original, cls=TaskEncoder)
        self.assertIsInstance(r, str)

        r = json.loads(r, object_hook=TaskEncoder.decoder_object_hook)
        self.assertIsInstance(r, TaskMessage)
        self.assertIsInstance(r, EventTest)

        self.assertIsInstance(r.payload, EntityTest)

        self.assertEqual(original.extra, r.extra)
        self.assertEqual(original.payload.uid, original.payload.uid)

    def test_complex_task_encode_decode(self):
        original = EventTest(EntityTest(child=EntityTest()))
        r = json.dumps(
            original,
            cls=TaskEncoder
        )
        self.assertIsInstance(r, str)
        r = json.loads(r, object_hook=TaskEncoder.decoder_object_hook)
        self.assertIsInstance(r, TaskMessage)

        self.assertIsInstance(r.payload, EntityTest)
        self.assertIsInstance(r.payload.child, EntityTest)

        self.assertEqual(r.payload.uid, original.payload.uid)
        self.assertEqual(r.payload.child.uid, original.payload.child.uid)


class TestAMQP(TestCase):
    def test_produce_consume(self):
        p = Producer(queue_name='test', routing_key='test', durable=False)
        c = Consumer(queue_name='test', routing_key='test', durable=False)

        rlist = []

        async def on_message(message: TaskMessage):
            rlist.append(message)
            print('receive message: %s' % message)
            await message.acknowledge()

        async def test():
            await p.start_producing()
            await c.start_consuming(on_message=on_message)

            for x in range(10):
                print("publish payload %s" % x)
                await p.publish(TaskMessage({'msg_id': x}, event='something.happen'))

            await p.close()

            await asyncio.sleep(0)
            await c.close()

        asyncio.get_event_loop().run_until_complete(test())

        self.assertEqual(10, len(rlist))

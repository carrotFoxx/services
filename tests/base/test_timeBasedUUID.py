import datetime
from unittest import TestCase

from microcore.base.utils import TimeBasedUUID


class TestTimeBasedUUID(TestCase):
    def test_from_timestamp(self):
        uuids = {TimeBasedUUID.from_timestamp(timestamp=t): t
                 for t in [
                     self.generate_ts("2017-02-04T11:05:29.000Z"),
                     self.generate_ts("2017-02-05T11:05:29.000Z"),
                     self.generate_ts("2017-02-06T11:05:29.000Z"),
                     self.generate_ts("2017-02-07T11:05:29.000Z"),
                     self.generate_ts("2017-02-08T11:05:30.000Z"),
                     self.generate_ts("2017-02-09T11:05:30.000Z"),
                     self.generate_ts("2017-02-10T11:05:30.000Z"),
                     self.generate_ts("2017-02-11T11:05:30.000Z"),
                     self.generate_ts("2017-02-12T11:05:30.000Z"),
                     self.generate_ts("2017-02-13T11:05:30.000Z"),
                     self.generate_ts("2017-02-14T11:05:29.000Z")
                 ]}

        gen_len = len(uuids)
        sorted_uuids = sorted(uuids.keys())  # type: list
        ts_index = {v: k for k, v in uuids.items()}
        sorted_ts = sorted(ts_index.keys())

        for x in sorted_ts:
            print(x, ts_index[x], sorted_uuids.index(ts_index[x]), sep='|')

        self.assertEqual(gen_len, len(set(uuids.keys())))
        self.assertLess(uuids[sorted_uuids.pop(0)], uuids[sorted_uuids.pop()])

    @staticmethod
    def generate_ts(date):
        return datetime.datetime.strptime(date, '%Y-%m-%dT%H:%M:%S.000Z').timestamp()

    def test_custom_uuid_collision(self):
        ts = datetime.datetime.now().timestamp()

        u_map = dict()
        collision_count = 0
        for x in range(0, int(1e6)):
            kts = ts + datetime.datetime.now().microsecond / 1e6
            uuid = TimeBasedUUID.from_timestamp(kts)
            if u_map.get(uuid):
                collision_count += 1
            u_map[uuid] = 1

        print('collisions:%s' % collision_count)
        if collision_count > 30000:
            self.fail()

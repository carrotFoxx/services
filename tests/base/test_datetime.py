from datetime import datetime

import pytest

from microcore.base.datetime import parse_datetime


def test_parse_datetime():
    date_local = parse_datetime('2017-09-20T19:41:59.6001+03:00')
    assert isinstance(date_local, datetime)
    assert date_local.microsecond == 600100
    assert date_local.utcoffset().seconds == 10800

    date_utc = parse_datetime('2017-09-20T16:41:59.6001Z')
    assert isinstance(date_utc, datetime)
    assert date_utc.utcoffset().seconds == 0

    assert date_local == date_utc


@pytest.mark.parametrize("date", [
    '2017-09-20T19:41:59.600+03:00',
    '2017-09-20T19:41:59.6001+03:00',
    '2017-09-20T19:41:59.600100+03:00',
    '2017-09-20T16:41:59.600Z',
    '2017-09-20T16:41:59.6001Z',
    '2017-09-20T16:41:59.600100Z'
])
def test_regex_parse_datetime(date: str):
    print(date, parse_datetime(date))

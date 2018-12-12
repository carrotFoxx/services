import logging
import sys

import pymongo
from pymongo.errors import ConnectionFailure

log_fmt = "[%(asctime)s]:" + logging.BASIC_FORMAT
logging.basicConfig(stream=sys.stdout, format=log_fmt, level=logging.DEBUG)

source = pymongo.MongoClient(host='10.0.0.12', port=30017)
target = pymongo.MongoClient(host='localhost', port=27017)
try:
    # The ismaster command is cheap and does not require auth.
    source.admin.command('ismaster')
    target.admin.command('ismaster')
except ConnectionFailure:
    logging.exception('failed to connect data-sources')

src_col = source.get_database('events').get_collection('cef')
tgt_col = target.get_database('events').get_collection('cef')

tgt_col.drop()

counter = 0
for d in src_col.find().limit(10000):
    tgt_col.insert_one(d)
    counter += 1
    if counter % 100 == 0:
        logging.debug('loaded %d', counter)

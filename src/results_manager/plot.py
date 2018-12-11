import logging
from datetime import datetime
from typing import Awaitable

from motor.core import AgnosticCollection

log = logging.getLogger(__name__)


class Plot:
    def __init__(self, start: datetime, end: datetime, n_steps: int) -> None:
        self.start = int(start.timestamp() * 1000)
        self.end = int(end.timestamp() * 1000)
        ts_range = self.end - self.start
        self.n_steps = n_steps
        self.step = int(ts_range / n_steps)
        log.info('creating graph using (start:%s, end:%s, step:%s, n_steps:%s)',
                 self.start, self.end, self.step, n_steps)

    async def create(self, cef_source: AgnosticCollection, anomaly_source: AgnosticCollection, query: dict = None):
        anomalies = await self._anomalies(anomaly_source)
        amounts = await self._amounts(cef_source, query=query)
        return self._prepare_points(anomalies, amounts)

    def _anomalies(self, collection: AgnosticCollection, ts_field: str = 'ts') -> Awaitable[list]:
        ts_field_expr = f'${ts_field}'
        return collection.aggregate([
            {
                '$match': {
                    ts_field: {'$gte': self.start, '$lt': self.end}
                }
            },
            {
                '$group': {
                    '_id': {
                        '$trunc': {
                            '$divide': [
                                {'$subtract': [ts_field_expr, self.start]},
                                self.step
                            ]
                        }
                    },
                    "amount": {'$sum': 1},
                    "r_start": {'$min': ts_field_expr},
                    "r_end": {'$max': ts_field_expr},
                }
            },
            {
                '$sort': {'_id': 1}
            }
        ]).to_list(self.n_steps + 1)

    def _amounts(self, collection: AgnosticCollection, ts_field: str = 'extensions.rt',
                 query: dict = None) -> Awaitable[list]:
        query = query or {}
        ts_field_expr = f'${ts_field}'
        return collection.aggregate([
            {
                '$match': {
                    **query,
                    ts_field: {"$gte": str(self.start), "$lt": str(self.end)}
                }
            },
            {
                '$group': {
                    '_id': {
                        '$trunc': {
                            '$divide': [
                                {'$subtract': [
                                    {"$convert": {"input": ts_field_expr, "to": "long"}},
                                    self.start
                                ]},
                                self.step
                            ]
                        }
                    },
                    "amount": {'$sum': 1},
                    "r_start": {'$min': ts_field_expr},
                    "r_end": {'$max': ts_field_expr},
                }
            },
            {
                '$sort': {'_id': 1}
            }
        ]).to_list(self.n_steps + 1)

    def _prepare_points(self, anomalies: list, amounts: list):
        data = []
        idx_res = {int(x['_id']): x for x in anomalies}
        idx_ams = {int(x['_id']): x for x in amounts}
        for x in range(0, self.n_steps, 1):
            item = {'_id': x,
                    'amount': 0,
                    'total': 0}
            # attach time periods
            mx = x + 1
            if mx == 1:
                item['r_start'] = self.start
                item['r_end'] = self.start + self.step
            else:
                item['r_start'] = self.start + (mx * self.step) - (self.step - 1)
                item['r_end'] = self.start + (mx * self.step)
            # attach anomaly data
            if x in idx_res:
                item['f_evt'] = idx_res[x]['r_start']
                item['l_evt'] = idx_res[x]['r_end']
                item['amount'] = idx_res[x]['amount']
            if x in idx_ams:
                item['total'] = idx_ams[x]['amount']
            data.append(item)
        return data

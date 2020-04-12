from aiohttp.web_exceptions import HTTPBadRequest
import logging
from typing import MutableMapping

import trafaret as t
from aiohttp import web
from yarl import URL

logger = logging.getLogger(__name__)

__all__ = (
    'DEFAULT_LIMIT',
    'Pagination'
)

#: The default number of resources on a page.
DEFAULT_LIMIT = 25


class Pagination():
    """
    Implements a pagination based on *limit* and *offset* values.

    .. code-block:: text

        /api/Article/?_limit=5&_offset=10

    :arg int limit:
        The number of resources on a page.
    :arg int offset:
        The offset, which leads to the current page.
    :arg int total:
        The total number of resources in the collection.
    """

    def __init__(self, request: web.Request, total: int = 0):
        """
        Initialize limit-offset paginator.

        :param request: Request instance
        :param total: Total count of resources
        """
        self.request = request
        self.total = total

        self.limit = request.query.get('_limit', DEFAULT_LIMIT)
        try:
            self.limit = int(t.Int(gt=0).check(self.limit))
        except t.DataError:
            raise HTTPBadRequest(reason='The limit must be an integer > 0. parameter=_limit')

        self.offset = request.query.get('_offset', 0)
        try:
            self.offset = int(t.Int(gte=0).check(self.offset))
        except t.DataError:
            raise HTTPBadRequest(reason='The offset must be an integer >= 0. parameter=_offset'
                                 )

        if self.offset % self.limit != 0:
            logger.warning('The offset is not dividable by the limit.')

    @property
    def url(self) -> URL:
        return self.request.url

    def links(self) -> MutableMapping:
        """
        Return pagination links.

        **Must be overridden.**

        A dictionary, which must be included in the top-level *links object*.
        It contains these keys:

        *   *self*
            The link to the current page

        *   *first*
            The link to the first page

        *   *last*
            The link to the last page

        *   *prev*
            The link to the previous page (only set, if a previous page exists)

        *   *next*
            The link to the next page (only set, if a next page exists)
        """
        result = {
            'self': self.page_link(limit=self.limit, offset=self.offset),
            'first': self.page_link(limit=self.limit, offset=0),
            'last': self.page_link(
                limit=self.limit,
                offset=int(
                    (self.total - 1) / self.limit) * self.limit
            )
        }
        if self.offset > 0:
            result['prev'] = self.page_link(
                limit=self.limit,
                offset=max(self.offset - self.limit, 0)
            )
        if self.offset + self.limit < self.total:
            result['next'] = self.page_link(
                limit=self.limit,
                offset=self.offset + self.limit
            )
        return result

    def meta(self) -> MutableMapping:
        """
        Return meta object of paginator.

        *   *total-resources*
            The total number of resources in the collection
        *   *page-limit*
            The number of resources on a page
        *   *page-offset*
            The offset of the current page
        """
        return {
            '_total': self.total,
            '_limit': self.limit,
            '_offset': self.offset
        }

    def page_link(self, **kwargs) -> str:
        """
        Return link to page.

        Uses the :attr:`uri` and replaces the *page* query parameters with the
        values in *pagination*.

        .. code-block:: python3

            pager.page_link({"offset": 10, "limit": 5})
            pager.page_link({"number": 10, "size": 5})
            pager.page_link({"cursor": 1, "limit": 5})
            # ...

        :param kwargs: Additional parameters to query string
        :rtype: str
        :return: The URL to the page
        """
        query = self.request.query.copy()
        query.update({
            f'_{key}': str(value)
            for key, value in kwargs.items()
        })

        return str(self.request.url.update_query(query))

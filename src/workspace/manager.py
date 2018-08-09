import asyncio
import logging

from common.entities import Workspace
from microcore.base.repository import Repository
from microcore.entity.bases import DateTimePropertyHelperMixin

logger = logging.getLogger(__name__)


class WorkspaceManager(DateTimePropertyHelperMixin):
    def __init__(self, workspaces: Repository, loop=None) -> None:
        super().__init__()
        self._loop = loop or asyncio.get_event_loop()
        self.workspaces = workspaces

    async def provision(self, workspace: Workspace):
        # todo: schedule provisioning
        logger.info('scheduling a provision on %s', workspace)

    async def schedule_gc(self, workspace: Workspace):
        # todo: schedule GC
        logger.debug('scheduling gc for %s', workspace)
